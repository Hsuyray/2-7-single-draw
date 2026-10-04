# Experiment log

Standard fields per run (from the handoff): configuration (`max_draw`, bet sizing, abstraction/bucket config, iterations), seed(s), training time, node count, peak RSS, coverage by phase, missing-state distribution, current-vs-average diagnostics, a convergence metric, and a policy-performance metric.

Raw profiling output from `scripts/profile_memory.py` goes to `experiments/memory_profile/` (CSV + `_report.txt`).

## Historical results (historical, superseded by newer runs)

These numbers come from earlier notes, not from runs in this repository's current state. Blank cells mean "not recorded". They were **not** re-verified.

| ID | max_draw | Abstraction | Bet sizing | Train seed | Eval seed | Iterations | CFR nodes | Train time | Peak RSS | Coverage (overall) | Coverage by phase | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | 1 | bucket | fast | 42 | 100000 | 1,000 | 27,912 | 138.790 s | | 74.20% | predraw 76.74%, draw 64.40%, postdraw 90.98% | 957 of 3,710 evaluated decisions missing. Largest missing group: 226 at predraw, seat 0, pot 4.5, current bet 2.0, history length 0. |
| H1-cva | 1 | bucket | fast | 42 | | 1,000 | | | | | | Current-vs-average diagnostic (min visits 100, min updates 20): 574 nodes considered, 64 passed filters, 19 with zero strategy weight, 43 with L1 >= 0.5, 32 with L1 >= 1.0. One node: current = 100% fold vs average = 100% call. |
| v1 | 1 | [unknown] | full | [unknown] | | 20,000 | | | | ~98% | | `max_draw=1` is rules-incomplete. File presumably `checkpoints/production_v1.chk.gz` (not verified). |
| v2 | 5 | [unknown] | [unknown] | [unknown] | | 8,000 | | | | ~94% | | Rules-complete setting. Which of `production_v2_maxdraw5.chk.gz` / `production_v2_maxdraw5_v2.chk.gz` this is was not verified. |
| 40k | 5 | [unknown] | [unknown] | [unknown] | | 40,000 (target) | | | > ~2 GB (reported) | | | **Killed for memory**; machine severely degraded. `checkpoints/production_v2_maxdraw5_40k.chk.gz.tmp` (52.9 MB) was left behind, i.e. the process died during a checkpoint write. Cause not diagnosed. |

Observation on H1: the pot 4.5 / current bet 2.0 group matches the blinds hard-coded in `scripts/save_training_checkpoint.py` (SB 1.0 + BB 2.0 + BB ante 1.5). Predraw, seat 0, history length 0 is the first decision of the hand, so 226 missing decisions there most likely means the evaluation reached first-decision hand buckets that 1,000 training deals never sampled. Hypothesis only.

## New runs (to be filled in by the user)

Use the same seed and game config when comparing runs. Record peak RSS from the profile CSV (`rss_gb` column max) or the training log (`process_rss=` lines).

| ID | Date | Command | max_draw | Abstraction | Bet sizing | Seed | Iterations | CFR nodes | Train time | Peak RSS | tracemalloc on? | Coverage (overall / by phase) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P0-tiny | | `python -m scripts.profile_memory --iterations 50 --sample-every 10` | 5 | bucket | fast | 42 | 50 | | | | yes | | |
| P0-small-rss | | `python -m scripts.profile_memory --iterations 1000 --sample-every 50 --no-tracemalloc` | 5 | bucket | fast | 42 | 1,000 | | | | no | | |
| P0-small-trace | | `python -m scripts.profile_memory --iterations 1000 --sample-every 50` | 5 | bucket | fast | 42 | 1,000 | | | | yes | | |
| (blank) | | | | | | | | | | | | | |
| (blank) | | | | | | | | | | | | | |
| (blank) | | | | | | | | | | | | | |
