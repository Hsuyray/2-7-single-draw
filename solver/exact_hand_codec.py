from solver.actions import (
    DiscardAction,
)
from solver.canonical_hand import (
    RANK_ORDER,
    canonicalize_hand,
)
from solver.cards import (
    Card,
)
from solver.hand import (
    Hand,
)
from solver.hand_abstraction import (
    SUITS,
    ExactHandEncoding,
    ExactHandKey,
    exact_hand_encoding,
)


RANK_FROM_VALUE = {
    value: rank
    for rank, value
    in RANK_ORDER.items()
}


def exact_hand_from_key(
    hand_key: ExactHandKey,
) -> Hand:
    """
    Construct the deterministic canonical
    representative of an ExactHandKey.

    Canonical suit indices map to:

        0 -> clubs
        1 -> diamonds
        2 -> hearts
        3 -> spades
    """
    cards: list[Card] = []

    for (
        rank_value,
        suit_index,
    ) in hand_key.cards:
        rank = RANK_FROM_VALUE.get(
            rank_value
        )

        if rank is None:
            raise ValueError(
                "Exact hand key contains an "
                f"unknown rank value: "
                f"{rank_value}"
            )

        if not (
            0
            <= suit_index
            < len(SUITS)
        ):
            raise ValueError(
                "Exact hand key contains an "
                f"invalid suit index: "
                f"{suit_index}"
            )

        cards.append(
            Card(
                rank=rank,
                suit=SUITS[
                    suit_index
                ],
            )
        )

    return canonicalize_hand(
        Hand(
            tuple(cards)
        )
    )


def canonical_discard_action_for_hand(
    *,
    hand: Hand,
    action: DiscardAction,
) -> DiscardAction:
    """
    Convert discard indices referring to the
    current Hand.cards ordering into indices
    referring to the canonical ExactHandKey
    ordering.
    """
    encoding = exact_hand_encoding(
        hand
    )

    action.validate_for_hand_size(
        len(hand.cards)
    )

    canonical_indices = tuple(
        sorted(
            encoding.original_to_canonical[
                original_index
            ]
            for original_index
            in action.discard_indices
        )
    )

    return DiscardAction(
        canonical_indices
    )


def actual_discard_action_for_hand(
    *,
    hand: Hand,
    action: DiscardAction,
) -> DiscardAction:
    """
    Convert canonical ExactHandKey discard
    indices into indices referring to the
    current Hand.cards ordering.
    """
    encoding = exact_hand_encoding(
        hand
    )

    action.validate_for_hand_size(
        len(hand.cards)
    )

    original_indices = tuple(
        sorted(
            encoding.canonical_to_original[
                canonical_index
            ]
            for canonical_index
            in action.discard_indices
        )
    )

    return DiscardAction(
        original_indices
    )


def exact_hand_index_encoding(
    hand: Hand,
) -> ExactHandEncoding:
    """
    Public codec alias for retrieving both
    the exact hand key and card-index
    mappings.
    """
    return exact_hand_encoding(
        hand
    )