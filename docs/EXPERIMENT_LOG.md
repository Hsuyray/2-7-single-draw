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
| v2 | 5 | bucket | full (pot fractions 0.2/0.33/0.5/0.66/0.9/1.0/1.25, all-in, increment 0.1) | [unknown] | | 8,000 | 1,068,645 info sets | | | ~94% | | Rules-complete setting. Metadata read from `checkpoints/production_v2_maxdraw5.chk.gz` (stack 20, external sampling, schema v3). Hard cap for this config is 2,031,912 info sets (A1). The other v2 file (`..._v2.chk.gz`) was not read: the loader was killed by the container memory limit. |
| 40k | 5 | bucket | full (per user recollection, not verified) | [unknown] | | 40,000 (target) | | | > ~2 GB (reported) | | | **Killed for memory**; machine severely degraded. `checkpoints/production_v2_maxdraw5_40k.chk.gz.tmp` (52.9 MB) was left behind, i.e. the process died during a checkpoint write. Reported config: stack 20, bucket, full sizing. If so, the A1 hard cap is 2,031,912 info sets (~7.7 GB at 4 KB/node); see `docs/A1_REPORT.md`. |

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

## A1 measurements (day35)

| Item | Config | Result | Source |
|---|---|---|---|
| Public tree | fast, stack 20, `max_draw=5` | 12 / 133 / 2,016 public nodes (predraw / draw / postdraw); info-set cap 346,353 | `scripts/enumerate_public_tree.py` |
| Public tree | full, stack 20, `max_draw=5` | 48 / 504 / 13,248; info-set cap 2,031,912 | same |
| Float fragmentation test | both | rounding to 6 dp merges 0 nodes | same |
| Node census | fast, 60 iters, Python 3.11 | 13,209 nodes, 3,997 B/node, 71% of bytes are equal-valued duplicate objects | `scripts/inspect_memory_model.py` |
| Profile (user) | fast, 1,000 iters | 114,110 nodes, 0.465 GB RSS, 590.8 s | `experiments/memory_profile/p0_small_rss.csv` |
| Profile (user) | fast, 300 iters, tracemalloc | 52,287 nodes, 0.569 GB RSS, 1065.8 s | `experiments/memory_profile/p0_trace300.csv` |

| Node census | fast, 100 iters, Python 3.12.9 (user) | 21,487 nodes, 3,881 B/node, 74% shareable, 1,026 B after sharing | `scripts/inspect_memory_model.py` |
| Node census | full, 100 iters, Python 3.12.9 (user) | 51,514 nodes, 3,788 B/node, 73% shareable, 1,024 B after sharing; 130.3 s | same |
| Profile (user) | full, stack 20, bucket, seed 42, 2,000 iters | 562,244 nodes (draw 53,181 / postdraw 495,860 / predraw 13,203); training 2,534 s; RSS after save 2.447 GB; **process peak 3.666 GB** | `scripts/profile_memory.py`, `experiments/memory_profile/a1_full_2k.csv` (local) |

Growth of the `full` configuration (cap 2,031,912 info sets): 100 iters 51,514 (2.5%), 2,000 iters 562,244 (27.7%), 8,000 iters 1,068,645 (52.6%, `production_v2_maxdraw5.chk.gz`). See `docs/A1_REPORT.md` section 8 for the memory projections.
| Node census after interning | fast, 60 iters, Python 3.11 | 13,209 nodes (unchanged), 1,161 B/node (was 3,997), fingerprints before/after identical | `scripts/inspect_memory_model.py`, `scripts/fingerprint_node_store.py` |

| Profile with interning (user) | full, stack 20, bucket, seed 42, 2,000 iters, Python 3.12 | 562,244 nodes (identical at all 20 samples); RSS before save 0.618 GiB (was 2.097), after save 0.667 GiB (was 2.447), **process peak 1.381 GiB (was 3.666)**; iters 1,000-2,000 took 1,264 s (was 1,245 s). Total time 13,587 s inflated by stalls at iters 500-900 (machine sleep/load, not interning) | `experiments/memory_profile/a1_full_2k_interned.csv` (local) |

