import pytest

from solver.actions import DiscardAction
from solver.cards import Card
from solver.draw import draw_cards
from solver.draw_deck import DrawDeck
from solver.hand import Hand


def test_draw_one_card() -> None:
    hand = Hand.from_strings("7s", "5h", "4d", "3c", "Ks")
    deck = DrawDeck(shuffle=False)
    deck.stock = [Card.from_string("2h")]

    action = DiscardAction((4,))

    result = draw_cards(
        hand=hand,
        deck=deck,
        action=action,
    )

    assert result.original_hand == hand
    assert result.action == action
    assert str(result.final_hand) == "2h 3c 4d 5h 7s"
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

    action = DiscardAction((2, 3, 4))

    result = draw_cards(
        hand=hand,
        deck=deck,
        action=action,
    )

    assert result.action == action
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

    action = DiscardAction(())

    result = draw_cards(
        hand=hand,
        deck=deck,
        action=action,
    )

    assert result.action == action
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
    action = DiscardAction((5,))

    with pytest.raises(ValueError):
        draw_cards(
            hand=hand,
            deck=deck,
            action=action,
        )


def test_duplicate_discard_indices_raise_error() -> None:
    with pytest.raises(ValueError):
        DiscardAction((4, 4))


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
    action = DiscardAction((2, 3, 4))

    with pytest.raises(ValueError):
        draw_cards(
            hand=hand,
            deck=deck,
            action=action,
        )


def test_draw_result_stores_action() -> None:
    hand = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "Ks",
    )
    deck = DrawDeck(
        cards=[
            Card.from_string("2h"),
        ],
        shuffle=False,
    )
    action = DiscardAction((4,))

    result = draw_cards(
        hand=hand,
        deck=deck,
        action=action,
    )

    assert result.action == action


def test_final_hand_is_canonicalized() -> None:
    hand = Hand.from_strings(
        "3c",
        "4d",
        "5h",
        "7s",
        "Ks",
    )
    deck = DrawDeck(
        cards=[
            Card.from_string("2h"),
        ],
        shuffle=False,
    )

    result = draw_cards(
        hand=hand,
        deck=deck,
        action=DiscardAction((4,)),
    )

    assert result.final_hand.cards == (
        Card.from_string("2h"),
        Card.from_string("3c"),
        Card.from_string("4d"),
        Card.from_string("5h"),
        Card.from_string("7s"),
    )