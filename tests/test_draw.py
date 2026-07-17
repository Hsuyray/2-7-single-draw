import pytest

from solver.cards import Card, Deck
from solver.draw import draw_cards
from solver.hand import Hand


def test_draw_one_card() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")
    deck = Deck()
    deck.cards = [Card.from_string("2h")]

    result = draw_cards(
        hand=hand,
        deck=deck,
        discard_indices=[4],
    )

    assert result.original_hand == hand
    assert str(result.final_hand) == "7s 5h 4d 3c 2h"
    assert result.discarded_cards == (Card.from_string("Ks"),)
    assert result.drawn_cards == (Card.from_string("2h"),)
    assert len(deck) == 0


def test_draw_multiple_cards() -> None:
    hand = Hand.from_strings("7s", "5h", "Qd", "Jc", "Ks")
    deck = Deck()
    deck.cards = [
        Card.from_string("2h"),
        Card.from_string("3d"),
        Card.from_string("4c"),
    ]

    result = draw_cards(
        hand=hand,
        deck=deck,
        discard_indices=[2, 3, 4],
    )

    assert len(result.final_hand.cards) == 5
    assert set(result.final_hand.cards) == {
        Card.from_string("7s"),
        Card.from_string("5h"),
        Card.from_string("2h"),
        Card.from_string("3d"),
        Card.from_string("4c"),
    }
    assert len(result.discarded_cards) == 3
    assert len(result.drawn_cards) == 3
    assert len(deck) == 0


def test_stand_pat_draws_no_cards() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "2s")
    deck = Deck()
    original_deck_size = len(deck)

    result = draw_cards(
        hand=hand,
        deck=deck,
        discard_indices=[],
    )

    assert result.final_hand == hand
    assert result.discarded_cards == ()
    assert result.drawn_cards == ()
    assert len(deck) == original_deck_size


def test_invalid_discard_index_raises_error() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")
    deck = Deck()

    with pytest.raises(IndexError):
        draw_cards(
            hand=hand,
            deck=deck,
            discard_indices=[5],
        )


def test_duplicate_discard_indices_raise_error() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")
    deck = Deck()

    with pytest.raises(ValueError):
        draw_cards(
            hand=hand,
            deck=deck,
            discard_indices=[4, 4],
        )


def test_cannot_draw_more_cards_than_deck_contains() -> None:
    hand = Hand.from_strings("7s", "5h", "Qd", "Jc", "Ks")
    deck = Deck()
    deck.cards = [
        Card.from_string("2h"),
        Card.from_string("3d"),
    ]

    with pytest.raises(ValueError):
        draw_cards(
            hand=hand,
            deck=deck,
            discard_indices=[2, 3, 4],
        )