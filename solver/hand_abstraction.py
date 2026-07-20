from dataclasses import dataclass
from itertools import permutations

from solver.canonical_hand import RANK_ORDER
from solver.hand import Hand


SUITS = ("c", "d", "h", "s")


@dataclass(frozen=True)
class ExactHandKey:
    cards: tuple[tuple[int, int], ...]


def exact_hand_key(
    hand: Hand,
) -> ExactHandKey:
    representations: list[
        tuple[tuple[int, int], ...]
    ] = []

    for suit_permutation in permutations(
        range(4)
    ):
        suit_mapping = {
            suit: suit_permutation[index]
            for index, suit in enumerate(SUITS)
        }

        representation = tuple(
            sorted(
                (
                    RANK_ORDER[card.rank],
                    suit_mapping[card.suit],
                )
                for card in hand.cards
            )
        )

        representations.append(representation)

    return ExactHandKey(
        cards=min(representations)
    )