from dataclasses import dataclass

from solver.cards import Card
from solver.hand_evaluator import evaluate_hand


@dataclass(frozen=True)
class PartialHand:
    cards: tuple[Card, ...]

    def __post_init__(self) -> None:
        if len(self.cards) > 5:
            raise ValueError(
                "A partial hand cannot contain more than five cards."
            )

        if len(set(self.cards)) != len(self.cards):
            raise ValueError(
                "A partial hand cannot contain duplicate cards."
            )

    def complete(self, new_cards: list[Card]) -> "Hand":
        combined_cards = self.cards + tuple(new_cards)

        if len(combined_cards) != 5:
            raise ValueError(
                "Completed hand must contain exactly five cards."
            )

        return Hand(combined_cards)


@dataclass(frozen=True)
class Hand:
    cards: tuple[Card, ...]

    def __post_init__(self) -> None:
        if len(self.cards) != 5:
            raise ValueError("A hand must contain exactly five cards.")

        if len(set(self.cards)) != 5:
            raise ValueError("A hand cannot contain duplicate cards.")

    @classmethod
    def from_strings(cls, *values: str) -> "Hand":
        cards = tuple(Card.from_string(value) for value in values)
        return cls(cards)

    @property
    def score(self) -> tuple[int, ...]:
        return evaluate_hand(list(self.cards))

    def discard(
        self,
        indices: list[int],
    ) -> tuple[PartialHand, tuple[Card, ...]]:
        if len(set(indices)) != len(indices):
            raise ValueError(
                "Discard indices cannot contain duplicates."
            )

        if any(index < 0 or index >= 5 for index in indices):
            raise IndexError(
                "Discard index must be between 0 and 4."
            )

        discard_set = set(indices)

        kept_cards = tuple(
            card
            for index, card in enumerate(self.cards)
            if index not in discard_set
        )

        discarded_cards = tuple(
            card
            for index, card in enumerate(self.cards)
            if index in discard_set
        )

        return PartialHand(kept_cards), discarded_cards

    def __str__(self) -> str:
        return " ".join(str(card) for card in self.cards)