"""
Train one CFRTrainer variant on the day74 experiment's deal sequence
(docs/proposals/CFR-linear-weighting.md, day75).

Same game, deal seeds (seed + 1, seed + 2, ...) and trainer settings
as scripts/compare_average_modes.py, so a checkpoint from this script
with --average-mode simple --iteration-weighting uniform has the same
strategies as that experiment's "simple" checkpoint, and other
variants differ from it in one setting only.

    python -m scripts.train_weighting_variant --iterations 2000,8000 \
        --average-mode simple --iteration-weighting linear \
        --out-dir experiments/linear_cfr --label lcfr

Writes <out-dir>/<label>__<iters>.chk.gz per milestone and
<label>__summary.json.
"""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.bet_sizing import (  # noqa: E402
    FAST_BET_SIZING,
    FULL_BET_SIZING,
)
from solver.cfr_trainer import (  # noqa: E402
    AVERAGE_MODES,
    ITERATION_WEIGHTINGS,
    CFRTrainer,
)
from solver.game_state import GameConfig  # noqa: E402
from solver.single_draw_game import SingleDrawGame  # noqa: E402


def build_trainer(args: argparse.Namespace) -> tuple[CFRTrainer, GameConfig]:
    config = GameConfig(
        player_count=2,
        starting_stack=args.stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=None,
        bet_sizing_policy=(
            FAST_BET_SIZING if args.bet_sizing == "fast" else FULL_BET_SIZING
        ),
        abstraction=args.abstraction,
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=args.seed,
        average_mode=args.average_mode,
        iteration_weighting=args.iteration_weighting,
        game_config=config,
    )

    return trainer, config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--iterations", required=True,
                        help="Comma-separated milestones, e.g. 2000,8000")
    parser.add_argument("--max-draw", type=int, default=5)
    parser.add_argument("--abstraction", default="bucket",
                        choices=("bucket", "exact"))
    parser.add_argument("--bet-sizing", default="fast",
                        choices=("fast", "full"))
    parser.add_argument("--stack", type=float, default=20.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--average-mode", default="simple",
                        choices=AVERAGE_MODES)
    parser.add_argument("--iteration-weighting", default="linear",
                        choices=ITERATION_WEIGHTINGS)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--label", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    milestones = sorted({int(x) for x in args.iterations.split(",")})
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    trainer, config = build_trainer(args)

    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter
        counter += 1
        return SingleDrawGame(
            config=config,
            button_seat=0,
            deck_seed=args.seed + counter,
        )

    summary = {"arguments": vars(args), "milestones": []}
    done = 0
    started = perf_counter()

    for milestone in milestones:
        trainer.train(factory, iterations=milestone - done)
        done = milestone

        trainer.save_checkpoint(
            out_dir / f"{args.label}__{milestone:06d}.chk.gz"
        )

        record = {
            "iterations": milestone,
            "nodes": len(trainer.node_store),
            "elapsed_s": round(perf_counter() - started, 1),
        }
        summary["milestones"].append(record)
        print(json.dumps(record), flush=True)

        (out_dir / f"{args.label}__summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
