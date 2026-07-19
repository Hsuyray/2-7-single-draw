from dataclasses import dataclass

from solver.cards import Card
from solver.draw_deck import DrawDeck
from solver.hand import Hand


@dataclass(frozen=True)
class DrawResult:
    original_hand: Hand
    final_hand: Hand
    discarded_cards: tuple[Card, ...]
    drawn_cards: tuple[Card, ...]


def draw_cards(
    hand: Hand,
    deck: DrawDeck,
    discard_indices: list[int],
) -> DrawResult:
    partial_hand, discarded_cards = hand.discard(discard_indices)

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
    )