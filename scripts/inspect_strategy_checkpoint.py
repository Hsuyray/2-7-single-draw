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


from solver.strategy_checkpoint import (  # noqa: E402
    LoadedStrategyCheckpoint,
    load_strategy_checkpoint,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a saved 2-7 Single Draw "
            "strategy checkpoint."
        )
    )

    parser.add_argument(
        "checkpoint",
        type=Path,
        help=(
            "Path to the compressed strategy "
            "checkpoint."
        ),
    )

    return parser.parse_args()


def print_betting_metadata(
    loaded: LoadedStrategyCheckpoint,
) -> None:
    metadata = loaded.metadata

    print(
        f"  bet sizing mode: "
        f"{metadata.bet_sizing_mode}"
    )

    print(
        f"  raise sizes: "
        f"{metadata.raise_sizes}"
    )

    if (
        metadata.bet_sizing_mode
        == "policy"
    ):
        print(
            f"  pot fractions: "
            f"{metadata.bet_pot_fractions}"
        )

        print(
            f"  include all-in: "
            f"{metadata.bet_include_all_in}"
        )

        print(
            f"  all-in threshold: "
            f"{metadata.bet_all_in_threshold}"
        )

        print(
            f"  chip increment: "
            f"{metadata.bet_chip_increment}"
        )


def print_checkpoint_summary(
    loaded: LoadedStrategyCheckpoint,
    *,
    checkpoint_path: Path,
) -> None:
    metadata = loaded.metadata

    strategy_index = (
        loaded.strategy_index
    )

    public_nodes = (
        strategy_index.public_nodes()
    )

    file_size_bytes = (
        checkpoint_path.stat().st_size
    )

    file_size_kb = (
        file_size_bytes
        / 1024
    )

    print(
        "Strategy checkpoint"
    )

    print(
        f"  file: "
        f"{checkpoint_path.resolve()}"
    )

    print(
        f"  file size: "
        f"{file_size_kb:,.2f} KB"
    )

    print(
        f"  format version: "
        f"{metadata.format_version}"
    )

    print(
        f"  game: "
        f"{metadata.game}"
    )

    print(
        f"  created: "
        f"{metadata.created_at_utc}"
    )

    print(
        f"  abstraction: "
        f"{metadata.abstraction}"
    )

    print(
        f"  iterations: "
        f"{metadata.completed_iterations:,}"
    )

    print(
        f"  max draw: "
        f"{metadata.max_draw}"
    )

    print(
        f"  draw actions: "
        f"{metadata.draw_action_mode}"
    )

    print_betting_metadata(
        loaded
    )

    print(
        f"  information states: "
        f"{loaded.strategy_count:,}"
    )

    print(
        f"  public nodes: "
        f"{len(public_nodes):,}"
    )


def main() -> None:
    args = parse_args()

    checkpoint_path = (
        args.checkpoint
    )

    loaded = (
        load_strategy_checkpoint(
            checkpoint_path
        )
    )

    print_checkpoint_summary(
        loaded,
        checkpoint_path=(
            checkpoint_path
        ),
    )


if __name__ == "__main__":
    main()