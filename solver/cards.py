from dataclasses import dataclass
import random


RANKS = "23456789TJQKA"
SUITS = "shdc"


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANKS:
            raise ValueError(f"Invalid rank: {self.rank}")

        if self.suit not in SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")

    @classmethod
    def from_string(cls, value: str) -> "Card":
        if len(value) != 2:
            raise ValueError(
                f"Card must contain exactly two characters: {value}"
            )

        return cls(
            rank=value[0].upper(),
            suit=value[1].lower(),
        )

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


class Deck:
    def __init__(self) -> None:
        self.cards = [
            Card(rank, suit)
            for rank in RANKS
            for suit in SUITS
        ]

    def __len__(self) -> int:
        return len(self.cards)

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self, count: int = 1) -> list[Card]:
        if count < 0:
            raise ValueError("Draw count cannot be negative.")

        if count > len(self.cards):
            raise ValueError("Not enough cards remaining in the deck.")

        if count == 0:
            return []

        drawn_cards = self.cards[-count:]
        del self.cards[-count:]

        return drawn_cards