from collections import Counter
from dataclasses import dataclass

from solver.canonical_hand import RANK_ORDER
from solver.hand import Hand


@dataclass(frozen=True)
class DrawHandBucket:
    rank_bands: tuple[int, ...]
    duplicate_flags: tuple[bool, ...]
    dominant_suit_flags: tuple[bool, ...]


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

    dominant_suit = max(
        suit_counts,
        key=suit_counts.get,
    )
    dominant_suit_count = suit_counts[
        dominant_suit
    ]

    return DrawHandBucket(
        rank_bands=tuple(
            _rank_band(rank)
            for rank in rank_values
        ),
        duplicate_flags=tuple(
            rank_counts[rank] > 1
            for rank in rank_values
        ),
        dominant_suit_flags=tuple(
            (
                card.suit == dominant_suit
                and dominant_suit_count >= 3
            )
            for card in hand.cards
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