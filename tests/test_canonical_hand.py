from solver.canonical_hand import (
    canonicalize_cards,
    canonicalize_hand,
)
from solver.cards import Card
from solver.hand import Hand


def test_canonicalize_hand_sorts_by_rank() -> None:
    hand = Hand.from_strings(
        "Ks",
        "3c",
        "Td",
        "5c",
        "4s",
    )

    canonical = canonicalize_hand(hand)

    assert canonical.cards == (
        Card.from_string("3c"),
        Card.from_string("4s"),
        Card.from_string("5c"),
        Card.from_string("Td"),
        Card.from_string("Ks"),
    )


def test_canonicalize_cards_sorts_equal_ranks_by_suit() -> None:
    cards = (
        Card.from_string("7s"),
        Card.from_string("7c"),
        Card.from_string("7h"),
        Card.from_string("7d"),
    )

    canonical = canonicalize_cards(cards)

    assert canonical == (
        Card.from_string("7c"),
        Card.from_string("7d"),
        Card.from_string("7h"),
        Card.from_string("7s"),
    )


def test_canonicalization_is_deterministic() -> None:
    first_hand = Hand.from_strings(
        "7s",
        "2h",
        "Kd",
        "4c",
        "9s",
    )

    second_hand = Hand.from_strings(
        "9s",
        "4c",
        "2h",
        "7s",
        "Kd",
    )

    assert canonicalize_hand(
        first_hand
    ) == canonicalize_hand(
        second_hand
    )


def test_canonicalization_does_not_change_score() -> None:
    hand = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )

    canonical = canonicalize_hand(hand)

    assert canonical.score == hand.score


def test_canonicalization_does_not_modify_original() -> None:
    hand = Hand.from_strings(
        "Ks",
        "3c",
        "Td",
        "5c",
        "4s",
    )

    original_cards = hand.cards

    canonicalize_hand(hand)

    assert hand.cards == original_cards


def test_already_canonical_hand_is_unchanged() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Tc",
    )

    assert canonicalize_hand(hand) == hand