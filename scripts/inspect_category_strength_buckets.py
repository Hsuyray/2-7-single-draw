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


from solver.cards import Card  # noqa: E402
from solver.hand import Hand  # noqa: E402
from solver.made_hand_bucket import (  # noqa: E402
    made_hand_bucket,
)


RANKS = "23456789TJQKA"
SUITS = "shdc"

TOTAL_FIVE_CARD_HANDS = 2_598_960


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze deterministic "
            "category-preserving equal-mass "
            "postdraw strength buckets."
        )
    )

    parser.add_argument(
        "--bucket-counts",
        type=str,
        default="64,128,256",
    )

    return parser.parse_args()


def parse_bucket_counts(
    raw: str,
) -> tuple[int, ...]:
    try:
        counts = tuple(
            int(value.strip())
            for value in raw.split(",")
            if value.strip()
        )
    except ValueError as error:
        raise ValueError(
            "Bucket counts must be "
            "comma-separated integers."
        ) from error

    if not counts:
        raise ValueError(
            "At least one bucket count "
            "is required."
        )

    if any(
        count <= 0
        for count in counts
    ):
        raise ValueError(
            "Bucket counts must be positive."
        )

    return tuple(
        sorted(
            set(
                counts
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
    frequencies = Counter()

    deck = standard_deck()

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


def frequencies_by_category(
    frequencies: Counter,
) -> dict[
    int,
    Counter,
]:
    result: dict[
        int,
        Counter,
    ] = {}

    for (
        score,
        count,
    ) in frequencies.items():
        if not score:
            continue

        category = score[0]

        result.setdefault(
            category,
            Counter(),
        )[
            score
        ] = count

    return result


def allocate_category_buckets(
    *,
    category_frequencies: dict[
        int,
        Counter,
    ],
    total_bucket_count: int,
) -> dict[
    int,
    int,
]:
    categories = tuple(
        sorted(
            category_frequencies
        )
    )

    if total_bucket_count < len(
        categories
    ):
        raise ValueError(
            "Total bucket count must be "
            "at least the number of hand "
            "categories."
        )

    total_hands = sum(
        sum(
            frequencies.values()
        )
        for frequencies in (
            category_frequencies.values()
        )
    )

    allocation = {
        category: 1
        for category in categories
    }

    remaining = (
        total_bucket_count
        - len(
            categories
        )
    )

    if remaining <= 0:
        return allocation

    exact_extra = {}

    for category in categories:
        category_hands = sum(
            category_frequencies[
                category
            ].values()
        )

        exact_extra[
            category
        ] = (
            remaining
            * category_hands
            / total_hands
        )

    assigned_extra = 0

    for category in categories:
        extra = int(
            exact_extra[
                category
            ]
        )

        allocation[
            category
        ] += extra

        assigned_extra += extra

    leftovers = (
        remaining
        - assigned_extra
    )

    remainder_order = sorted(
        categories,
        key=lambda category: (
            exact_extra[
                category
            ]
            - int(
                exact_extra[
                    category
                ]
            )
        ),
        reverse=True,
    )

    for category in (
        remainder_order[
            :leftovers
        ]
    ):
        allocation[
            category
        ] += 1

    return allocation


def build_category_equal_mass_mapping(
    *,
    category_frequencies: dict[
        int,
        Counter,
    ],
    allocation: dict[
        int,
        int,
    ],
) -> dict[
    tuple[int, ...],
    int,
]:
    mapping = {}

    bucket_offset = 0

    for category in sorted(
        category_frequencies
    ):
        frequencies = (
            category_frequencies[
                category
            ]
        )

        bucket_count = (
            allocation[
                category
            ]
        )

        ordered_scores = tuple(
            sorted(
                frequencies
            )
        )

        total_mass = sum(
            frequencies.values()
        )

        cumulative_mass = 0

        for score in ordered_scores:
            score_mass = (
                frequencies[
                    score
                ]
            )

            midpoint = (
                cumulative_mass
                + score_mass / 2
            )

            local_bucket = int(
                midpoint
                * bucket_count
                / total_mass
            )

            local_bucket = min(
                local_bucket,
                bucket_count - 1,
            )

            mapping[
                score
            ] = (
                bucket_offset
                + local_bucket
            )

            cumulative_mass += (
                score_mass
            )

        bucket_offset += (
            bucket_count
        )

    return mapping


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
    category_sets = {}

    for (
        score,
        count,
    ) in frequencies.items():
        bucket_id = (
            mapping[
                score
            ]
        )

        hand_mass[
            bucket_id
        ] += count

        score_mass[
            bucket_id
        ] += 1

        category_sets.setdefault(
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

    mixed = sum(
        len(categories) > 1
        for categories in (
            category_sets.values()
        )
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
            mixed
        ),
        "hand_mass": hand_mass,
    }


def print_category_allocation(
    *,
    category_frequencies: dict[
        int,
        Counter,
    ],
    allocation: dict[
        int,
        int,
    ],
) -> None:
    print(
        "  category allocation:"
    )

    for category in sorted(
        category_frequencies
    ):
        hand_count = sum(
            category_frequencies[
                category
            ].values()
        )

        score_count = len(
            category_frequencies[
                category
            ]
        )

        print(
            f"    category {category}: "
            f"{allocation[category]:>3} buckets, "
            f"{hand_count:>9,} hands, "
            f"{score_count:>5,} scores"
        )


def print_statistics(
    *,
    bucket_count: int,
    statistics: dict,
) -> None:
    print(
        f"  used buckets: "
        f"{statistics['used_buckets']:,}"
    )

    print(
        f"  avg hands/bucket: "
        f"{statistics['avg_hands']:,.2f}"
    )

    print(
        f"  min hands/bucket: "
        f"{statistics['min_hands']:,}"
    )

    print(
        f"  max hands/bucket: "
        f"{statistics['max_hands']:,}"
    )

    print(
        f"  avg scores/bucket: "
        f"{statistics['avg_scores']:.2f}"
    )

    print(
        f"  min scores/bucket: "
        f"{statistics['min_scores']:,}"
    )

    print(
        f"  max scores/bucket: "
        f"{statistics['max_scores']:,}"
    )

    print(
        f"  mixed-category buckets: "
        f"{statistics['mixed_category_buckets']:,}"
    )

    target_mass = (
        TOTAL_FIVE_CARD_HANDS
        / bucket_count
    )

    print(
        f"  global target mass: "
        f"{target_mass:,.2f}"
    )


def main() -> None:
    args = parse_args()

    bucket_counts = (
        parse_bucket_counts(
            args.bucket_counts
        )
    )

    print(
        "Category-preserving postdraw "
        "strength-bucket diagnostic"
    )

    print(
        f"  expected hands: "
        f"{TOTAL_FIVE_CARD_HANDS:,}"
    )

    print(
        f"  candidate buckets: "
        f"{bucket_counts}"
    )

    print()
    print(
        "Enumerating complete hand universe..."
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

    if (
        total_hands
        != TOTAL_FIVE_CARD_HANDS
    ):
        raise RuntimeError(
            "Unexpected five-card hand "
            "count."
        )

    category_frequencies = (
        frequencies_by_category(
            frequencies
        )
    )

    print()
    print(
        "Universe"
    )

    print(
        f"  hands: "
        f"{total_hands:,}"
    )

    print(
        f"  unique scores: "
        f"{len(frequencies):,}"
    )

    print(
        f"  categories: "
        f"{len(category_frequencies)}"
    )

    print(
        f"  elapsed: "
        f"{elapsed:.3f}s"
    )

    for bucket_count in (
        bucket_counts
    ):
        print()
        print(
            "=" * 72
        )

        print(
            f"{bucket_count} BUCKETS"
        )

        allocation = (
            allocate_category_buckets(
                category_frequencies=(
                    category_frequencies
                ),
                total_bucket_count=(
                    bucket_count
                ),
            )
        )

        print_category_allocation(
            category_frequencies=(
                category_frequencies
            ),
            allocation=allocation,
        )

        mapping = (
            build_category_equal_mass_mapping(
                category_frequencies=(
                    category_frequencies
                ),
                allocation=allocation,
            )
        )

        statistics = (
            bucket_statistics(
                frequencies=(
                    frequencies
                ),
                mapping=mapping,
            )
        )

        print()

        print_statistics(
            bucket_count=(
                bucket_count
            ),
            statistics=statistics,
        )


if __name__ == "__main__":
    main()