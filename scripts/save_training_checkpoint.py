import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from solver.cfr_trainer import (  # noqa: E402
    CFRTrainer,
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train the heads-up 2-7 Single "
            "Draw CFR prototype and save an "
            "average-strategy checkpoint."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help=(
            "Number of CFR training "
            "iterations."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path("checkpoints")
            / "strategy.chk.gz"
        ),
        help=(
            "Checkpoint output path."
        ),
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
        help=(
            "Starting stack in chips."
        ),
    )

    parser.add_argument(
        "--max-draw",
        type=int,
        default=2,
        choices=range(
            0,
            6,
        ),
        help=(
            "Maximum number of cards that "
            "may be discarded."
        ),
    )

    parser.add_argument(
        "--traversal-mode",
        choices=(
            "full",
            "external_sampling",
        ),
        default="external_sampling",
        help=(
            "CFR traversal algorithm."
        ),
    )

    parser.add_argument(
        "--draw-action-mode",
        choices=(
            "full",
            "candidate",
        ),
        default="candidate",
        help=(
            "Draw action generation mode."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help=(
            "Base random seed."
        ),
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.iterations <= 0:
        raise ValueError(
            "Iterations must be positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Starting stack must be "
            "positive."
        )

    if args.max_draw < 0:
        raise ValueError(
            "Max draw cannot be negative."
        )

    if args.max_draw > 5:
        raise ValueError(
            "Max draw cannot exceed five."
        )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    game_counter = 0

    def game_factory() -> SingleDrawGame:
        nonlocal game_counter

        game_seed = args.seed

        game_counter += 1

        return SingleDrawGame(
            config=GameConfig(
                player_count=2,
                starting_stack=args.stack,
                small_blind=1.0,
                big_blind=2.0,
                big_blind_ante=1.5,
            ),
            button_seat=0,
            deck_seed=game_seed,
        )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=(),
        abstraction="exact",
        traversal_mode=(
            args.traversal_mode
        ),
        draw_action_mode=(
            args.draw_action_mode
        ),
        random_seed=args.seed,
    )

    print(
        "Training started:"
    )

    print(
        f"  iterations: "
        f"{args.iterations}"
    )

    print(
        f"  stack: "
        f"{args.stack}"
    )

    print(
        f"  traversal: "
        f"{args.traversal_mode}"
    )

    print(
        f"  draw actions: "
        f"{args.draw_action_mode}"
    )

    print(
        f"  max draw: "
        f"{args.max_draw}"
    )

    print(
        f"  seed: "
        f"{args.seed}"
    )

    trainer.train(
        game_factory,
        iterations=args.iterations,
    )

    checkpoint_path = (
        trainer.save_checkpoint(
            args.output
        )
    )

    print(
        "Training completed:"
    )

    print(
        f"  iterations: "
        f"{trainer.completed_iterations}"
    )

    print(
        f"  CFR nodes: "
        f"{len(trainer.node_store)}"
    )

    print(
        f"  checkpoint: "
        f"{checkpoint_path.resolve()}"
    )


if __name__ == "__main__":
    main()