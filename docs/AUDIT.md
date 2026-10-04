# Repository audit (read-only)

Date: 2026-09-30. Branch audited: `claude/2-7-single-draw-cfr-2xzbj6` at `5b82321` (`day28`).
Method: reading files and `git ls-files` only. **Nothing was executed.** Every statement below is from static reading of the code; anything about runtime behaviour is labelled as such.

## 1. Training entry point

| Script | Role |
|---|---|
| `scripts/save_training_checkpoint.py` | **Production training entry point.** CLI flags, batched training, periodic checkpoint save, existing free-memory guard. The only script that exposes `--max-draw 5` via flags. |
| `scripts/run_training.py` | Hard-coded diagnostic run (max_draw=3, bucket, 1,000 iters, stack 100, `TrainingGameFactory` with alternating button). No CLI flags. Not a production entry point. |
| `scripts/smoke_train.py`, `scripts/run_sanity_training.py` | Small smoke/sanity runs (not audited in detail). |

`save_training_checkpoint.py` flags and defaults (confirmed):

| Flag | Default | Notes |
|---|---|---|
| `--iterations` | 10 | |
| `--output` | `checkpoints/strategy.chk.gz` | same path is overwritten by every intermediate save |
| `--stack` | 20.0 | blinds are hard-coded: SB 1.0, BB 2.0, BB ante 1.5 |
| `--max-draw` | **2** | choices 0..5. Default is *not* the rules-complete 5. |
| `--abstraction` | **exact** | `exact` or `bucket` |
| `--traversal-mode` | external_sampling | or `full` |
| `--draw-action-mode` | auto | `auto` resolves to `full` |
| `--bet-sizing` | fast | `none` / `fast` / `full` |
| `--seed` | 42 | trainer RNG seed **and** base deck seed |
| `--seed-mode` | sequential | deck seed = `seed + game_counter`; `fixed` uses the same deck every iteration |
| `--batch-size` | 500 | iterations between memory checks / checkpoint saves |
| `--min-free-memory-gb` | 2.0 | **existing guard**: stops and saves when *system available memory* (`psutil.virtual_memory().available`) drops below this. It does not look at process RSS. |
| `--checkpoint-every-batches` | 1 | 0 disables intermediate saves |

Seeds / iteration mechanics (confirmed by reading `CFRTrainer.train`):
- `CFRTrainer.__post_init__` creates `self._random = random.Random(random_seed)` once. `train()` does not reset any RNG or counter, so calling `train(k)` twice is the same as `train(2k)`. The script's `game_counter` lives in a closure and also persists across batches. **Batching therefore does not change results.** (Static reasoning, not verified by a run.)
- One iteration = one sampled deal, then two traversals (seat 0, seat 1) on `deepcopy`s of that deal.

Checkpoint saving (`CFRTrainer.save_checkpoint` -> `strategy_checkpoint.save_strategy_checkpoint`):
- Saves **only the average strategy** (`StrategyIndex.strategies()`) plus metadata, format version 3 (`CHECKPOINT_FORMAT_VERSION = 3`). **Regret sums, strategy sums and visit counts are not saved, so a checkpoint cannot resume training.** A run stopped by any memory guard cannot be continued; it can only be re-run from scratch.
- Writes to `<path>.tmp` with gzip+pickle, then `replace()`. It builds the whole strategy mapping in memory before pickling (a transient copy proportional to node count).

## 2. How nodes, regrets, strategy sums and keys are stored

- `solver/node_store.py`: `NodeStore.nodes: dict[InformationState, CFRNode]`. Plain dict, never pruned during training.
- `solver/cfr_node.py`: `CFRNode` is a regular `@dataclass` (**no `__slots__`**) with
  - `actions: tuple[SolverAction, ...]`
  - `regret_sum: dict[SolverAction, float]`, `strategy_sum: dict[SolverAction, float]` (two dicts per node)
  - `visit_count`, `strategy_update_count`, `regret_update_count` (int), `strategy_weight_sum` (float).
- Info-set key: `solver/information_state.py` `InformationState` (frozen dataclass): `observer_seat: int`, `public_node: PublicNodeKey`, `own_hand_key: ExactHandKey | DrawHandBucket | PostdrawStrengthBucket`.
- `solver/public_state.py` `PublicNodeKey` (frozen dataclass): `phase: str`, `acting_seat`, `button_seat`, **`pot: float`, `current_bet: float`, `minimum_raise_size: float`**, `players: tuple[PublicPlayerState, ...]` (each with **`stack: float`, `committed_total: float`, `committed_this_round: float`**, flags, `draw_count`), and `action_history: tuple[PublicAction, ...]`.
  - Observation (not a confirmed bug): keys contain raw floats. Two states that differ only by float residue (e.g. `0.30000000000000004` vs `0.3`) would hash to different keys. This is on the handoff's fragmentation watch-list and is a candidate explanation for node growth, **unverified**.
  - Each `PublicNodeKey` is built fresh by `PublicNodeKey.from_game` per lookup; stored keys are not interned/shared across hand buckets (static reading).
