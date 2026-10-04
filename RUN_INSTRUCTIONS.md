# Run instructions (branch `unattended-writing`)

Nothing on this branch has been executed. Run the steps below **in order**, from the repository root, in PowerShell, with the venv active. Stop at the first step whose output matches a "problem" condition and look at it before going on.

```powershell
cd <path-to>\2-7-single-draw
git checkout unattended-writing
.\.venv\Scripts\Activate.ps1
python --version          # expect 3.12.x
python -c "import psutil, pytest; print(psutil.__version__, pytest.__version__)"
```

Problem: `ModuleNotFoundError` for psutil or pytest -> `python -m pip install psutil pytest` (they are not in `requirements.txt`).

## 0. Is `.venv` / `checkpoints/` tracked? (read-only checks; you decide what to do)

```powershell
git ls-files .venv | Measure-Object -Line
git ls-files checkpoints
git ls-files | Select-String "__pycache__" | Measure-Object -Line
Get-Content .gitignore
```

Expected (from the audit): about 1,891 `.venv` files, 13 files under `checkpoints/` (including `production_v2_maxdraw5_40k.chk.gz.tmp`), many `__pycache__` files, and an empty `.gitignore`.

If they are tracked and you want to stop tracking them **without deleting your local copies**, the usual steps are (not done by me):

```powershell
# add to .gitignore:  .venv/   __pycache__/   *.pyc   *.tmp   (and checkpoints/ if you want)
git rm -r --cached .venv
git rm -r --cached --quiet -- "*__pycache__*"
git rm --cached checkpoints/production_v2_maxdraw5_40k.chk.gz.tmp
git commit -m "dayNN: stop tracking venv, bytecode and temp checkpoint"
```

Notes: `--cached` only removes files from the index; they stay on disk. The large checkpoints stay in git history either way; removing them from history needs a history rewrite, which is a separate decision. If the checkpoints must stay versioned, consider Git LFS instead of untracking.

## 1. Tests

```powershell
python -m pytest tests -q
```

Expected: all tests pass **except probably one**:
- `tests/test_hand_strategy_resolver.py::test_bucket_postdraw_returns_made_hand_bucket` is expected to **fail**. It asserts `MadeHandBucket`, but the fixed resolver returns `PostdrawStrengthBucket` (see `docs/AUDIT.md` section 3). The new `tests/test_regression_fixed_bugs.py` asserts the fixed behaviour. If that old test fails, it is a stale test, not a regression; decide whether to update it.

Only the new tests (fast, under a few seconds; `test_chunked_training_matches_single_call` trains 6 iterations at `max_draw=1`):

```powershell
python -m pytest tests/test_memory_guard.py tests/test_profile_memory.py tests/test_regression_fixed_bugs.py -q
```

Problem conditions:
- Any failure in `test_regression_fixed_bugs.py` -> a fixed bug may have regressed, or my test setup is wrong. Read the assertion before changing solver code.
- `test_chunked_training_matches_single_call` fails -> splitting `train()` into chunks changes results. Then the RSS guard is **not** behaviour-preserving when enabled; use `--max-rss-gb 0` for real runs and tell me.
- An `ImportError` for `scripts.*` -> run pytest from the repository root.

## 2. Tiny profile run (smoke test, ~1 minute or less expected; not measured)

```powershell
python -m scripts.profile_memory --iterations 50 --sample-every 10
```

Expected output shape:

```
Memory profile started:
  iterations: 50
  ...
[start] iteration=0, CFR_nodes=0, rss=0.0xxxGB, elapsed=0.0s
[sample] iteration=10, CFR_nodes=..., rss=...GB, elapsed=...s
...
[sample] iteration=50, CFR_nodes=..., rss=...GB, elapsed=...s

Memory profile summary
  completed iterations: 50
  CFR nodes: ...
  training seconds: ...
  peak sampled RSS: ... GB
CFR nodes by phase:
  draw: ...
  postdraw_betting: ...
  predraw_betting: ...
CFR nodes by action count:
  ...
lru_cache sizes:
  ...
tracemalloc top 25 by filename (...):
tracemalloc top 25 by lineno (...):
CSV: ...\experiments\memory_profile\profile_md5_bucket_fast_s42_it50.csv
Report: ...\experiments\memory_profile\profile_md5_bucket_fast_s42_it50_report.txt
```

