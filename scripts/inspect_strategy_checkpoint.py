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


def main() -> None:
    args = parse_args()

    loaded = load_strategy_checkpoint(
        args.checkpoint
    )

    metadata = loaded.metadata
    strategy_index = (
        loaded.strategy_index
    )

    public_nodes = (
        strategy_index.public_nodes()
    )

    print(
        "Strategy checkpoint"
    )

    print(
        f"  file: "
        f"{args.checkpoint.resolve()}"
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
        f"{metadata.completed_iterations}"
    )

    print(
        f"  max draw: "
        f"{metadata.max_draw}"
    )

    print(
        f"  draw actions: "
        f"{metadata.draw_action_mode}"
    )

    print(
        f"  raise sizes: "
        f"{metadata.raise_sizes}"
    )

    print(
        f"  information states: "
        f"{loaded.strategy_count}"
    )

    print(
        f"  public nodes: "
        f"{len(public_nodes)}"
    )


if __name__ == "__main__":
    main()