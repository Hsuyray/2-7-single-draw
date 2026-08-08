import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path
import sys
from time import perf_counter


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from solver.cards import (  # noqa: E402
    Card,
)
from solver.hand import (  # noqa: E402
    Hand,
)
from solver.made_hand_bucket import (  # noqa: E402
    made_hand_bucket,
)


RANKS = "23456789TJQKA"
SUITS = "shdc"

TOTAL_FIVE_CARD_HANDS = 2_598_960


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate the complete 52-card "
            "five-card hand universe and "
            "analyze deterministic postdraw "
            "strength buckets."
        )
    )

    parser.add_argument(
        "--bucket-counts",
        type=str,
        default=(
            "32,64,128,256,512,1024"
        ),
    )

    return parser.parse_args()


def parse_bucket_counts(
    raw: str,
) -> tuple[int, ...]:
    try:
        values = tuple(
            int(
                value.strip()
            )
            for value in raw.split(",")
            if value.strip()
        )
    except ValueError as error:
        raise ValueError(
            "Bucket counts must be "
            "comma-separated integers."
        ) from error

    if not values:
        raise ValueError(
            "At least one bucket count "
            "is required."
        )

    if any(
        value <= 0
        for value in values
    ):
        raise ValueError(
            "Bucket counts must be positive."
        )

    return tuple(
        sorted(
            set(
                values
            )
        )
    )


def standard_deck() -> tuple[
    Card,
    ...,
]:
    return tuple(
        Card(
            rank=rank,
            suit=suit,
        )
        for rank in RANKS
        for suit in SUITS
    )


def collect_score_frequencies() -> Counter:
    deck = standard_deck()

    frequencies = Counter()

    for cards in combinations(
        deck,
        5,
    ):
        hand = Hand(
            cards=tuple(
                cards
            )
        )

        bucket = (
            made_hand_bucket(
                hand
            )
        )

        frequencies[
            bucket.score
        ] += 1

    return frequencies


def category_distribution(
    frequencies: Counter,
) -> Counter:
    result = Counter()

    for (
        score,
        count,
    ) in frequencies.items():
        if not score:
            continue

        result[
            score[0]
        ] += count

    return result


def category_score_counts(
    frequencies: Counter,
) -> Counter:
    result = Counter()

    for score in frequencies:
        if not score:
            continue

        result[
            score[0]
        ] += 1

    return result


def equal_score_bucket_map(
    *,
    scores: tuple[
        tuple[int, ...],
        ...,
    ],
    bucket_count: int,
) -> dict[
    tuple[int, ...],
    int,
]:
    total_scores = len(
        scores
    )

    result = {}

    for (
        index,
        score,
    ) in enumerate(
        scores
    ):
        bucket_id = (
            index
            * bucket_count
            // total_scores
        )

        result[
            score
        ] = min(
            bucket_id,
            bucket_count - 1,
        )

    return result


def equal_mass_bucket_map(
    *,
    frequencies: Counter,
    bucket_count: int,
) -> dict[
    tuple[int, ...],
    int,
]:
    ordered_scores = tuple(
        sorted(
            frequencies
        )
    )

    total_mass = sum(
        frequencies.values()
    )

    result = {}

    cumulative_mass = 0

    for score in ordered_scores:
        count = frequencies[
            score
        ]

        midpoint = (
            cumulative_mass
            + count / 2
        )

        bucket_id = int(
            midpoint
            * bucket_count
            / total_mass
        )

        result[
            score
        ] = min(
            bucket_id,
            bucket_count - 1,
        )

        cumulative_mass += count

    return result


def bucket_statistics(
    *,
    frequencies: Counter,
    mapping: dict[
        tuple[int, ...],
        int,
    ],
) -> dict:
    hand_mass = Counter()
    score_mass = Counter()
    categories = {}

    for (
        score,
        count,
    ) in frequencies.items():
        bucket_id = mapping[
            score
        ]

        hand_mass[
            bucket_id
        ] += count

        score_mass[
            bucket_id
        ] += 1

        if score:
            categories.setdefault(
                bucket_id,
                set(),
            ).add(
                score[0]
            )

    hand_values = tuple(
        hand_mass.values()
    )

    score_values = tuple(
        score_mass.values()
    )

    mixed_category_buckets = sum(
        len(
            categories.get(
                bucket_id,
                set(),
            )
        )
        > 1
        for bucket_id
        in hand_mass
    )

    return {
        "used_buckets": len(
            hand_mass
        ),
        "min_hands": min(
            hand_values,
            default=0,
        ),
        "max_hands": max(
            hand_values,
            default=0,
        ),
        "avg_hands": (
            sum(
                hand_values
            )
            / len(
                hand_values
            )
            if hand_values
            else 0.0
        ),
        "min_scores": min(
            score_values,
            default=0,
        ),
        "max_scores": max(
            score_values,
            default=0,
        ),
        "avg_scores": (
            sum(
                score_values
            )
            / len(
                score_values
            )
            if score_values
            else 0.0
        ),
        "mixed_category_buckets": (
            mixed_category_buckets
        ),
    }