Fingerprint comparison on Python 3.12 (user, day42): before/after identical (`Compare-Object` and `git diff --no-index` printed nothing).

## A2 baseline evaluation reports (day46)

`python -m scripts.evaluate_checkpoint <checkpoint>` (preset `standard`, seed 2027, button 0, deck seeds >= 1e9 so never training deals). Run in the cloud container (Python 3.13, 4 cores); times on the laptop will differ. Full reports: `experiments/eval/*.json` / `.txt`. v1 was evaluated twice and `--compare` reported the two JSON reports identical outside `timing` / `environment`; the v2 second run is pending (REPRO-PENDING).

| Metric | v1 `production_v1` | v2 `production_v2_maxdraw5` |
|---|---|---|
| Config | max_draw 1, bucket, full sizing, 20,000 iters | max_draw 5, bucket, full sizing, 8,000 iters |
| Strategies (info sets) | 305,175 | 1,068,645 |
| Invalid strategies / action-space mismatches / max zero-sum error | 0 / 0 / 8.9e-15 | 0 / 0 / 8.9e-15 |
| Stored strategies near-uniform (pre / draw / post) | 78% / 86% / 70% | 82% / 93% / 81% |
| Coverage overall (20k deals) | 96.83% ± 0.06 | 92.78% ± 0.08 |
| Coverage pre / draw / post | 97.28 / 94.79 / 99.81% | 94.55 / 87.25 / 97.76% |
| Played decisions near-uniform (pre / draw / post) | 10.8 / 23.1 / 18.1% | 19.3 / 46.1 / 27.3% |
| Deals with any missing decision | 9.27% | 22.41% |
| First miss: pre / draw / post (deals) | 995 / 841 / 18 | 2,110 / 2,202 / 171 |
| Largest missing public node | root (pot 4.5, bet 2): 378 | root: 790 |
| Button-1 coverage (diagnostic) | 0.00% | 0.00% |
| Self-play seat 0 (chips/deal) | +1.20 ± 0.07 | +0.73 ± 0.07 |
| vs uniform (duplicate, 5k pairs) | +1.86 ± 0.08 | +1.12 ± 0.09 |
| vs call_station | +1.15 ± 0.09 | **+0.06 ± 0.11** |
| SBR gain seat 0 / seat 1 (mean of 5, sd) | -0.49 (0.31) / +0.70 (0.36) | -0.42 (0.43) / -0.17 (0.40) |
| SBR mean over seats (se over repeats) | +0.11 ± 0.09 | -0.30 ± 0.10 |
| SBR per-run gain se | 0.34-0.37 | 0.41-0.43 |
| Load time / total time / peak RSS | 33 s / 14 min / 2.0 GB | 147 s / 49 min / 8.2 GB |

Reading (confirmed = measured above; the rest is hypothesis):
- Confirmed: the old ~94-98% coverage numbers overstate training. A large share of decisions that "hit" a stored strategy hit a uniform one (v2 draw: 46%). Draw is the weakest phase in both.
- Confirmed: v2 does not beat a call-station that always stands pat (+0.06 ± 0.11). v1 beats it by +1.15. Hypothesis: 8k iterations is far too few for the max_draw=5 / full-sizing tree (52.6% of the info-set cap visited, A1), so many reached decisions are effectively uniform.
- Confirmed: at this budget (100 response deals, 3 sweeps) SBR does not find a response better than the profile on held-out deals (v2 mean -0.30; v1 seat 0 negative in all 5 repeats; every run used all 3 sweeps). It cannot detect exploitability at this size and is not usable as a gate yet. Hypothesis: the pure response overfits 100 deals. Next experiment (one variable): v1, response deals 100 / 300 / 1,000, everything else fixed.
- Confirmed: `production_v2_maxdraw5.chk.gz` is the 8k run. `production_v2_maxdraw5_v2.chk.gz` still could not be loaded (killed), iteration count unknown.
