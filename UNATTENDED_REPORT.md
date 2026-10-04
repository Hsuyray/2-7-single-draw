# Unattended session report

Branch: `unattended-writing` (created from `claude/2-7-single-draw-cfr-2xzbj6` @ `5b82321 day28`). Local commits only (`day29: ...`), **not pushed**. Nothing was executed except `python -m py_compile` on files I wrote (Python 3.11 in the container; the stray `.pyc` files it produced were deleted).

## Files created / modified

| File | Status | One line |
|---|---|---|
| `docs/AUDIT.md` | new | Read-only audit: entry point, node/regret/key storage, regression-test coverage, tracked files, handoff discrepancies. |
| `solver/memory_guard.py` | new | `RSSGuard` (injectable RSS reader, 0 disables), `RSSCheck`, `iteration_chunks`, `current_rss_bytes` (psutil, lazy import). No CFR logic. |
| `scripts/save_training_checkpoint.py` | modified | Adds `--max-rss-gb` (default 3.0, 0 disables) and `--rss-check-every` (default 100); on exceeding the limit prints a warning, stops, and runs the existing final `save_checkpoint`. |
| `scripts/profile_memory.py` | new | Bounded profiling run (default max_draw=5, bucket, fast, seed 42, 300 iterations, hard cap 5,000): CSV of iteration / nodes / RSS / tracemalloc, then node-by-phase, action-count, lru_cache and tracemalloc report. |
| `tests/test_memory_guard.py` | new | Guard with fake RSS reader; chunked-vs-single `train()` equivalence; script loop with a fake trainer (trip, disabled, not tripped, bad arg). |
| `tests/test_profile_memory.py` | new | Arg defaults/validation/hard cap, CSV row building and round trip, phase/action histograms, peak RSS. |
| `tests/test_regression_fixed_bugs.py` | new | Float-residue betting-round termination (+/-1e-12), real difference still open, all-in within epsilon accepted; postdraw lookup returns `PostdrawStrengthBucket`; resolver key == training key for all three phases. |
| `docs/EXPERIMENT_LOG.md` | new | Historical results table (marked superseded) + blank rows for new runs. |
| `README.md` | modified (was empty) | Project summary, venv setup, module-style commands, layout, doc pointers. |
| `docs/PARALLEL_TRAINING_DESIGN.md` | new | Design discussion only: independent seeds, synchronous batched snapshot, partitioned external sampling, parallel-outside-training; risks and determinism tests. |
| `RUN_INSTRUCTIONS.md` | new | Ordered PowerShell commands, expected output, problem conditions, git ls-files checks. |
| `UNATTENDED_REPORT.md` | new | This file. |

No tracked file was deleted; no CFR, bucket, betting, info-set or checkpoint-schema code was changed.

## Decisions made without asking

1. **Branch**: created `unattended-writing` as you asked, instead of the session's default branch `claude/2-7-single-draw-cfr-2xzbj6`. No push.
2. **psutil**: `requirements.txt` is empty, so strictly psutil is "not in requirements". But `save_training_checkpoint.py` already does `import psutil` at module import, and psutil 7.2.2 is in the committed `.venv`. Using it adds no new dependency, so I used it (lazy import in `memory_guard.py`) instead of writing untested Windows `ctypes` code. I did **not** edit `requirements.txt`; I recommend adding `psutil` and `pytest` there.
3. **Where to put the guard**: new module `solver/memory_guard.py` (so both scripts and tests can import it) rather than inline in the script.
4. **Check interval**: separate `--rss-check-every` (default 100 iterations), implemented by splitting each batch's `train()` call into chunks. Reason: the batch size (500) is also the checkpoint cadence, and 500 `max_draw=5` iterations between checks seemed too coarse. Chunking is results-neutral by static reading (`train()` keeps RNG and counters across calls), and a test checks it. **With the guard disabled (`--max-rss-gb 0`) each batch is still a single `train()` call, exactly as before.**
5. **Default ON at 3 GB**: as requested. This means a run whose RSS exceeds 3 GB now stops where it previously continued. If the old 8k v2 run exceeded 3 GB (unknown), reproducing it needs `--max-rss-gb 0` or a higher limit.
6. **Single save on RSS trip**: when the RSS guard trips, the intermediate save for that batch is skipped and only the existing final save runs (the existing low-free-memory path saves twice). Reason: saving builds a full strategy copy; doing it twice under memory pressure is the riskier choice.
7. **Kept the existing free-memory guard** unchanged; the RSS guard is additional.
8. **Output format**: existing lines are unchanged; I added `max RSS` lines to the header, a `process_rss=` line after each batch when the guard is on, and a stop reason (`low memory` / `RSS limit`) in the final message.
9. **Profiler defaults**: `bucket` abstraction, `fast` sizing, stack 20, SB 1 / BB 2 / ante 1.5 (same config and seeding as `save_training_checkpoint.py`; the historical runs used bucket + fast). tracemalloc is on by default (as asked) with `--no-tracemalloc` for clean RSS, because tracemalloc inflates RSS and slows the run.
10. **Output location**: no `experiments/` or `logs/` convention existed; I used `experiments/memory_profile/`. I did not edit `.gitignore`.
11. **Stale test**: `tests/test_hand_strategy_resolver.py::test_bucket_postdraw_returns_made_hand_bucket` appears to assert the pre-fix behaviour. I did **not** edit it (no changes to existing tests without your decision); I added a correct regression test in a new file instead.
12. **Regression-test scope**: added an all-in-within-epsilon test in addition to the betting-round-termination test you named, because the handoff says *two* exact comparisons were fixed and the second is in `_apply_raise`.
13. **Commits**: tasks 7 and 8 went into one commit (`b2d6576`) because a transient tool failure blocked the separate commit; everything else is one commit per task.

