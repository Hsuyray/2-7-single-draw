from time import perf_counter

from solver.information_state import (
    AbstractionMode,
)
from solver.starting_range_cache import (
    StartingRangeCache,
)


def precompute(
    abstraction: AbstractionMode,
) -> None:
    cache = StartingRangeCache()

    print(
        f"Building {abstraction} "
        "starting range..."
    )

    start = perf_counter()

    starting_range = (
        cache.load_or_build(
            abstraction
        )
    )

    elapsed = (
        perf_counter()
        - start
    )

    print(
        f"Done: {abstraction}"
    )

    print(
        "Canonical keys: "
        f"{starting_range.hand_count:,}"
    )

    print(
        "Raw combination weight: "
        f"{starting_range.total_weight:,.0f}"
    )

    print(
        f"Elapsed: {elapsed:.2f}s"
    )

    print()


def main() -> None:
    precompute(
        "exact"
    )

    precompute(
        "bucket"
    )


if __name__ == "__main__":
    main()