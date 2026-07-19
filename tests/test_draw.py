import pytest

from solver.cards import Card
from solver.draw import draw_cards
from solver.draw_deck import DrawDeck
from solver.hand import Hand


def test_draw_one_card() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")
    deck = DrawDeck(shuffle=False)
    deck.stock = [Card.from_string("2h")]

    result = draw_cards(
        hand=hand,
        deck=deck,
        discard_indices=[4],
    )

    assert result.original_hand == hand
    assert str(result.final_hand) == "7s 5h 4d 3c 2h"
    assert result.discarded_cards == (
        Card.from_string("Ks"),
    )
    assert result.drawn_cards == (
        Card.from_string("2h"),
    )
    assert deck.stock_size == 0
    assert deck.muck == [
        Card.from_string("Ks"),
    ]


def test_draw_multiple_cards() -> None:
    hand = Hand.from_strings(
        "7s",
        "5h",
        "Qd",
        "Jc",
        "Ks",
    )
    deck = DrawDeck(shuffle=False)
    deck.stock = [
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
    assert deck.stock_size == 0
    assert set(deck.muck) == set(
        result.discarded_cards
    )


def test_stand_pat_draws_no_cards() -> None:
    hand = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    deck = DrawDeck(shuffle=False)
    original_stock_size = deck.stock_size

    result = draw_cards(
        hand=hand,
        deck=deck,
        discard_indices=[],
    )

    assert result.final_hand == hand
    assert result.discarded_cards == ()
    assert result.drawn_cards == ()
    assert deck.stock_size == original_stock_size
    assert deck.muck_size == 0


def test_invalid_discard_index_raises_error() -> None:
    hand = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "Ks",
    )
    deck = DrawDeck(shuffle=False)

    with pytest.raises(IndexError):
        draw_cards(
            hand=hand,
            deck=deck,
            discard_indices=[5],
        )


def test_duplicate_discard_indices_raise_error() -> None:
    hand = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "Ks",
    )
    deck = DrawDeck(shuffle=False)

    with pytest.raises(ValueError):
        draw_cards(
            hand=hand,
            deck=deck,
            discard_indices=[4, 4],
        )


def test_cannot_draw_more_cards_than_deck_contains() -> None:
    hand = Hand.from_strings(
        "7s",
        "5h",
        "Qd",
        "Jc",
        "Ks",
    )
    deck = DrawDeck(
        cards=[
            Card.from_string("2h"),
            Card.from_string("3d"),
        ],
        shuffle=False,
    )

    with pytest.raises(ValueError):
        draw_cards(
            hand=hand,
            deck=deck,
            discard_indices=[2, 3, 4],
        )