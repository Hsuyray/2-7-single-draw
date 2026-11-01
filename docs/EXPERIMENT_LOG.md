# Experiment log

Standard fields per run (from the handoff): configuration (`max_draw`, bet sizing, abstraction/bucket config, iterations), seed(s), training time, node count, peak RSS, coverage by phase, missing-state distribution, current-vs-average diagnostics, a convergence metric, and a policy-performance metric.

Raw profiling output from `scripts/profile_memory.py` goes to `experiments/memory_profile/` (CSV + `_report.txt`).

## Historical results (historical, superseded by newer runs)

These numbers come from earlier notes, not from runs in this repository's current state. Blank cells mean "not recorded". They were **not** re-verified.

**Superseded (day56):** the v1 "~98%" and v2 "~94%" coverage figures and the v1 / v2 file attributions below are replaced by the A2 benchmark reports ("A2 benchmark reports, report v2 (day55)" below): v1 96.8%, v2 92.8%, and `production_v2_maxdraw5.chk.gz` is the 8k run.

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

`python -m scripts.evaluate_checkpoint <checkpoint>` (preset `standard`, seed 2027, button 0, deck seeds >= 1e9 so never training deals). Run in the cloud container (Python 3.13, 4 cores); times on the laptop will differ. Full reports: `experiments/eval/*.json` / `.txt`. Each checkpoint was evaluated twice; `--compare` reported the two JSON reports identical outside `timing` / `environment`.

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
- Confirmed: v2 vs call_station is +0.06 ± 0.11 (v1: +1.15). Corrected reading (day49): this is **not** a failure by itself. In this two-player zero-sum game, in the seat-swapped duplicate format, an equilibrium strategy guarantees at least the game value 0 against any opponent; it does not promise to beat a weak opponent by much, and a larger margin does not mean closer to equilibrium (a maximally exploitative strategy would win more). Only a significant **loss** would prove the profile exploitable. The result is consistent with that guarantee and gives no evidence either way about convergence. Gate Q4 was changed to "does not lose" accordingly (`solver/benchmark_gates.py`).
- Confirmed: at this budget (100 response deals, 3 sweeps) SBR does not find a response better than the profile on held-out deals (v2 mean -0.30; v1 seat 0 negative in all 5 repeats; every run used all 3 sweeps). It cannot detect exploitability at this size and is not usable as a gate yet. Two hypotheses (A2_DESIGN section 11): (a) overfitting to 100 deals; (b) **fallback bias**, confirmed in code: on validation states the response never learned, it plays the profile's argmax, and for a uniform or missing strategy that is the first legal action, i.e. FOLD when facing a bet and stand pat on the draw. Experiment: `scripts/inspect_sbr_budget.py` (results below once run).
- Confirmed: `production_v2_maxdraw5.chk.gz` is the 8k run. `production_v2_maxdraw5_v2.chk.gz` still could not be loaded (killed), iteration count unknown.

## A2 SBR budget experiment (day50)

