# CLAUDE.md: 2-7 Single Draw CFR Solver

Read this fully before touching code. The repo is authoritative: if the code disagrees with this file, say so and trust the code.

**Work is split into workstreams (WS A0..E3). Read `docs/WORKSTREAMS.md` first, find your WS, and stay inside the files that WS owns.** Other docs: `docs/AUDIT.md` (code audit), `docs/EXPERIMENT_LOG.md` (results), `docs/PARALLEL_TRAINING_DESIGN.md`, `docs/game_rules.md`, `docs/architecture_v1.md`, `RUN_INSTRUCTIONS.md`.

When reporting, separate: confirmed bug / evidence / likely cause / hypothesis / speculation.

## 1. Project

A Python solver for **2-7 Single Draw poker** using **Counterfactual Regret Minimization (CFR)**.

- A computational game-theory project on an imperfect-information extensive-form game. Not a poker bot, not standard RL (not value-based, not policy-gradient, not an MDP solve).
- **Product goal:** strategies usable by professional players, in the style of GTO Wizard. Train offline once, save checkpoints, let users query them repeatedly (Hand Mode / Range Mode) without retraining.
- **Game:** predraw betting -> draw -> postdraw betting (`predraw_betting`, `draw`, `postdraw_betting`; there is no preflop/postflop). Configurable stacks, blinds, antes. Zero-sum utilities with exact chip conservation.
- **Rules fact:** full 2-7 Single Draw allows discarding **0 to 5 cards**. `max_draw=1` is a rules-incomplete simplification. Any serious checkpoint must use `max_draw=5`.
- The trainer supports heads-up games only.

## 2. Environment and workflow

- Windows, PowerShell, Python 3.12 virtualenv. Install: `python -m pip install -r requirements.txt`.
- All scripts run as modules from the repo root: `python -m scripts.<name>`. Tests: `python -m pytest tests -q`.
- Hardware: i7-12700H (14 cores / 20 threads), 16 GB RAM. Training is single-threaded.
- Git: day-numbered commit messages (`day33`, `day34`, ...). Push through the **`Hsuyray`** GitHub account (not `ray-askew`). Do not push unless asked.
- Working loop: run a script, read the full output, pick **one** highest-priority next step, change code only when diagnostics show a clear need.
- When giving code or diffs, label each as **new file** or **overwrite existing file**.

### Key files (paths verified)
`solver/game_state.py`, `solver/cfr_trainer.py`, `solver/cfr_node.py`, `solver/node_store.py`, `solver/strategy_checkpoint.py`, `solver/hand_strategy_resolver.py`, `solver/postdraw_strength_bucket.py`, `solver/best_response.py`, `solver/bet_sizing.py`, `solver/memory_guard.py`, `scripts/save_training_checkpoint.py` (production training entry point), `scripts/profile_memory.py`, `scripts/inspect_*.py`, `scripts/evaluate_strategy_profile.py`.

## 3. State (see `docs/EXPERIMENT_LOG.md` and `docs/WORKSTREAMS.md` section 1 for numbers)

- v1 checkpoint: `max_draw=1`, 20,000 iters, ~98% coverage, `full` bet sizing. Rules-incomplete.
- v2 checkpoint: `max_draw=5`, 8,000 iters, ~94% coverage. Two v2 files exist in `checkpoints/`; which is the 8k run is not recorded.
- Checkpoint schema: v3 (`CHECKPOINT_FORMAT_VERSION`). Checkpoints hold the average strategy only (no regrets), so training cannot resume from one.
- A 40k-iteration `max_draw=5` run exceeded ~2 GB and froze the machine. Cause not yet diagnosed (workstream A1). Training now has an RSS guard (`--max-rss-gb`, default 3, 0 disables).
- Measured (1,000 iters, `max_draw=5`, bucket, fast, seed 42): 114,110 nodes, ~0.59 s/iter, RSS 0.465 GB.

