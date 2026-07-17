import pytest

from solver.cards import Card
from solver.hand import Hand


def test_create_hand_from_strings() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "2s")

    assert len(hand.cards) == 5
    assert str(hand) == "7s 5h 4d 3c 2s"


def test_hand_has_score() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "2s")

    assert hand.score == (0, 7, 5, 4, 3, 2)


def test_hand_requires_five_cards() -> None:
    with pytest.raises(ValueError):
        Hand.from_strings("7s", "5h", "4d", "3c")


def test_hand_rejects_duplicate_cards() -> None:
    with pytest.raises(ValueError):
        Hand.from_strings("7s", "7s", "4d", "3c", "2s")


def test_discard_one_card() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")

    partial_hand, discarded_cards = hand.discard([4])

    assert len(partial_hand.cards) == 4
    assert discarded_cards == (Card.from_string("Ks"),)


def test_discard_multiple_cards() -> None:
    hand = Hand.from_strings("7s", "5h", "Qd", "Jc", "Ks")

    partial_hand, discarded_cards = hand.discard([2, 3, 4])

    assert len(partial_hand.cards) == 2
    assert len(discarded_cards) == 3


def test_complete_partial_hand() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")

    partial_hand, _ = hand.discard([4])
    completed_hand = partial_hand.complete(
        [Card.from_string("2h")]
    )

    assert str(completed_hand) == "7s 5h 4d 3c 2h"


def test_duplicate_discard_indices_raise_error() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")

    with pytest.raises(ValueError):
        hand.discard([4, 4])


def test_invalid_discard_index_raises_error() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")

    with pytest.raises(IndexError):
        hand.discard([5])


def test_negative_discard_index_raises_error() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")

    with pytest.raises(IndexError):
        hand.discard([-1])


def test_completed_hand_must_have_five_cards() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")

    partial_hand, _ = hand.discard([4])

    with pytest.raises(ValueError):
        partial_hand.complete([])


def test_completed_hand_rejects_duplicate_cards() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")

    partial_hand, _ = hand.discard([4])

    with pytest.raises(ValueError):
        partial_hand.complete(
            [Card.from_string("7s")]
        )