`python -m scripts.inspect_sbr_budget checkpoints/production_v1.chk.gz --check-report experiments/eval/production_v1__9069fb8b__standard__s2027.json` (user's laptop; budgets 100/300/1,000, 3 repeats, validation 1,000, sweeps <= 3, seed 2027). `CHECK OK`: the 100-deal production gains equal the standard report exactly.

| Budget | Seat | Argmax gain (sd) | Sample-fallback gain (sd) | Fallback share | Tied fallback | States learned |
|---|---|---|---|---|---|---|
| 100 | 0 | -0.36 (0.36) | -0.52 (0.44) | 66.8% | 22.8% | ~8.5k |
| 100 | 1 | +0.48 (0.20) | +0.01 (0.02) | 82.9% | 22.0% | ~7.2k |
| 300 | 0 | -0.67 (0.56) | -0.73 (0.16) | 43.6% | 19.9% | ~21.3k |
| 300 | 1 | +0.27 (0.10) | -0.22 (0.16) | 62.2% | 20.8% | ~17.3k |
| 1,000 | 0 | -0.43 (0.37) | -0.41 (0.41) | 21.6% | 13.0% | ~50k |
| 1,000 | 1 | +0.48 (0.50) | -0.25 (0.29) | 34.5% | 16.2% | ~40.5k |

Per-run gain se 0.34-0.39 throughout. Time per run: ~45 s (100), ~110 s (300), ~320-590 s (1,000).

Follow-up measurement (container, v1, seat 0, 1 repeat, validation 200): responder-state visits per learned state per sweep: **0.44** at 100 deals (97% of states <= 1 visit per sweep), **0.53** at 300 deals (94%).

Reading:
- Confirmed: (a) overfitting is falsified. Mean gain over seats is +0.06 / -0.20 / +0.02 for 100 / 300 / 1,000 deals: no rise over a 10x budget, although the fallback share fell from 67-83% to 22-35%.
- Confirmed: (b) the fallback bias is falsified, in the opposite direction. Sampling the profile on unlearned states is not better than the argmax: equal for seat 0 (mean difference -0.07 over 9 runs) and worse for seat 1 in all 9 runs (mean -0.57). Likely cause (hypothesis): folding / standing pat is cheaper than playing a uniform strategy that includes large raises with any hand.
- Confirmed: (c) SBR is sample-starved by construction. Learned states grow about linearly with deals (40-84 new states per deal), so each state's pure action is picked from roughly one sampled value per action, and values reset every sweep. More deals add states, not samples per state. The gain therefore measures replacing the profile's mixed strategy with noise-picked pure actions, which can be negative. **At any affordable budget the current SBR cannot estimate exploitability.** It stays ungated and is marked inconclusive in reports.
- Not retried: cross-sweep value accumulation (reverted earlier, CLAUDE.md).

## A2 SBR power test, first v1 run (day52)

`python -m scripts.inspect_sbr_power checkpoints/production_v1.chk.gz` (user's laptop, day51 code; leaks 0 / 0.1 / 0.3 / 1, response 300, validation 1,000, sweeps <= 3, 2 repeats, seed 2027). Gain = mean of 2 runs ± mean per-run se.

| Responder | Mode | Leak 0 | 0.1 | 0.3 | 1 | Verdict |
|---|---|---|---|---|---|---|
| seat 0 | reference exploit | -1.94 | -0.51 | -0.38 | +0.75 ± 0.11 | |
| seat 0 | per_state | -0.20 ± 0.35 | -0.19 | -0.29 | +0.38 ± 0.17 | PASS (51% of reference) |
| seat 0 | grouped | +0.51 ± 0.36 | +0.43 | -0.15 | **+1.70 ± 0.22** | PASS |
| seat 1 | reference exploit | -1.02 | -0.01 | +0.18 | +0.095 ± 0.05 | |
| seat 1 | per_state | +0.23 | +0.53 | +0.31 | -0.03 ± 0.04 | (invalid test, see below) |
| seat 1 | grouped | +0.36 | +0.08 | +0.69 | +0.07 ± 0.04 | (invalid test, see below) |

Fallback share: grouped 2-8% (except seat 1 leak 1), per_state 38-70%. Policy keys: grouped ~6-7k vs per_state ~17-22k at 300 deals.

Reading:
- Confirmed: with the leak in seat 1, grouped SBR finds the full leak at +1.70 ± 0.22, more than the hand-written exploit (+0.75); the original per-state SBR finds only +0.38 ± 0.17. Grouped is the clearly stronger detector.
- Confirmed: the seat 1 rows are a **test-design error**, not an estimator failure. The day51 leak applied to every state with FOLD, including seat 0's first decision facing the big blind. At leak 1 seat 0 folds every hand at once, so seat 1 never acts: reference exploit +0.095, SBR runs took 6-8 s with 108-289 policy keys and 88-100% fallback.
- Fix (day52): the leak applies only when the opponent's last public action is a voluntary raise; a P0 check marks a test "INVALID" when the reference exploit itself is not significant. On v1, all 79,010 seat-1 FOLD states face a voluntary raise (0 differ), so the seat-0 responder results above are unchanged by the fix; 1,348 seat-0 root FOLD states are now excluded.
- Not yet shown: power for small leaks (0.1, 0.3). Per-run se ~0.35 at 1,000 validation deals is larger than those leaks' effect; the hand-written reference does not gain there either.
- Pending: rerun with `--responder-seats 1` on the day52 code.

## A2 SBR power test, seat 1 rerun (day53)

`python -m scripts.inspect_sbr_power checkpoints/production_v1.chk.gz --responder-seats 1 --out-dir experiments/eval/power_seat1` (user's laptop, day52 code: leak only after a voluntary raise). Leak 0 rows are bit-identical to the day51 run (same seeds; the rule change does not touch leak 0).

| Responder | Mode | Leak 0 | 0.1 | 0.3 | 1 | Verdict |
|---|---|---|---|---|---|---|
| seat 1 | reference exploit | -1.02 | -1.13 | -0.19 | **+1.98 ± 0.22** | P0 ok |
| seat 1 | per_state | +0.23 ± 0.36 | +0.24 | -0.21 | +0.31 ± 0.22 | **FAIL** (16% of reference) |
| seat 1 | grouped | +0.36 ± 0.38 | +0.55 | +0.36 | **+3.13 ± 0.24** | **PASS** |

Combined with day52 (seat 0): grouped SBR passes P0-P3 for both seats and beats the hand-written exploit at full leak in both (+1.70 vs +0.75, +3.13 vs +1.98); per-state SBR passes seat 0 only marginally (51%) and fails seat 1 (16%). Neither detects the 0.1 / 0.3 leaks at 1,000 validation deals (per-run se ~0.35-0.39; the reference does not gain there either).

Decision (day53): grouped SBR (`coarse`) replaces per-state SBR in `scripts/evaluate_checkpoint.py` (report version 2). The day46-48 v1 / v2 reports (version 1) remain valid for every section except SBR. No-leak grouped gain on v1 at 300 response deals: seat 0 +0.51 ± 0.36, seat 1 +0.36 ± 0.38 (not significant individually); this is the first plausible lower-bound reading for v1, pending the grouped budget curve.

## A2 grouped SBR budget curve, v1 (day54)

`python -m scripts.inspect_sbr_budget checkpoints/production_v1.chk.gz --grouping coarse` (user's laptop, day53 code; budgets 100/300/1,000, 3 repeats, validation 1,000, sweeps <= 3, seed 2027). No leak planted.

| Response deals | Seat 0 gain (sd) | Seat 1 gain (sd) | Mean over seats | Fallback | Policy keys | Time per run |
|---|---|---|---|---|---|---|
| 100 | +0.13 (0.34) | -0.26 (0.26) | -0.07 | 8-14% | ~3.9k | ~110 s |
| 300 | +0.09 (0.35) | +0.16 (0.48) | +0.12 | 3-5% | ~6.7k | ~290 s |
| 1,000 | **+1.21 (0.79)** | **+1.36 (0.35)** | **+1.28** | 0.5-1% | ~9.9k | ~780-930 s |

Per-run gain se 0.36-0.40 throughout.

Reading:
- Confirmed: at 1,000 response deals all 6 runs are positive (+0.45 to +2.02) on held-out validation deals. **v1 is exploitable by at least ~1.3 chips per deal per seat (~0.64 BB/hand, ~640 mbb/hand).** This is a lower bound; the gain is still rising with the budget, so the true value is higher.
- Confirmed: grouped SBR has no power at 100 deals (the previous standard preset) and little at 300. The standard preset now uses 1,000 response deals x 2 repeats per seat.
- Confirmed: no significantly negative gain at any budget (validity, P3).
- Measurement bug (script only, fixed day54): in grouped mode the "sample" probe looked up learned actions by raw state instead of group key, so it never found one and played the profile against itself; that column (mean about -0.04 over 18 runs) is a noise check, not a fallback comparison. The "visits/state" column counted states, not groups. The production gains above are unaffected.
- Because the lower bound grows with the response budget, SBR numbers are comparable only at the same preset.

## A2 benchmark reports, report v2 (day55)

`python -m scripts.evaluate_checkpoint <checkpoint>` (user's laptop, Windows 11, Python 3.12.9, preset standard, seed 2027, grouped SBR 1,000 response deals x 2 repeats per seat).

| Metric | v1 `production_v1` | v2 `production_v2_maxdraw5` |
|---|---|---|
| Gates v1 verdict | FAIL (Q1, Q3) | FAIL (Q1, Q2, Q3) |
| **Grouped SBR lower bound, mean over seats** | **+1.57 chips/deal** (4 runs +1.14 to +2.02, per-run se ~0.37) | **+2.47 chips/deal** (4 runs +2.11 to +2.80, per-run se ~0.47) |
| SBR fallback share | 0.3-1.4% | 1.0-1.2% |
| Policy keys learned per run | ~9.5-10k | ~60-66k |
| SBR time (4 runs) | 1,395 s | 10,841 s |
| Total time / peak RSS | ~26 min / 1.98 GB | ~3.1 h / 8.14 GB |

Reading:
- Confirmed: **reproducible across platforms.** The new v1 report (Windows, Python 3.12.9) is identical to the day46 report (Linux container, Python 3.13.17) in every section except SBR (checkpoint, setup, static, coverage, button-1 diagnostic, baselines, current_vs_average compared as JSON). The v2 summary numbers outside SBR also match the day46 v2 report. The four v1 SBR gains equal the same-seed runs of the grouped budget curve exactly.
- Confirmed: both checkpoints are clearly exploitable; every SBR run is positive and far above its se. v2's lower bound (+2.47) is higher than v1's (+1.57), but they are different games (max_draw 5 vs 1), so the numbers are not a like-for-like ranking.
- v2 needs ~3 h and 8 GB for a standard report on the laptop; SBR is 95% of that.

## B2 draw-decision analysis (day57-59)

`python -m scripts.inspect_draw_decisions <checkpoint>` (20,000 self-play deals, seed 2027, same deals as the benchmark coverage section). Avoidable mistakes = breaking a made 7-low or keeping a pair when the state has an action free of it.

| | v1 (`max_draw=1`, 6 draw actions) | v2 (`max_draw=5`, 32 draw actions) |
|---|---|---|
| Draw decisions | 30,086 | 30,168 |
| Avoidable mistake probability, all / trained | 15.1% / 8.5% | 11.5% / 4.0% |
| Missing + near-uniform share of draw decisions | 27% | 53% |
| Expected cards drawn, trained (uniform) | 0.76 (0.83) | 2.35 (2.50) |
| Made 8 / 9, trained, expected cards drawn | 0.51 | 2.27 |

Reading:
- Confirmed: the discard mapping and draw_count encoding are correct (`tests/test_draw_mapping_properties.py`).
- Confirmed: draw quality is dominated by under-training. In v2 even "trained" states (not within 1e-6 of uniform) are close to uniform: made 8 / 9 hands, which should mostly stand pat, draw 2.27 cards on average.
- The 1e-6 near-uniform test (A2 Q3) understates how untrained a checkpoint is; a distance-from-uniform metric is proposed to A2.
- v1 and v2 mistake rates are not comparable (different action sets).
- Details and proposals: `docs/proposals/B2-draw-analysis.md`.

## C1 resumable training, step 1 verification (day59)

`save_training_checkpoint.py --state-output / --resume` (training state file, `solver/training_run.py`; v3 checkpoint unchanged). Windows, Python 3.12.

| Check | Config | Result |
|---|---|---|
| Resume = uninterrupted (cross-process) | bucket, `max_draw=5`, fast, seed 42, 30 + 30 vs 60 | 13,209 nodes, identical sha256 node fingerprint |
| Resume = uninterrupted (tests) | exact / sequential, exact / fixed, bucket / `max_draw=5`; 4 -> 7 -> 10 vs 10; RSS-guard stop at 2 -> 6 vs 6 | identical fingerprints and checkpoints |
| No new flags, before vs after the change | bucket / `max_draw=5` / fast / 40 iters; exact / `max_draw=1` / full / fixed seed 7 / 30 iters | identical strategies (8,916 / 1,882); metadata differs only in `created_at_utc` |
| Full test suite | | 874 passed |


T5 (day60, laptop): `full`, bucket, `max_draw=5`, seed 42, 2,000 iterations, batch 500, RSS guard off.

| Item | Value |
|---|---|
| Nodes at 500 / 1,000 / 1,500 / 2,000 | 213,501 / 356,412 / 471,899 / 562,244 |
| Wall time | 3,063 s (batch 4 took 1,010 s vs ~620-675 s for batches 1-3; not investigated) |
| File sizes | `.chk.gz` 5.6 MB, `.state.gz` 16.4 MB |
| Stored `peak_rss_gb` (read before the state write) | 1.42 GB at 2,000 |
| Reload of the 2k state, then save both files | load 7.0 s, RSS 1.05 GB; checkpoint save 18.9 s, peak 1.535 GB; state save 13.8 s, peak unchanged |

Reading: confirmed that saving the state does not raise the peak above the checkpoint save, so the 5-7 GiB concern in `docs/C1_DESIGN.md` 2.5 is refuted. The stored peak missed the state write itself; the script now also prints the peak after each state save.

## C1 first library solution, 8k (day63)

`python -m scripts.solve_library train hu_d5_full_bucket_s20 --until 8000` on the laptop: `full`, bucket, `max_draw=5`, seed 42 sequential, batch 500, RSS guard 10 GB. One segment, no interruption.

| Item | Value |
|---|---|
| Nodes at 500 / 2,000 / 4,000 / 8,000 | 213,501 / 562,244 / 800,762 / 1,068,645 |
| Wall time | 27,003 s (~7.5 h); 1,420-1,790 s per 500-iteration batch |
| RSS | 1.39 GB while training; peak 2.88 GB in the last batch (checkpoint + state save) |
| Files | checkpoint 13.2 MB, state 42.3 MB |

Reading:
- Confirmed: the 8k checkpoint has the same 1,068,645 strategies as `production_v2_maxdraw5.chk.gz`, all values identical; metadata differs only in `created_at_utc`. The library pipeline reproduces the v2 training exactly.
- Confirmed: node counts for the first 2,000 iterations match T5.
- Inference: the 8k standard evaluation will reproduce the v2 report (FAIL: Q1, Q2, Q3, Q6), since the benchmark is deterministic.
- Not explained: the first 2,000 iterations took 6,200 s vs 3,063 s in T5 with identical node counts. Hypothesis: laptop power mode, thermals or other load; the training loop did not change between the two runs.
