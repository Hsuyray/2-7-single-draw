from dataclasses import dataclass
from itertools import permutations

from solver.canonical_hand import (
    RANK_ORDER,
)
from solver.hand import (
    Hand,
)


SUITS = (
    "c",
    "d",
    "h",
    "s",
)


@dataclass(frozen=True)
class ExactHandKey:
    """
    Suit-isomorphic canonical representation
    of an exact five-card hand.

    Each card is stored as:

        (rank_value, canonical_suit_index)
    """

    cards: tuple[
        tuple[int, int],
        ...,
    ]


@dataclass(frozen=True)
class ExactHandEncoding:
    """
    ExactHandKey plus card-index mappings.

    original_to_canonical:
        original Hand.cards index
        -> ExactHandKey.cards index

    canonical_to_original:
        ExactHandKey.cards index
        -> original Hand.cards index
    """

    key: ExactHandKey

    original_to_canonical: tuple[
        int,
        ...,
    ]

    canonical_to_original: tuple[
        int,
        ...,
    ]

    def __post_init__(self) -> None:
        card_count = len(
            self.key.cards
        )

        if len(
            self.original_to_canonical
        ) != card_count:
            raise ValueError(
                "original_to_canonical must "
                "contain one index per card."
            )

        if len(
            self.canonical_to_original
        ) != card_count:
            raise ValueError(
                "canonical_to_original must "
                "contain one index per card."
            )

        expected_indices = tuple(
            range(card_count)
        )

        if tuple(
            sorted(
                self.original_to_canonical
            )
        ) != expected_indices:
            raise ValueError(
                "original_to_canonical must "
                "be a permutation of all "
                "card indices."
            )

        if tuple(
            sorted(
                self.canonical_to_original
            )
        ) != expected_indices:
            raise ValueError(
                "canonical_to_original must "
                "be a permutation of all "
                "card indices."
            )

        for (
            original_index,
            canonical_index,
        ) in enumerate(
            self.original_to_canonical
        ):
            if (
                self.canonical_to_original[
                    canonical_index
                ]
                != original_index
            ):
                raise ValueError(
                    "Exact hand index mappings "
                    "must be inverses."
                )


def exact_hand_encoding(
    hand: Hand,
) -> ExactHandEncoding:
    """
    Canonicalize an exact hand under every
    possible suit permutation.

    In addition to the canonical key, retain
    mappings between the current Hand.cards
    ordering and the canonical key ordering.
    """
    best_candidate: tuple[
        tuple[
            tuple[int, int],
            ...,
        ],
        tuple[int, ...],
        tuple[int, ...],
    ] | None = None

    for suit_permutation in permutations(
        range(4)
    ):
        suit_mapping = {
            suit: suit_permutation[index]
            for index, suit
            in enumerate(SUITS)
        }

        transformed_cards = [
            (
                RANK_ORDER[card.rank],
                suit_mapping[card.suit],
                original_index,
            )
            for original_index, card
            in enumerate(hand.cards)
        ]

        transformed_cards.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            )
        )

        representation = tuple(
            (
                rank_value,
                canonical_suit,
            )
            for (
                rank_value,
                canonical_suit,
                _,
            ) in transformed_cards
        )

        canonical_to_original = tuple(
            original_index
            for (
                _,
                _,
                original_index,
            ) in transformed_cards
        )

        original_to_canonical_list = [
            0
            for _ in hand.cards
        ]

        for (
            canonical_index,
            original_index,
        ) in enumerate(
            canonical_to_original
        ):
            original_to_canonical_list[
                original_index
            ] = canonical_index

        original_to_canonical = tuple(
            original_to_canonical_list
        )

        candidate = (
            representation,
            original_to_canonical,
            canonical_to_original,
        )

        if (
            best_candidate is None
            or candidate < best_candidate
        ):
            best_candidate = candidate

    if best_candidate is None:
        raise RuntimeError(
            "Unable to canonicalize exact hand."
        )

    (
        representation,
        original_to_canonical,
        canonical_to_original,
    ) = best_candidate

    return ExactHandEncoding(
        key=ExactHandKey(
            cards=representation
        ),
        original_to_canonical=(
            original_to_canonical
        ),
        canonical_to_original=(
            canonical_to_original
        ),
    )


def exact_hand_key(
    hand: Hand,
) -> ExactHandKey:
    """
    Backward-compatible helper returning
    only the canonical exact hand key.
    """
    return exact_hand_encoding(
        hand
    ).key