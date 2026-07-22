from collections import Counter
from dataclasses import dataclass

from solver.canonical_hand import RANK_ORDER
from solver.hand import Hand


@dataclass(frozen=True)
class DrawHandBucket:
    rank_bands: tuple[int, ...]
    duplicate_flags: tuple[bool, ...]
    suit_multiplicities: tuple[int, ...]
    unique_rank_count: int
    unique_low_count: int
    high_card_count: int
    straight_pressure: int


def draw_hand_bucket(
    hand: Hand,
) -> DrawHandBucket:
    rank_values = tuple(
        RANK_ORDER[card.rank]
        for card in hand.cards
    )

    rank_counts = Counter(rank_values)
    suit_counts = Counter(
        card.suit
        for card in hand.cards
    )

    return DrawHandBucket(
        rank_bands=tuple(
            _rank_band(rank)
            for rank in rank_values
        ),
        duplicate_flags=tuple(
            rank_counts[rank] > 1
            for rank in rank_values
        ),
        suit_multiplicities=tuple(
            suit_counts[card.suit]
            for card in hand.cards
        ),
        unique_rank_count=len(
            set(rank_values)
        ),
        unique_low_count=len(
            {
                rank
                for rank in rank_values
                if rank <= 9
            }
        ),
        high_card_count=sum(
            rank >= 10
            for rank in rank_values
        ),
        straight_pressure=_straight_pressure(
            rank_values
        ),
    )


def _rank_band(
    rank: int,
) -> int:
    if rank <= 5:
        return 0

    if rank <= 7:
        return 1

    if rank <= 9:
        return 2

    return 3


def _straight_pressure(
    rank_values: tuple[int, ...],
) -> int:
    unique_ranks = set(rank_values)

    return max(
        (
            len(
                unique_ranks.intersection(
                    range(start, start + 5)
                )
            )
            for start in range(2, 11)
        ),
        default=0,
    )