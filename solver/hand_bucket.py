from collections import Counter
from dataclasses import dataclass

from solver.canonical_hand import RANK_ORDER
from solver.hand import Hand


HIGH_CARD_BUCKET = 10


@dataclass(frozen=True)
class HandBucket:
    bucketed_ranks: tuple[int, ...]
    rank_multiplicities: tuple[int, ...]
    suit_pattern: tuple[int, ...]
    low_card_mask: int
    unique_low_count: int
    max_suit_count: int


def hand_bucket(
    hand: Hand,
) -> HandBucket:
    rank_values = tuple(
        RANK_ORDER[card.rank]
        for card in hand.cards
    )

    bucketed_ranks = tuple(
        min(rank, HIGH_CARD_BUCKET)
        for rank in rank_values
    )

    rank_counts = Counter(rank_values)

    rank_multiplicities = tuple(
        sorted(
            rank_counts.values(),
            reverse=True,
        )
    )

    suit_pattern = _canonical_suit_pattern(
        hand
    )

    low_card_mask = 0
    unique_low_ranks: set[int] = set()

    for index, rank in enumerate(rank_values):
        if rank <= 9:
            low_card_mask |= 1 << index
            unique_low_ranks.add(rank)

    suit_counts = Counter(
        card.suit
        for card in hand.cards
    )

    max_suit_count = max(
        suit_counts.values(),
        default=0,
    )

    return HandBucket(
        bucketed_ranks=bucketed_ranks,
        rank_multiplicities=rank_multiplicities,
        suit_pattern=suit_pattern,
        low_card_mask=low_card_mask,
        unique_low_count=len(unique_low_ranks),
        max_suit_count=max_suit_count,
    )


def _canonical_suit_pattern(
    hand: Hand,
) -> tuple[int, ...]:
    suit_mapping: dict[str, int] = {}
    next_suit_id = 0
    pattern: list[int] = []

    for card in hand.cards:
        if card.suit not in suit_mapping:
            suit_mapping[card.suit] = next_suit_id
            next_suit_id += 1

        pattern.append(
            suit_mapping[card.suit]
        )

    return tuple(pattern)