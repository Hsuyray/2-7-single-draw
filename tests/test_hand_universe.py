from itertools import islice
from solver.cards import RANKS, SUITS
from solver.hand import Hand
from solver.hand_universe import (
    DECK_SIZE,
    STARTING_HAND_COMBINATION_COUNT,
    STARTING_HAND_SIZE,
    count_starting_hands,
    iter_exact_starting_hand_keys,
    iter_starting_hands,
    standard_deck_cards,
)
from solver.hand_abstraction import ExactHandKey


def test_standard_deck_has_52_cards() -> None:
    deck = standard_deck_cards()

    assert len(deck) == DECK_SIZE


def test_standard_deck_has_no_duplicates() -> None:
    deck = standard_deck_cards()

    assert len(
        set(deck)
    ) == DECK_SIZE


def test_standard_deck_has_four_suits_per_rank() -> None:
    deck = standard_deck_cards()

    for rank in RANKS:
        matching = [
            card
            for card in deck
            if card.rank == rank
        ]

        assert len(matching) == 4


def test_starting_hand_size_is_five() -> None:
    hands = list(
        islice(
            iter_starting_hands(),
            10,
        )
    )

    assert len(hands) == 10

    assert all(
        isinstance(
            hand,
            Hand,
        )
        for hand in hands
    )

    assert all(
        len(hand.cards)
        == STARTING_HAND_SIZE
        for hand in hands
    )


def test_starting_hands_have_unique_cards() -> None:
    hands = list(
        islice(
            iter_starting_hands(),
            100,
        )
    )

    for hand in hands:
        assert (
            len(set(hand.cards))
            == STARTING_HAND_SIZE
        )


def test_starting_hand_count() -> None:
    assert (
        count_starting_hands()
        == STARTING_HAND_COMBINATION_COUNT
    )

    assert (
        STARTING_HAND_COMBINATION_COUNT
        == 2_598_960
    )


def test_exact_keys_are_generated_lazily() -> None:
    keys = list(
        islice(
            iter_exact_starting_hand_keys(),
            10,
        )
    )

    assert len(keys) == 10

    assert all(
        isinstance(
            key,
            ExactHandKey,
        )
        for key in keys
    )


def test_standard_deck_has_thirteen_ranks_per_suit() -> None:
    deck = standard_deck_cards()

    for suit in SUITS:
        matching = [
            card
            for card in deck
            if card.suit == suit
        ]

        assert len(matching) == 13