### Fixed bugs (do not regress; covered by `tests/test_regression_fixed_bugs.py`)
1. Exact floating-point equality in `game_state.py` caused infinite betting loops and `RecursionError` under `full` bet sizing. **Never use exact float equality for chip/bet logic** (use `CHIP_EPSILON`).
2. `hand_strategy_resolver.py` used the wrong bucket type for postdraw lookups (must be `PostdrawStrengthBucket`).
3. Type-check error in the postdraw strength bucket inspection script.

### Known limitation (do not "fix" without a new plan)
SampledBestResponse (SBR) oscillates because action values reset every sweep. A cross-sweep accumulation fix was tried, made results worse, and was **reverted. Do not retry it.** SBR is sample-sensitive; treat it as a proxy, not true exploitability.

## 4. Non-negotiable engineering principles

1. Correctness before scale. Root-cause diagnosis before adding iterations. "Train longer" is not a fix.
2. Incremental, testable changes. No large refactors without a stated reason. Preserve the working architecture.
3. Preserve reproducibility (fixed seeds, deterministic benchmarks) and existing diagnostic/logging scripts.
4. One major variable per experiment.
5. No performance optimization before correctness, and **every optimization must reproduce identical results under a fixed seed** (same node count, same strategies) versus the baseline.
6. Technical substance over cosmetics. Do not reformat or restyle code.
7. If the user proposes an incorrect interpretation, say so directly.

For **every** proposed fix state: the failure mode it addresses, why it should work, how to test it, and what result would falsify it.

## 5. CFR correctness checklist (keep true at all times)

- Info-set keys are deterministic; identical information states give identical keys. Strategically equivalent states merge; distinct ones do not.
- Regrets update for the correct acting player. Counterfactual reach uses opponent reach and chance reach correctly.
- Strategies sum to 1, no NaN or inf. Regret matching handles negative regrets.
- Average-strategy accumulation uses the intended weighting at the correct info sets. Strategy-sum weights are nonnegative.
- Terminal utilities are zero-sum. Pot and commitments reconcile.
- Legal actions are identical in training and evaluation for equivalent states, and nonempty at nonterminal decision nodes.
- Betting and draw histories are encoded consistently across modules.
- Raise sizes are legal (pot, stack, call, commitment constraints).

### Fragmentation watch-list
Floating-point pots/stacks/bets (`PublicNodeKey` holds raw floats), inconsistent chip rounding, history-encoding differences, action-label changes, legal-action ordering, abstraction/bucket differences, draw-history representation, absolute vs player-relative positions, eval keys differing from training keys. Investigate these **before** blaming too few iterations.

## 6. Frozen interfaces (change only via the owning workstream, with a version bump)

- `InformationState` / `PublicNodeKey` key format and the checkpoint schema (v3): changing either invalidates every checkpoint and requires retraining.
- Query API JSON format (owned by WS D1) and hand-class taxonomy (owned by WS D3).

## 7. Experiment logging standard

Every experiment records: configuration (`max_draw`, bet sizing profile, bucket config, iterations), seed(s), training time, node count, peak RSS, coverage by phase, missing-state distribution, current-vs-average diagnostics, a convergence metric, a policy performance metric. Fixed seeds and identical game configs for comparisons; repeat runs where practical. Results go in `docs/EXPERIMENT_LOG.md`; raw profiling output in `experiments/memory_profile/`.

## 8. Hard rules for code changes

- Inspect existing code before changing anything.
- No unrelated refactors, renames, or reformatting.
- Keep the existing architecture unless the user approves otherwise.
- Every change ships with a diagnostic or test and a stated expected output.
- After any behavior-preserving change, prove equivalence with a fixed-seed before/after comparison (node count, strategies).
- Never use exact float equality for chips/bets.
- Multi-core training: propose options and trade-offs first (`docs/PARALLEL_TRAINING_DESIGN.md`); do not implement without approval.
- End every task with a summary: what changed, why, how it was tested, the result.
- Commit with the next day-numbered message; do not push unless asked. Never rewrite history, never delete tracked files without being asked.
