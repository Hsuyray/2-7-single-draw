from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

from solver.cards import Card
from solver.hand import Hand
from solver.made_hand_bucket import (
    made_hand_bucket,
)


RANKS = "23456789TJQKA"
SUITS = "shdc"

POSTDRAW_BUCKET_COUNT = 128

CATEGORY_BUCKET_ALLOCATION = {
    0: 61,
    1: 51,
    2: 7,
    3: 4,
    4: 1,
    5: 1,
    6: 1,
    7: 1,
    8: 1,
}


@dataclass(frozen=True)
class PostdrawStrengthBucket:
    """
    Deterministic postdraw hand-strength
    abstraction.

    category:
        Original made-hand category from
        the 2-7 evaluator.

    bucket_id:
        Global bucket identifier in the
        range 0..127.

    category_bucket:
        Bucket identifier within the
        made-hand category.
    """

    category: int
    bucket_id: int
    category_bucket: int

    def __post_init__(self) -> None:
        if self.category not in (
            CATEGORY_BUCKET_ALLOCATION
        ):
            raise ValueError(
                "Unknown made-hand category."
            )

        if not (
            0
            <= self.bucket_id
            < POSTDRAW_BUCKET_COUNT
        ):
            raise ValueError(
                "Postdraw bucket ID is "
                "outside the valid range."
            )

        category_bucket_count = (
            CATEGORY_BUCKET_ALLOCATION[
                self.category
            ]
        )

        if not (
            0
            <= self.category_bucket
            < category_bucket_count
        ):
            raise ValueError(
                "Category bucket is outside "
                "the valid range."
            )


def _standard_deck() -> tuple[
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


@lru_cache(maxsize=1)
def _score_frequencies() -> dict[
    tuple[int, ...],
    int,
]:
    """
    Enumerate the complete five-card hand
    universe once per process.

    The result is cached, so subsequent
    postdraw lookups are dictionary-only.
    """
    frequencies: Counter = Counter()

    deck = _standard_deck()

    for cards in combinations(
        deck,
        5,
    ):
        hand = Hand(
            cards=tuple(
                cards
            )
        )

        score = (
            made_hand_bucket(
                hand
            ).score
        )

        frequencies[
            score
        ] += 1

    return dict(
        frequencies
    )


def _frequencies_by_category() -> dict[
    int,
    dict[
        tuple[int, ...],
        int,
    ],
]:
    result: dict[
        int,
        dict[
            tuple[int, ...],
            int,
        ],
    ] = {}

    for (
        score,
        frequency,
    ) in _score_frequencies().items():
        if not score:
            raise RuntimeError(
                "Made-hand score cannot "
                "be empty."
            )

        category = score[0]

        result.setdefault(
            category,
            {},
        )[
            score
        ] = frequency

    return result


def _category_offsets() -> dict[
    int,
    int,
]:
    offsets = {}

    current = 0

    for category in sorted(
        CATEGORY_BUCKET_ALLOCATION
    ):
        offsets[
            category
        ] = current

        current += (
            CATEGORY_BUCKET_ALLOCATION[
                category
            ]
        )

    if current != POSTDRAW_BUCKET_COUNT:
        raise RuntimeError(
            "Category bucket allocation "
            "does not sum to the configured "
            "postdraw bucket count."
        )

    return offsets


@lru_cache(maxsize=1)
def _score_to_bucket() -> dict[
    tuple[int, ...],
    PostdrawStrengthBucket,
]:
    """
    Build the deterministic 128-bucket
    category-preserving equal-mass mapping.
    """
    frequencies_by_category = (
        _frequencies_by_category()
    )

    offsets = _category_offsets()

    mapping: dict[
        tuple[int, ...],
        PostdrawStrengthBucket,
    ] = {}

    for category in sorted(
        frequencies_by_category
    ):
        frequencies = (
            frequencies_by_category[
                category
            ]
        )

        bucket_count = (
            CATEGORY_BUCKET_ALLOCATION[
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

            midpoint_mass = (
                cumulative_mass
                + score_mass / 2
            )

            local_bucket = int(
                midpoint_mass
                * bucket_count
                / total_mass
            )

            local_bucket = min(
                local_bucket,
                bucket_count - 1,
            )

            global_bucket = (
                offsets[
                    category
                ]
                + local_bucket
            )

            mapping[
                score
            ] = (
                PostdrawStrengthBucket(
                    category=category,
                    bucket_id=(
                        global_bucket
                    ),
                    category_bucket=(
                        local_bucket
                    ),
                )
            )

            cumulative_mass += (
                score_mass
            )

    return mapping


def postdraw_strength_bucket(
    hand: Hand,
) -> PostdrawStrengthBucket:
    """
    Convert one exact five-card hand into
    the deterministic 128-bucket postdraw
    abstraction.
    """
    if len(
        hand.cards
    ) != 5:
        raise ValueError(
            "Postdraw strength bucket "
            "requires exactly five cards."
        )

    score = (
        made_hand_bucket(
            hand
        ).score
    )

    mapping = (
        _score_to_bucket()
    )

    try:
        return mapping[
            score
        ]

    except KeyError as error:
        raise RuntimeError(
            "Made-hand score is missing "
            "from the complete postdraw "
            "bucket universe."
        ) from error


def postdraw_bucket_mapping_size() -> int:
    return len(
        _score_to_bucket()
    )


def postdraw_bucket_count() -> int:
    return len(
        {
            bucket.bucket_id
            for bucket
            in _score_to_bucket().values()
        }
    )