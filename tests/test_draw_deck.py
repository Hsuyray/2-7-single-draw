import pytest

from solver.cards import Card
from solver.draw_deck import DrawDeck


def make_cards(*values: str) -> list[Card]:
    return [
        Card.from_string(value)
        for value in values
    ]


def test_standard_draw_deck_contains_52_cards() -> None:
    deck = DrawDeck(shuffle=False)

    assert deck.stock_size == 52
    assert deck.muck_size == 0
    assert deck.total_available == 52


def test_standard_draw_deck_contains_unique_cards() -> None:
    deck = DrawDeck(shuffle=False)

    assert len(set(deck.stock)) == 52


def test_draw_removes_cards_from_stock() -> None:
    deck = DrawDeck(
        cards=make_cards("2s", "3h", "4d"),
        shuffle=False,
    )

    drawn_cards = deck.draw(2)

    assert drawn_cards == make_cards("3h", "4d")
    assert deck.stock == make_cards("2s")
    assert deck.stock_size == 1


def test_draw_zero_returns_empty_list() -> None:
    deck = DrawDeck(shuffle=False)

    assert deck.draw(0) == []
    assert deck.stock_size == 52


def test_negative_draw_is_rejected() -> None:
    deck = DrawDeck(shuffle=False)

    with pytest.raises(ValueError):
        deck.draw(-1)


def test_discard_moves_cards_to_muck() -> None:
    deck = DrawDeck(
        cards=make_cards("2s", "3h"),
        shuffle=False,
    )

    discarded_cards = make_cards("As", "Kh")

    deck.discard(discarded_cards)

    assert deck.muck == discarded_cards
    assert deck.muck_size == 2
    assert deck.total_available == 4


def test_duplicate_cards_in_initial_deck_are_rejected() -> None:
    with pytest.raises(ValueError):
        DrawDeck(
            cards=make_cards("2s", "2s"),
            shuffle=False,
        )


def test_duplicate_cards_in_single_discard_are_rejected() -> None:
    deck = DrawDeck(
        cards=make_cards("2s"),
        shuffle=False,
    )

    with pytest.raises(ValueError):
        deck.discard(
            make_cards("As", "As")
        )


def test_card_already_in_stock_cannot_be_discarded() -> None:
    deck = DrawDeck(
        cards=make_cards("2s", "3h"),
        shuffle=False,
    )

    with pytest.raises(ValueError):
        deck.discard(
            make_cards("2s")
        )


def test_card_already_in_muck_cannot_be_discarded_again() -> None:
    deck = DrawDeck(
        cards=make_cards("2s"),
        shuffle=False,
    )

    deck.discard(
        make_cards("As")
    )

    with pytest.raises(ValueError):
        deck.discard(
            make_cards("As")
        )


def test_muck_is_reshuffled_when_stock_runs_out() -> None:
    deck = DrawDeck(
        cards=make_cards("2s"),
        shuffle=False,
        seed=42,
    )

    deck.discard(
        make_cards("3h", "4d")
    )

    drawn_cards = deck.draw(3)

    assert set(drawn_cards) == set(
        make_cards("2s", "3h", "4d")
    )
    assert deck.stock_size == 0
    assert deck.muck_size == 0


def test_draw_can_use_stock_and_then_muck() -> None:
    deck = DrawDeck(
        cards=make_cards("2s", "3h"),
        shuffle=False,
        seed=42,
    )

    deck.discard(
        make_cards("4d", "5c")
    )

    drawn_cards = deck.draw(3)

    assert len(drawn_cards) == 3
    assert len(set(drawn_cards)) == 3
    assert deck.total_available == 1


def test_cannot_draw_more_than_total_available() -> None:
    deck = DrawDeck(
        cards=make_cards("2s", "3h"),
        shuffle=False,
    )

    deck.discard(
        make_cards("4d")
    )

    with pytest.raises(ValueError):
        deck.draw(4)


def test_replace_draws_before_adding_discards_to_muck() -> None:
    deck = DrawDeck(
        cards=make_cards("2s"),
        shuffle=False,
    )

    discarded_card = Card.from_string("As")

    replacement_cards = deck.replace(
        [discarded_card]
    )

    assert replacement_cards == make_cards("2s")
    assert discarded_card not in replacement_cards
    assert deck.muck == [discarded_card]


def test_replace_multiple_cards() -> None:
    deck = DrawDeck(
        cards=make_cards("2s", "3h", "4d"),
        shuffle=False,
    )

    discarded_cards = make_cards("As", "Kh")

    replacement_cards = deck.replace(
        discarded_cards
    )

    assert replacement_cards == make_cards("3h", "4d")
    assert deck.stock == make_cards("2s")
    assert deck.muck == discarded_cards