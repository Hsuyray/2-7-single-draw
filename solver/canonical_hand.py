from solver.cards import Card
from solver.hand import Hand


RANK_ORDER = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}

SUIT_ORDER = {
    "c": 0,
    "d": 1,
    "h": 2,
    "s": 3,
}


def canonical_card_key(
    card: Card,
) -> tuple[int, int]:
    return (
        RANK_ORDER[card.rank],
        SUIT_ORDER[card.suit],
    )


def canonicalize_cards(
    cards: tuple[Card, ...],
) -> tuple[Card, ...]:
    return tuple(
        sorted(
            cards,
            key=canonical_card_key,
        )
    )


def canonicalize_hand(
    hand: Hand,
) -> Hand:
    return Hand(
        canonicalize_cards(hand.cards)
    )