def print_bucket_statistics(
    *,
    label: str,
    bucket_count: int,
    statistics: dict,
) -> None:
    print(
        f"  {label}"
    )

    print(
        f"    target buckets: "
        f"{bucket_count:,}"
    )

    print(
        f"    used buckets: "
        f"{statistics['used_buckets']:,}"
    )

    print(
        f"    avg hands/bucket: "
        f"{statistics['avg_hands']:,.2f}"
    )

    print(
        f"    min hands/bucket: "
        f"{statistics['min_hands']:,}"
    )

    print(
        f"    max hands/bucket: "
        f"{statistics['max_hands']:,}"
    )

    print(
        f"    avg scores/bucket: "
        f"{statistics['avg_scores']:.2f}"
    )

    print(
        f"    min scores/bucket: "
        f"{statistics['min_scores']:,}"
    )

    print(
        f"    max scores/bucket: "
        f"{statistics['max_scores']:,}"
    )

    print(
        f"    mixed-category buckets: "
        f"{statistics['mixed_category_buckets']:,}"
    )


def main() -> None:
    args = parse_args()

    bucket_counts = (
        parse_bucket_counts(
            args.bucket_counts
        )
    )

    print(
        "Full postdraw hand-universe "
        "diagnostic"
    )

    print(
        f"  expected five-card hands: "
        f"{TOTAL_FIVE_CARD_HANDS:,}"
    )

    print(
        f"  candidate bucket counts: "
        f"{bucket_counts}"
    )

    print()
    print(
        "Enumerating all five-card hands..."
    )

    started_at = (
        perf_counter()
    )

    frequencies = (
        collect_score_frequencies()
    )

    elapsed = (
        perf_counter()
        - started_at
    )

    total_hands = sum(
        frequencies.values()
    )

    ordered_scores = tuple(
        sorted(
            frequencies
        )
    )

    print()
    print(
        "Universe summary"
    )

    print(
        f"  enumerated hands: "
        f"{total_hands:,}"
    )

    print(
        f"  unique scores: "
        f"{len(ordered_scores):,}"
    )

    print(
        f"  elapsed: "
        f"{elapsed:.3f}s"
    )

    if (
        total_hands
        != TOTAL_FIVE_CARD_HANDS
    ):
        raise RuntimeError(
            "Unexpected five-card hand "
            "universe size."
        )

    hand_categories = (
        category_distribution(
            frequencies
        )
    )

    score_categories = (
        category_score_counts(
            frequencies
        )
    )

    print()
    print(
        "Category distribution"
    )

    for category in sorted(
        hand_categories
    ):
        hand_count = (
            hand_categories[
                category
            ]
        )

        score_count = (
            score_categories[
                category
            ]
        )

        print(
            f"  category {category}: "
            f"{hand_count:,} hands, "
            f"{score_count:,} scores"
        )

    print()
    print(
        "Bucket comparison"
    )

    for bucket_count in (
        bucket_counts
    ):
        print()
        print(
            "=" * 64
        )

        print(
            f"{bucket_count:,} BUCKETS"
        )

        score_mapping = (
            equal_score_bucket_map(
                scores=ordered_scores,
                bucket_count=(
                    bucket_count
                ),
            )
        )

        score_statistics = (
            bucket_statistics(
                frequencies=(
                    frequencies
                ),
                mapping=(
                    score_mapping
                ),
            )
        )

        print_bucket_statistics(
            label=(
                "equal-score-count"
            ),
            bucket_count=(
                bucket_count
            ),
            statistics=(
                score_statistics
            ),
        )

        mass_mapping = (
            equal_mass_bucket_map(
                frequencies=(
                    frequencies
                ),
                bucket_count=(
                    bucket_count
                ),
            )
        )

        mass_statistics = (
            bucket_statistics(
                frequencies=(
                    frequencies
                ),
                mapping=(
                    mass_mapping
                ),
            )
        )

        print()

        print_bucket_statistics(
            label=(
                "equal-combination-mass"
            ),
            bucket_count=(
                bucket_count
            ),
            statistics=(
                mass_statistics
            ),
        )


if __name__ == "__main__":
    main()