- Private-key abstraction (bucket mode): predraw/draw -> `draw_hand_bucket(hand)`; postdraw -> `postdraw_strength_bucket(hand)` (128 buckets).

Caches found (`lru_cache`):
- `solver/postdraw_strength_bucket.py`: `_score_frequencies` (maxsize=1), `_score_to_bucket` (maxsize=1). Bounded.
- `solver/draw_range_transition.py`: `_cached_transition_exact_key` (maxsize=100_000). Bounded by count, not bytes. Not imported by `cfr_trainer.py` directly (static reading); whether the training path reaches it was not traced.
- No module-level unbounded dict caches were found by grep (`*cache* = {}` patterns).

## 3. Regression tests for the two fixed bugs

| Fixed bug | Existing coverage | Verdict |
|---|---|---|
| Exact float equality in `game_state.py` (betting-round termination `_is_betting_round_complete`, all-in detection in `_apply_raise`; both now use `CHIP_EPSILON = 1e-9`) | `tests/test_game_state.py` only uses exactly representable values (1.0, 2.0, 3.0...). No test injects float residue. | **Missing.** Added (Task 4) in `tests/test_regression_fixed_bugs.py`. |
| Wrong bucket type in `hand_strategy_resolver.py` postdraw lookups | `tests/test_hand_strategy_resolver.py::test_bucket_postdraw_returns_made_hand_bucket` asserts `isinstance(result, MadeHandBucket)`. The current resolver returns `postdraw_strength_bucket(hand)`, a `PostdrawStrengthBucket`, which is **not** a subclass of `MadeHandBucket`. | **Existing test appears stale: it asserts the pre-fix behaviour and should fail against the current code** (static reading; not run). A correct regression test was added (Task 4) in `tests/test_regression_fixed_bugs.py`. The stale test was **not** edited (left for the user to decide). |

Remaining exact float comparisons in `solver/game_state.py` (observations only, **not changed**): `PlayerState.commit_chips` `if self.stack == 0` (line ~108), `legal_actions` `if to_call == 0` (line ~247), `_apply_raise` `if raise_size >= self.minimum_raise_size`. A stack residue such as `1e-12` would leave a player not marked all-in and able to "raise" by a residue amount. Hypothesis only; no failing case was observed.

## 4. Tracked files that probably should not be tracked

- `.gitignore` exists but is **empty**.
- `requirements.txt` exists but is **empty**. `psutil` 7.2.2 and pytest 9.x are installed in the committed `.venv`, and `save_training_checkpoint.py` already does `import psutil` at module import time.
- `.venv/` is **tracked**: 1,891 files under `.venv/` in `git ls-files`.
- `__pycache__/*.pyc` under `scripts/`, `solver/`, `tests/` are **tracked**.
- `checkpoints/` is **tracked**: 13 files, ~148 MB on disk, including
  - `production_v2_maxdraw5_40k.chk.gz.tmp` (52.9 MB) - a temporary file left by `save_strategy_checkpoint`. Its presence is evidence that the 40k run was **killed while writing a checkpoint** (the `finally: unlink()` never ran). Whether the kill coincided with the save or just an intermediate save in progress is unknown.
  - `production_v2_maxdraw5.chk.gz` (29.5 MB) and `production_v2_maxdraw5_v2.chk.gz` (59.0 MB): two max_draw=5 checkpoints; their metadata was not read (no code executed).
- `data/starting_ranges/*.pkl` are tracked (probably intended; they are precomputed inputs).

## 5. Discrepancies with the handoff document

| Handoff says | Repo shows |
|---|---|
| `CLAUDE_CODE_HANDOFF.md` in repo | Not present in the repo; content was only supplied in the prompt. |
| "Save results under `experiments/` or `logs/` [VERIFY]" | Neither directory exists. No experiment-log convention in the repo. New tooling uses `experiments/` (decision logged in `UNATTENDED_REPORT.md`). |
| Entry point `scripts/run_training.py` or `save_training_checkpoint.py` [VERIFY] | `save_training_checkpoint.py` is the configurable one; `run_training.py` is a hard-coded diagnostic. |
| Training has no memory safety | A free-system-memory guard (`--min-free-memory-gb`, default 2 GB, checked per batch of 500 iterations) already exists. It checks *available system memory*, not process RSS, and only between batches. |
| v2 checkpoint = max_draw=5, 8,000 iters | Two v2 files exist (`production_v2_maxdraw5.chk.gz`, `production_v2_maxdraw5_v2.chk.gz`); which one is the 8k run was not determined. |
| "Key files" list | All listed files exist at the stated paths. |
| README empty | Confirmed (0 bytes). |
