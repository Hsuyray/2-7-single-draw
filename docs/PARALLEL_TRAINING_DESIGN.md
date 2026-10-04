# Parallel CFR training: design discussion (no code)

Status: **proposal only**. Nothing here is implemented. Per the handoff, P2 (multi-core) comes after P0 (memory) and needs explicit approval before any implementation.

## 0. Constraints from the current code

Facts from reading the code (see `docs/AUDIT.md`):
- `CFRTrainer.train` runs one sampled deal per iteration and traverses it twice (seat 0, then seat 1). With `external_sampling`, the traverser's actions are all explored and the opponent's actions are sampled using the trainer's single `random.Random(random_seed)`.
- Regrets and strategy sums live in one `NodeStore` dict (`InformationState -> CFRNode`, per-node `dict` regrets/strategy sums). Updates are read-modify-write on shared state.
- Deal seeds come from the caller's game factory (`seed + game_counter`).
- Checkpoints hold only the average strategy, not regrets.

Memory matters more than cores right now. A single process already exceeded ~2 GB at 40k `max_draw=5` iterations. Any design that keeps **one full `NodeStore` per worker** multiplies peak memory by the worker count; on a 16 GB machine that rules out many of them until P0 explains and reduces the per-process footprint.

Python specifics: threads do not help CPU-bound pure-Python CFR because of the GIL. Parallelism means `multiprocessing` (separate processes, separate memory, pickled messages).

## 1. Option A: independent seeds, merge at the end

Each of K workers trains an independent `CFRTrainer` with its own seed (deal seeds and sampling RNG) for N/K iterations. Afterwards, merge: for each info set, sum `strategy_sum` across workers (and optionally `regret_sum`).

Pros
- Trivial to implement, no communication during training.
- Each worker is exactly today's single-threaded code, so every worker is deterministic by construction.

Cons / convergence risk
- These are K independent CFR runs of N/K iterations each, **not** one run of N iterations. Regret matching in worker k never sees worker j's regrets, so each worker's current strategy is only N/K iterations mature. Averaging K average strategies is not guaranteed to reach the same exploitability as one N-iteration run. For Monte Carlo CFR the regret bound shrinks roughly as 1/sqrt(T) per run, so K runs of T/K iterations each are each worse, and averaging does not recover the gap in general.
- Merging `regret_sum` from independent runs and continuing from it is heuristic. The strategy sums were accumulated under different current strategies.
- Memory: K full node stores (the worst case above).
- Info-set coverage improves (more deals sampled), which might look like progress on coverage metrics even when convergence has not improved. Evaluate with exploitability proxies, not coverage alone.

Determinism test
- Fixed (seed list, K, N): run twice, merged `strategy_sum` and node key set must be bitwise identical. Merging must iterate workers in a fixed order (float addition is not associative).
- K=1 must reproduce the current single-process run exactly (same node count, same strategies).

## 2. Option B: synchronous batched (parallel) iterations with a shared snapshot

Each round: the coordinator broadcasts the current regrets (or the current strategy) to K workers. Each worker runs B iterations of external-sampling traversals against that **frozen** snapshot and returns regret and strategy-sum **deltas**. The coordinator adds the deltas in fixed worker order and starts the next round.

Pros
- Closer to single-run CFR: every worker uses the same current strategy, and all updates go into one set of regrets.
- With B=1 and K=1 it reduces exactly to today's algorithm (a strong determinism anchor).
- Deterministic if each worker's RNG is seeded from (base seed, round, worker id), and deltas are summed in worker-id order.

Cons / convergence risk
- The strategy is stale for K*B iterations: it only updates between rounds. Large K*B behaves like a larger batch and may slow convergence per iteration (the tradeoff is well known from "parallel/batched MCCFR"). The staleness should be treated as a hyperparameter and ablated.
- Communication: broadcasting the whole regret table each round is expensive in Python (pickling a large dict). Mitigations: send only regrets for info sets reachable in the next batch (not known in advance), use shared memory arrays (needs a fixed node index, which the current dict-of-dicts storage does not have), or keep workers' local mirrors updated with deltas only.
- Memory: each worker holds a mirror of the table (K copies again) unless shared memory is used. This makes Option B depend on P0 outcomes (a compact array layout would enable `multiprocessing.shared_memory`).
- Results differ from the single-process run for K>1 (different RNG streams and staleness), so "identical results" can only be required for K=1, B=1.

Determinism test
- K=1, B=1 must match the current trainer bit for bit (nodes, regret sums, strategy sums).
- Fixed (seed, K, B): two runs must be bitwise identical; run with workers finishing in different orders (inject sleeps) to prove the merge order is fixed.
- Convergence check vs single process at equal total iterations: exploitability proxy / head-to-head. Expect small degradation that grows with K*B.

## 3. Option C: partitioned external sampling (partition the tree)

Partition work by a public chance outcome or first-level public node (for example, by the traverser seat, or by the predraw hand bucket of the traverser at the root) so that workers own **disjoint** sets of info sets and never update the same node.

Pros
- No write conflicts: each info set has exactly one owner.
- Memory can be split instead of duplicated: each worker stores only its own partition.

Cons / convergence risk
- In this game nearly every info set is reachable from every deal. The traverser's private hand bucket is only part of the key; the opponent's info sets along the same path belong to other partitions. A traversal needs the **current strategy** of opponent nodes owned by other workers, so workers still need read access to others' regrets (messaging or shared memory). The naive "no communication" version is not correct.
- Partition by traversing seat (two workers, seat 0 and seat 1) is the simplest disjoint split for **updates** in external sampling: in `_external_sampling_cfr`, `accumulate_strategy` and `add_regrets` run only at the traverser's nodes (opponent nodes are only read, via `current_strategy`, and created by `get_or_create` if missing). Opponent strategy reads and node creation still cross the partition. At most 2x speedup.
- Load balance depends on the partition (bucket frequencies are skewed).

Determinism test
- Same as Option B: a 1-partition run must equal today's trainer exactly; fixed partitions + fixed seeds must be bitwise reproducible; ownership check (assert no info set is written by two workers).

## 4. Option D: parallelize outside training

Use the cores for work that is embarrassingly parallel and does not touch CFR updates:
- Running several independent experiments at once (different seeds for variance estimates, ablations), each as its own process. This directly serves the handoff's "do not draw conclusions from one noisy run" rule.
- Evaluation: sampled best response, coverage evaluation, head-to-head over fixed deal seeds split into chunks, then merged in fixed order.

Pros: zero risk to CFR correctness; results per run are identical to today's. Cons: does not speed up a single long run. Memory still scales with the number of concurrent processes.

## 5. Recommendation

1. Do nothing until P0 explains memory growth. Every option except D multiplies memory or needs a compact, index-addressable node layout.
2. First parallel step: **Option D** (parallel independent runs / evaluation). No algorithm change, immediately useful for seed variance.
3. If single-run speed is still needed: **Option B** with K=1/B=1 bit-identity as the gate, then ablate K*B against the single-process baseline on the exploitability proxy.
4. Avoid Option A as a production method; it is useful only as a cheap coverage/variance probe.

## 6. What would falsify each option

- A: merged K-worker strategy is measurably more exploitable (SBR proxy with enough response deals, or head-to-head loss) than a single run with the same total iterations.
- B: K=1/B=1 differs from the current trainer at all; or exploitability at equal wall-clock time is not better than single-process.
- C: any info set written by two workers; or speedup < ~1.3x at 2 workers after communication costs.
- D: parallel runs with the same seed differ from the same seed run alone (would indicate hidden shared state, e.g. files or caches).
