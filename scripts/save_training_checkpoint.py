import argparse
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


import psutil  # noqa: E402

from solver.bet_sizing import (  # noqa: E402
    FAST_BET_SIZING,
    FULL_BET_SIZING,
    BetSizingPolicy,
)
from solver.cfr_trainer import (  # noqa: E402
    CFRTrainer,
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.information_state import (  # noqa: E402
    AbstractionMode,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


DEFAULT_BATCH_SIZE = 500

DEFAULT_MIN_FREE_MEMORY_GB = 2.0


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
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path("checkpoints")
            / "strategy.chk.gz"
        ),
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--max-draw",
        type=int,
        default=2,
        choices=range(
            0,
            6,
        ),
    )

    parser.add_argument(
        "--abstraction",
        choices=(
            "exact",
            "bucket",
        ),
        default="exact",
    )

    parser.add_argument(
        "--traversal-mode",
        choices=(
            "full",
            "external_sampling",
        ),
        default="external_sampling",
    )

    parser.add_argument(
        "--draw-action-mode",
        choices=(
            "auto",
            "full",
            "candidate",
        ),
        default="auto",
    )

    parser.add_argument(
        "--bet-sizing",
        choices=(
            "none",
            "fast",
            "full",
        ),
        default="fast",
        help=(
            "none disables betting raises; "
            "fast uses 33/66/100/all-in; "
            "full uses the complete sizing "
            "abstraction."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--seed-mode",
        choices=(
            "fixed",
            "sequential",
        ),
        default="sequential",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=(
            "Number of iterations to run "
            "between memory checks and "
            "checkpoint saves."
        ),
    )

    parser.add_argument(
        "--min-free-memory-gb",
        type=float,
        default=(
            DEFAULT_MIN_FREE_MEMORY_GB
        ),
        help=(
            "Stop training and save if "
            "available system memory drops "
            "below this threshold, in GB."
        ),
    )

    parser.add_argument(
        "--checkpoint-every-batches",
        type=int,
        default=1,
        help=(
            "Save an intermediate checkpoint "
            "every N batches, in addition to "
            "the final save. Set to 0 to "
            "disable intermediate saves."
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
            "Starting stack must be positive."
        )

    if not (
        0
        <= args.max_draw
        <= 5
    ):
        raise ValueError(
            "Max draw must be between "
            "zero and five."
        )

    if (
        args.abstraction == "bucket"
        and args.draw_action_mode
        == "candidate"
    ):
        raise ValueError(
            "Bucket abstraction currently "
            "requires --draw-action-mode "
            "auto or full."
        )

    if args.batch_size <= 0:
        raise ValueError(
            "Batch size must be positive."
        )

    if args.min_free_memory_gb <= 0:
        raise ValueError(
            "Minimum free memory must be "
            "positive."
        )

    if args.checkpoint_every_batches < 0:
        raise ValueError(
            "Checkpoint-every-batches cannot "
            "be negative."
        )


def resolve_bet_sizing(
    mode: str,
) -> tuple[
    tuple[float, ...] | None,
    BetSizingPolicy | None,
]:
    if mode == "none":
        return (
            (),
            None,
        )

    if mode == "fast":
        return (
            None,
            FAST_BET_SIZING,
        )

    if mode == "full":
        return (
            None,
            FULL_BET_SIZING,
        )

    raise ValueError(
        "Unknown bet sizing mode."
    )


def available_memory_gb() -> float:
    return (
        psutil.virtual_memory().available
        / (1024 ** 3)
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    (
        raise_sizes,
        bet_sizing_policy,
    ) = resolve_bet_sizing(
        args.bet_sizing
    )

    shared_game_config = GameConfig(
        player_count=2,
        starting_stack=args.stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    game_counter = 0

    def game_factory() -> SingleDrawGame:
        nonlocal game_counter

        if args.seed_mode == "fixed":
            game_seed = args.seed
        else:
            game_seed = (
                args.seed
                + game_counter
            )

        game_counter += 1

        return SingleDrawGame(
            config=shared_game_config,
            button_seat=0,
            deck_seed=game_seed,
        )

    abstraction: AbstractionMode = (
        args.abstraction
    )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
        abstraction=abstraction,
        traversal_mode=(
            args.traversal_mode
        ),
        draw_action_mode=(
            args.draw_action_mode
        ),
        random_seed=args.seed,
        game_config=shared_game_config,
    )

    print(
        "Training started:"
    )

    print(
        f"  iterations: "
        f"{args.iterations:,}"
    )

    print(
        f"  stack: "
        f"{args.stack}"
    )

    print(
        f"  abstraction: "
        f"{args.abstraction}"
    )

    print(
        f"  traversal: "
        f"{args.traversal_mode}"
    )

    print(
        f"  bet sizing: "
        f"{args.bet_sizing}"
    )

    if bet_sizing_policy is not None:
        print(
            f"  pot fractions: "
            f"{bet_sizing_policy.pot_fractions}"
        )

        print(
            f"  include all-in: "
            f"{bet_sizing_policy.include_all_in}"
        )

    print(
        f"  draw action setting: "
        f"{args.draw_action_mode}"
    )

    print(
        f"  resolved draw actions: "
        f"{trainer.resolved_draw_action_mode}"
    )

    print(
        f"  max draw: "
        f"{args.max_draw}"
    )

    print(
        f"  seed: "
        f"{args.seed}"
    )

    print(
        f"  seed mode: "
        f"{args.seed_mode}"
    )

    print(
        f"  batch size: "
        f"{args.batch_size:,}"
    )

    print(
        f"  min free memory (GB): "
        f"{args.min_free_memory_gb}"
    )

    print(
        f"  checkpoint every N batches: "
        f"{args.checkpoint_every_batches}"
    )

    print()

    print(
        f"  starting free memory: "
        f"{available_memory_gb():.2f} GB"
    )

    print()

    remaining_iterations = args.iterations

    batch_number = 0

    stopped_early = False

    overall_start = time.perf_counter()

    while remaining_iterations > 0:
        batch_number += 1

        this_batch_size = min(
            args.batch_size,
            remaining_iterations,
        )

        batch_start = time.perf_counter()

        trainer.train(
            game_factory,
            iterations=this_batch_size,
        )

        batch_seconds = (
            time.perf_counter()
            - batch_start
        )

        remaining_iterations -= (
            this_batch_size
        )

        free_memory = (
            available_memory_gb()
        )

        elapsed_total = (
            time.perf_counter()
            - overall_start
        )

        print(
            f"Batch {batch_number}: "
            f"completed_iterations="
            f"{trainer.completed_iterations:,}, "
            f"CFR_nodes="
            f"{len(trainer.node_store):,}, "
            f"batch_seconds="
            f"{batch_seconds:.1f}, "
            f"elapsed_total="
            f"{elapsed_total:.1f}s, "
            f"free_memory="
            f"{free_memory:.2f}GB"
        )

        should_checkpoint = (
            args.checkpoint_every_batches
            > 0
            and batch_number
            % args.checkpoint_every_batches
            == 0
        )

        low_memory = (
            free_memory
            < args.min_free_memory_gb
        )

        if low_memory:
            print()

            print(
                "WARNING: free memory "
                f"({free_memory:.2f} GB) "
                "is below the safety "
                "threshold "
                f"({args.min_free_memory_gb} "
                "GB). Stopping training "
                "and saving now."
            )

            stopped_early = True

        if should_checkpoint or low_memory:
            checkpoint_path = (
                trainer.save_checkpoint(
                    args.output
                )
            )

            print(
                f"  Saved checkpoint "
                f"({trainer.completed_iterations:,} "
                f"iterations) to "
                f"{checkpoint_path.resolve()}"
            )

        if low_memory:
            break

    final_checkpoint_path = (
        trainer.save_checkpoint(
            args.output
        )
    )

    print()

    print(
        "Training completed"
        if not stopped_early
        else "Training stopped early "
        "(low memory)"
    )

    print(
        ":"
    )

    print(
        f"  iterations: "
        f"{trainer.completed_iterations:,}"
    )

    print(
        f"  CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  final free memory: "
        f"{available_memory_gb():.2f} GB"
    )

    print(
        f"  checkpoint: "
        f"{final_checkpoint_path.resolve()}"
    )


if __name__ == "__main__":
    main()