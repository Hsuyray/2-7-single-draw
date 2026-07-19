from dataclasses import dataclass

from solver.actions import DiscardAction
from solver.cards import Card
from solver.draw_deck import DrawDeck
from solver.hand import Hand


@dataclass(frozen=True)
class DrawResult:
    original_hand: Hand
    final_hand: Hand
    discarded_cards: tuple[Card, ...]
    drawn_cards: tuple[Card, ...]
    action: DiscardAction


def draw_cards(
    hand: Hand,
    deck: DrawDeck,
    action: DiscardAction,
) -> DrawResult:
    action.validate_for_hand_size(
        len(hand.cards)
    )

    partial_hand, discarded_cards = hand.discard(
        list(action.discard_indices)
    )

    drawn_cards = tuple(
        deck.replace(discarded_cards)
    )

    final_hand = partial_hand.complete(
        list(drawn_cards)
    )

    return DrawResult(
        original_hand=hand,
        final_hand=final_hand,
        discarded_cards=discarded_cards,
        drawn_cards=drawn_cards,
        action=action,
    )