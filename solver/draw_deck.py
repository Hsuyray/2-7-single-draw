import random
from collections.abc import Iterable

from solver.cards import Card, RANKS, SUITS


class DrawDeck:
    def __init__(
        self,
        cards: Iterable[Card] | None = None,
        *,
        shuffle: bool = True,
        seed: int | None = None,
    ) -> None:
        if cards is None:
            initial_cards = [
                Card(rank, suit)
                for rank in RANKS
                for suit in SUITS
            ]
        else:
            initial_cards = list(cards)

        if len(set(initial_cards)) != len(initial_cards):
            raise ValueError(
                "Draw deck cannot contain duplicate cards."
            )

        self._random = random.Random(seed)
        self.stock: list[Card] = initial_cards
        self.muck: list[Card] = []

        if shuffle:
            self._random.shuffle(self.stock)

    def __len__(self) -> int:
        return len(self.stock)

    @property
    def stock_size(self) -> int:
        return len(self.stock)

    @property
    def muck_size(self) -> int:
        return len(self.muck)

    @property
    def total_available(self) -> int:
        return len(self.stock) + len(self.muck)

    def draw(self, count: int = 1) -> list[Card]:
        if count < 0:
            raise ValueError(
                "Draw count cannot be negative."
            )

        if count == 0:
            return []

        if count > self.total_available:
            raise ValueError(
                "Not enough cards available to complete the draw."
            )

        drawn_cards: list[Card] = []

        while len(drawn_cards) < count:
            if not self.stock:
                self._reshuffle_muck_into_stock()

            remaining_count = count - len(drawn_cards)
            draw_now = min(remaining_count, len(self.stock))

            drawn_cards.extend(
                self.stock[-draw_now:]
            )
            del self.stock[-draw_now:]

        return drawn_cards

    def discard(self, cards: Iterable[Card]) -> None:
        discarded_cards = list(cards)

        if len(set(discarded_cards)) != len(discarded_cards):
            raise ValueError(
                "Discarded cards cannot contain duplicates."
            )

        existing_cards = set(self.stock) | set(self.muck)

        duplicate_cards = [
            card
            for card in discarded_cards
            if card in existing_cards
        ]

        if duplicate_cards:
            raise ValueError(
                "A discarded card is already present "
                "in the draw deck."
            )

        self.muck.extend(discarded_cards)

    def replace(
        self,
        discarded_cards: Iterable[Card],
    ) -> list[Card]:
        cards_to_discard = list(discarded_cards)

        # Draw first so the player cannot immediately receive
        # one of the cards they just discarded.
        replacement_cards = self.draw(
            len(cards_to_discard)
        )

        self.discard(cards_to_discard)

        return replacement_cards

    def _reshuffle_muck_into_stock(self) -> None:
        if not self.muck:
            raise RuntimeError(
                "Cannot replenish stock because the muck is empty."
            )

        self._random.shuffle(self.muck)
        self.stock.extend(self.muck)
        self.muck.clear()