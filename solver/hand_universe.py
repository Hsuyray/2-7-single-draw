from collections import Counter
from collections.abc import (
    Iterable,
    Iterator,
)
from itertools import combinations
from math import comb
from typing import TypeAlias

from solver.cards import Card, Deck
from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand import Hand
from solver.hand_abstraction import (
    ExactHandKey,
    exact_hand_key,
)


STARTING_HAND_SIZE = 5
DECK_SIZE = 52

STARTING_HAND_COMBINATION_COUNT = comb(
    DECK_SIZE,
    STARTING_HAND_SIZE,
)


StartingHandKey: TypeAlias = (
    ExactHandKey
    | DrawHandBucket
)


def standard_deck_cards() -> tuple[
    Card,
    ...,
]:
    """
    Return the project's canonical
    52-card deck.
    """
    deck = Deck()

    return tuple(
        deck.cards
    )


def iter_starting_hands() -> Iterator[
    Hand
]:
    """
    Lazily iterate over all legal
    five-card combinations.

    Total:
        C(52, 5) = 2,598,960
    """
    deck = standard_deck_cards()

    for cards in combinations(
        deck,
        STARTING_HAND_SIZE,
    ):
        yield Hand(cards)


def iter_exact_starting_hand_keys(
) -> Iterator[
    ExactHandKey
]:
    """
    Convert each raw five-card combination
    into its canonical ExactHandKey.

    Multiple raw combinations may map to
    the same ExactHandKey.
    """
    for hand in iter_starting_hands():
        yield exact_hand_key(
            hand
        )


def count_starting_hands() -> int:
    return (
        STARTING_HAND_COMBINATION_COUNT
    )


def count_exact_keys(
    hands: Iterable[Hand],
) -> dict[
    ExactHandKey,
    int,
]:
    """
    Aggregate an arbitrary collection of
    raw hands by canonical ExactHandKey.

    Useful both for tests and for the
    complete starting-hand universe.
    """
    counts: Counter[
        ExactHandKey
    ] = Counter()

    for hand in hands:
        key = exact_hand_key(
            hand
        )

        counts[key] += 1

    return dict(counts)


def exact_starting_hand_key_counts(
) -> dict[
    ExactHandKey,
    int,
]:
    """
    Aggregate all 2,598,960 raw starting
    combinations by canonical ExactHandKey.

    This is an expensive offline/precompute
    operation.

    Do not call this inside CFR traversal
    or ordinary unit tests.
    """
    return count_exact_keys(
        iter_starting_hands()
    )


def draw_bucket_counts(
) -> dict[
    DrawHandBucket,
    int,
]:
    """
    Aggregate the complete five-card
    universe into DrawHandBucket classes.

    Each value represents the number of
    raw five-card combinations belonging
    to the bucket.

    This is also an offline/precompute
    operation.
    """
    counts: Counter[
        DrawHandBucket
    ] = Counter()

    for hand in iter_starting_hands():
        bucket = draw_hand_bucket(
            hand
        )

        counts[bucket] += 1

    return dict(counts)


def total_exact_key_combinations(
    key_counts: dict[
        ExactHandKey,
        int,
    ],
) -> int:
    return sum(
        key_counts.values()
    )


def total_bucket_combinations(
    bucket_counts: dict[
        DrawHandBucket,
        int,
    ],
) -> int:
    return sum(
        bucket_counts.values()
    )