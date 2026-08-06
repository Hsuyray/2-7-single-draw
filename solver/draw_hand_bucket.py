from collections import Counter
from dataclasses import dataclass

from solver.canonical_hand import RANK_ORDER
from solver.hand import Hand


@dataclass(frozen=True)
class DrawHandBucket:
    rank_classes: tuple[int, ...]
    rank_multiplicities: tuple[int, ...]
    pair_classes: tuple[int, ...]
    trip_classes: tuple[int, ...]
    quad_classes: tuple[int, ...]
    unique_rank_count: int
    flush_risk_positions: tuple[bool, ...]
    is_straight: bool
    is_flush: bool


def draw_hand_bucket(
    hand: Hand,
) -> DrawHandBucket:
    """
    Build a positional draw-hand abstraction.

    Cards are ordered deterministically before
    positional features are generated.

    The ordering keeps cards belonging to a
    four-card or five-card dominant suit together
    within equal ranks, without storing the
    physical suit name in the bucket.
    """
    if len(hand.cards) != 5:
        raise ValueError(
            "Draw-hand abstraction requires "
            "exactly five cards."
        )

    suit_counts = Counter(
        card.suit
        for card in hand.cards
    )

    dominant_suit, dominant_count = max(
        suit_counts.items(),
        key=lambda item: (
            item[1],
            item[0],
        ),
    )

    flush_relevant = (
        dominant_count >= 4
    )

    ordered_cards = tuple(
        sorted(
            hand.cards,
            key=lambda card: (
                RANK_ORDER[
                    card.rank
                ],
                (
                    0
                    if (
                        flush_relevant
                        and card.suit
                        == dominant_suit
                    )
                    else 1
                ),
                card.suit,
            ),
        )
    )

    rank_values = tuple(
        RANK_ORDER[
            card.rank
        ]
        for card in ordered_cards
    )

    rank_classes = tuple(
        _rank_class(
            rank
        )
        for rank in rank_values
    )

    exact_rank_counts = Counter(
        rank_values
    )

    return DrawHandBucket(
        rank_classes=rank_classes,
        rank_multiplicities=tuple(
            exact_rank_counts[
                rank
            ]
            for rank in rank_values
        ),
        pair_classes=tuple(
            sorted(
                _rank_class(
                    rank
                )
                for rank, count
                in exact_rank_counts.items()
                if count == 2
            )
        ),
        trip_classes=tuple(
            sorted(
                _rank_class(
                    rank
                )
                for rank, count
                in exact_rank_counts.items()
                if count == 3
            )
        ),
        quad_classes=tuple(
            sorted(
                _rank_class(
                    rank
                )
                for rank, count
                in exact_rank_counts.items()
                if count == 4
            )
        ),
        unique_rank_count=len(
            exact_rank_counts
        ),
        flush_risk_positions=tuple(
            (
                flush_relevant
                and card.suit
                == dominant_suit
            )
            for card in ordered_cards
        ),
        is_straight=_is_straight(
            rank_values
        ),
        is_flush=(
            dominant_count == 5
        ),
    )


def _rank_class(
    rank: int,
) -> int:
    """
    Intermediate draw abstraction.

    Classes:
        2-3   -> 0
        4-5   -> 1
        6-7   -> 2
        8-9   -> 3
        T-J   -> 4
        Q-K-A -> 5
    """
    if rank <= 3:
        return 0

    if rank <= 5:
        return 1

    if rank <= 7:
        return 2

    if rank <= 9:
        return 3

    if rank <= 11:
        return 4

    return 5


def _is_straight(
    rank_values: tuple[
        int,
        ...,
    ],
) -> bool:
    unique_ranks = sorted(
        set(
            rank_values
        )
    )

    if len(unique_ranks) != 5:
        return False

    return all(
        (
            unique_ranks[
                index + 1
            ]
            - unique_ranks[
                index
            ]
            == 1
        )
        for index in range(4)
    )