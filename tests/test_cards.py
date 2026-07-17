import pytest

from solver.cards import Card, Deck


def test_create_card_from_string() -> None:
    card = Card.from_string("7s")

    assert card.rank == "7"
    assert card.suit == "s"
    assert str(card) == "7s"


def test_card_input_is_normalized() -> None:
    card = Card.from_string("Ah")

    assert card.rank == "A"
    assert card.suit == "h"


def test_invalid_rank_raises_error() -> None:
    with pytest.raises(ValueError):
        Card.from_string("1s")


def test_invalid_suit_raises_error() -> None:
    with pytest.raises(ValueError):
        Card.from_string("7x")


def test_invalid_length_raises_error() -> None:
    with pytest.raises(ValueError):
        Card.from_string("10s")


def test_deck_contains_52_unique_cards() -> None:
    deck = Deck()

    assert len(deck) == 52
    assert len(set(deck.cards)) == 52


def test_draw_removes_cards_from_deck() -> None:
    deck = Deck()

    drawn_cards = deck.draw(5)

    assert len(drawn_cards) == 5
    assert len(deck) == 47


def test_drawn_cards_are_not_in_deck() -> None:
    deck = Deck()

    drawn_cards = deck.draw(5)

    assert all(card not in deck.cards for card in drawn_cards)


def test_cannot_draw_more_cards_than_remain() -> None:
    deck = Deck()

    with pytest.raises(ValueError):
        deck.draw(53)


def test_draw_zero_cards_returns_empty_list() -> None:
    deck = Deck()

    drawn_cards = deck.draw(0)

    assert drawn_cards == []
    assert len(deck) == 52


def test_draw_count_cannot_be_negative() -> None:
    deck = Deck()

    with pytest.raises(ValueError):
        deck.draw(-1)