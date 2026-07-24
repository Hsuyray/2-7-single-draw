from collections import Counter
from dataclasses import dataclass

from solver.canonical_hand import RANK_ORDER
from solver.hand import Hand


@dataclass(frozen=True)
class DrawHandBucket:
    rank_values: tuple[int, ...]
    rank_multiplicities: tuple[int, ...]
    suit_pattern: tuple[int, ...]
    pair_ranks: tuple[int, ...]
    trip_ranks: tuple[int, ...]
    quad_ranks: tuple[int, ...]
    unique_rank_count: int
    is_straight: bool
    is_flush: bool


def draw_hand_bucket(
    hand: Hand,
) -> DrawHandBucket:
    if len(hand.cards) != 5:
        raise ValueError(
            "Draw-hand abstraction requires "
            "exactly five cards."
        )

    rank_values = tuple(
        RANK_ORDER[card.rank]
        for card in hand.cards
    )

    rank_counts = Counter(rank_values)

    pair_ranks = tuple(
        sorted(
            rank
            for rank, count
            in rank_counts.items()
            if count == 2
        )
    )

    trip_ranks = tuple(
        sorted(
            rank
            for rank, count
            in rank_counts.items()
            if count == 3
        )
    )

    quad_ranks = tuple(
        sorted(
            rank
            for rank, count
            in rank_counts.items()
            if count == 4
        )
    )

    return DrawHandBucket(
        rank_values=rank_values,
        rank_multiplicities=tuple(
            rank_counts[rank]
            for rank in rank_values
        ),
        suit_pattern=_canonical_suit_pattern(
            hand
        ),
        pair_ranks=pair_ranks,
        trip_ranks=trip_ranks,
        quad_ranks=quad_ranks,
        unique_rank_count=len(rank_counts),
        is_straight=_is_straight(
            rank_values
        ),
        is_flush=_is_flush(hand),
    )


def _canonical_suit_pattern(
    hand: Hand,
) -> tuple[int, ...]:
    """
    Convert actual suits into suit-isomorphic labels.

    Examples:
        2c 3d 4h 5s 7c -> (0, 1, 2, 3, 0)
        2h 3s 4c 5d 7h -> (0, 1, 2, 3, 0)

    These hands have the same suit structure, so they
    receive the same pattern even though the real suits
    differ.
    """
    suit_labels: dict[str, int] = {}
    next_label = 0
    pattern: list[int] = []

    for card in hand.cards:
        if card.suit not in suit_labels:
            suit_labels[card.suit] = (
                next_label
            )
            next_label += 1

        pattern.append(
            suit_labels[card.suit]
        )

    return tuple(pattern)


def _is_flush(
    hand: Hand,
) -> bool:
    return (
        len(
            {
                card.suit
                for card in hand.cards
            }
        )
        == 1
    )


def _is_straight(
    rank_values: tuple[int, ...],
) -> bool:
    unique_ranks = sorted(
        set(rank_values)
    )

    if len(unique_ranks) != 5:
        return False

    # In 2-7 lowball, Ace is always high.
    # Therefore A-2-3-4-5 is not treated
    # as a five-high straight.
    return all(
        unique_ranks[index + 1]
        - unique_ranks[index]
        == 1
        for index in range(4)
    )