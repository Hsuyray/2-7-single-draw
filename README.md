# 2-7 Single Draw CFR solver

A Python solver for heads-up **2-7 (deuce-to-seven) Single Draw** using **Counterfactual Regret Minimization (CFR)**.

This is a computational game-theory project on an imperfect-information, extensive-form game. It is **not** a poker bot and **not** standard reinforcement learning: CFR minimises counterfactual regret at every information set and the **average** strategy approaches a Nash equilibrium. The goal is offline-solved strategies that can be saved as checkpoints and queried repeatedly (hand-level and range-level views).

Game flow: predraw betting -> draw -> postdraw betting. `max_draw` limits the number of cards a player may discard; full 2-7 Single Draw allows 0 to 5, so **`max_draw=5` is the only rules-complete setting**. The trainer (`solver/cfr_trainer.py`) currently supports heads-up games only.

## Setup (Windows PowerShell)

The code was developed on Python 3.12 (`.venv/pyvenv.cfg` records 3.12.9).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pytest psutil
```

`requirements.txt` is currently empty. `psutil` is required by `scripts/save_training_checkpoint.py` and `scripts/profile_memory.py`; `pytest` runs the tests. (A `.venv` is also committed to the repository; see `docs/AUDIT.md`.)

## Running

Run everything from the repository root **as modules**:

```powershell
python -m pytest tests -q
python -m scripts.save_training_checkpoint --help
python -m scripts.profile_memory --help
```

Training entry point: `scripts/save_training_checkpoint.py`. Its defaults are **not** the rules-complete configuration (`--max-draw` defaults to 2 and `--abstraction` to `exact`), so pass them explicitly, e.g.

```powershell
python -m scripts.save_training_checkpoint --max-draw 5 --abstraction bucket --bet-sizing fast --iterations 1000 --seed 42 --output checkpoints\example.chk.gz
```

Memory safety flags on that script:
- `--min-free-memory-gb` (default 2.0): stop and save when available *system* memory drops below this.
- `--max-rss-gb` (default 3.0, `0` disables): stop and save when this *process's* RSS exceeds the limit, checked every `--rss-check-every` iterations (default 100).

Checkpoints hold the **average strategy and metadata only** (format version 3). They do not include regrets, so training cannot be resumed from a checkpoint.

See `RUN_INSTRUCTIONS.md` for the exact order of commands for the current memory investigation.

## Repository layout

| Path | Contents |
|---|---|
| `solver/` | Game engine (`game_state.py`, `single_draw_game.py`, `draw.py`, `pots.py`, `terminal_utility.py`), information-state keys (`information_state.py`, `public_state.py`), hand abstractions (`draw_hand_bucket.py`, `postdraw_strength_bucket.py`, `hand_abstraction.py`), bet sizing (`bet_sizing.py`, `bet_sizing_profiles.py`), CFR (`cfr_trainer.py`, `cfr_node.py`, `node_store.py`), checkpoints (`strategy_checkpoint.py`, `strategy_index.py`), evaluation (`best_response.py`, `strategy_profile_evaluator.py`), lookup/browsing (`hand_strategy_resolver.py`, `strategy_browser.py`, `checkpoint_browser.py`), and `memory_guard.py` (process-RSS guard). |
| `scripts/` | Command-line entry points: training (`save_training_checkpoint.py`), memory profiling (`profile_memory.py`), and `inspect_*`, `evaluate_strategy_profile.py`, `query_strategy_checkpoint.py` diagnostics. |
| `tests/` | pytest suite (one file per module plus integration and regression tests). |
| `data/starting_ranges/` | Precomputed starting-range pickles. |
| `checkpoints/` | Saved strategy checkpoints (`*.chk.gz`). |
| `docs/` | Design and project documents (below). |

## Documentation

- `docs/game_rules.md` - game rules.
- `docs/architecture_v1.md` - original architecture and product goals.
- `docs/AUDIT.md` - read-only audit of the repository: entry point, storage of nodes/regrets/keys, test coverage for fixed bugs, tracked files.
- `docs/EXPERIMENT_LOG.md` - historical results and the table for new runs.
- `docs/PARALLEL_TRAINING_DESIGN.md` - design discussion for multi-core CFR (no code).
- `RUN_INSTRUCTIONS.md` - commands to run, in order, and how to read the output.