Problem conditions: any traceback; `CFR_nodes` stays 0; RSS already above 1 GB at 50 iterations.

## 3. Small profiling config (the P0 measurement)

Run both. The first gives clean RSS (tracemalloc off), the second attributes allocations (slower, RSS inflated by tracemalloc's own bookkeeping).

```powershell
python -m scripts.profile_memory --iterations 1000 --sample-every 50 --no-tracemalloc --csv experiments\memory_profile\p0_small_rss.csv
python -m scripts.profile_memory --iterations 1000 --sample-every 50 --csv experiments\memory_profile\p0_small_trace.csv
```

Optional (tests the "checkpoint save builds a large transient copy" hypothesis): add `--checkpoint-output experiments\p0_small.chk.gz`. The CSV then has an `after_checkpoint_save` row; compare its RSS with the last `sample` row.

How to read the results:
- Plot or eyeball `cfr_nodes` and `rss_gb` against `iteration` in the CSV.
- **Node count saturates, RSS keeps rising** -> the node store is not the cause; look at caches / garbage (tracemalloc lines outside `cfr_node.py`, `node_store.py`, `public_state.py`, `information_state.py`).
- **Node count and RSS rise together, roughly linearly** -> memory is dominated by nodes. Bytes per node = delta RSS / delta nodes. Check whether node growth is legitimate (state space) or fragmentation (e.g. float fields in `PublicNodeKey`).
- **tracemalloc top lines** in `cfr_node.py` (per-node dicts), `public_state.py` / `information_state.py` (keys), `draw_range_transition.py` (cache), or `deepcopy` in `cfr_trainer.py` (transient) point at the structure to examine next.
- `lru_cache sizes`: `_cached_transition_exact_key` near its `maxsize=100000` would mean that cache is full.

Record the results in `docs/EXPERIMENT_LOG.md` (rows P0-small-rss / P0-small-trace).

Problem conditions: RSS above 3 GB (the guard stops the run and prints `STOPPED BY RSS GUARD`), or the machine becomes sluggish. In that case lower `--iterations` and send me the CSV.

## 4. RSS-guard checks on the training entry point

4a. Guard trips and saves (small, safe; limit set deliberately tiny):

```powershell
python -m scripts.save_training_checkpoint --max-draw 5 --abstraction bucket --bet-sizing fast --iterations 200 --batch-size 100 --rss-check-every 20 --max-rss-gb 0.01 --seed 42 --output experiments\guard_smoke.chk.gz
```

Expected: after the first 20 iterations a `WARNING: process RSS (...) exceeded the limit (0.01 GB)` line, then `Training stopped early (RSS limit)`, `iterations: 20`, and the checkpoint path. Problem: no warning (the guard did not trip), a traceback, or no checkpoint file.

4b. Guard on (not tripped) vs off must give identical strategies:

```powershell
python -m scripts.save_training_checkpoint --max-draw 5 --abstraction bucket --bet-sizing fast --iterations 200 --batch-size 100 --seed 42 --max-rss-gb 0 --output experiments\eq_off.chk.gz
python -m scripts.save_training_checkpoint --max-draw 5 --abstraction bucket --bet-sizing fast --iterations 200 --batch-size 100 --seed 42 --max-rss-gb 12 --rss-check-every 7 --output experiments\eq_on.chk.gz
python -c "from solver.strategy_checkpoint import load_strategy_checkpoint as L; a=L('experiments/eq_off.chk.gz'); b=L('experiments/eq_on.chk.gz'); sa=a.strategy_index.strategies(); sb=b.strategy_index.strategies(); print('iterations', a.metadata.completed_iterations, b.metadata.completed_iterations); print('info sets', len(sa), len(sb)); print('IDENTICAL' if sa == sb else 'DIFFERENT')"
```

Expected: both runs print the same `CFR_nodes` per batch, and the last line prints `IDENTICAL`. (Checkpoint files are not byte-identical because metadata stores `created_at_utc` and gzip stores a timestamp; that is why the comparison loads the strategies.) Problem: `DIFFERENT` -> the guard changes results; do not use it for real runs until fixed.

## 5. What to send back

- The pytest summary line (and the names of any failures).
- `experiments\memory_profile\*_report.txt` and the CSVs from step 3.
- The last lines of steps 4a and 4b.