## Discrepancies: handoff vs repo

- `CLAUDE_CODE_HANDOFF.md` is not in the repo (it was only in the prompt).
- A memory guard already exists in the entry point (`--min-free-memory-gb`, system available memory, per batch). The handoff implies none.
- `save_training_checkpoint.py` defaults are `--max-draw 2`, `--abstraction exact`, not the rules-complete settings.
- Checkpoints store the average strategy only (no regrets), so a guarded stop cannot be resumed.
- `checkpoints/production_v2_maxdraw5_40k.chk.gz.tmp` (52.9 MB) is tracked: the 40k run died during a checkpoint write.
- Two max_draw=5 checkpoints exist (`production_v2_maxdraw5.chk.gz`, 29.5 MB; `..._v2.chk.gz`, 59.0 MB); which one is the "8k, ~94%" v2 is not recorded.
- `.gitignore` and `requirements.txt` are both empty; `.venv/` (1,891 files), `__pycache__/*.pyc` and `checkpoints/` are tracked.
- No `experiments/` or `logs/` directory existed.
- Remaining exact float comparisons in `game_state.py` (`stack == 0`, `to_call == 0`, `raise_size >= minimum_raise_size`): not changed, only reported (`docs/AUDIT.md` section 3).
- `PublicNodeKey` holds raw floats (pot, bets, stacks): a fragmentation candidate on the handoff's watch-list. Not tested, not changed.

## Not verified (nothing was run)

- None of the new tests has run. All code was traced by hand against the real signatures (`CFRTrainer.train`, `save_checkpoint`, `GameState.apply_action`, `HandStrategyResolver.resolve`, `_private_hand_key`, `StrategyIndex.strategies`).
- That chunked `train()` calls give identical results (static reasoning + a test).
- That `scripts.*` imports work under your pytest setup (`scripts/` has no `__init__.py`; it relies on namespace packages and pytest's rootdir insertion, as `tests/__init__.py` does for `solver`).
- psutil RSS on Windows (`memory_info().rss` = working set) vs. what Task Manager shows.
- Runtime and memory of `profile_memory.py` at `max_draw=5`; whether tracemalloc overhead is acceptable at 1,000 iterations.
- Whether the old `test_bucket_postdraw_returns_made_hand_bucket` really fails (static reading says it should).
- The 4a guard smoke test assumes a Python process's RSS exceeds 0.01 GB at the first check (very likely).

## What to check first

1. `python -m pytest tests/test_memory_guard.py tests/test_profile_memory.py tests/test_regression_fixed_bugs.py -q` (see `RUN_INSTRUCTIONS.md` step 1). In particular `test_chunked_training_matches_single_call`.
2. Full suite: confirm whether `test_bucket_postdraw_returns_made_hand_bucket` fails, and decide whether to update it.
3. `RUN_INSTRUCTIONS.md` step 4b (guard on vs off must print `IDENTICAL`) before using the guard on a real run.
4. Then the P0 profiling runs (step 3) and fill in `docs/EXPERIMENT_LOG.md`.
5. The `.venv` / `checkpoints/` / `__pycache__` tracking decision (step 0).
