from dataclasses import dataclass

from solver.actions import (
    DiscardAction,
)
from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_bucket_card_ordering,
    draw_hand_bucket,
)
from solver.hand import (
    Hand,
)


@dataclass(frozen=True)
class BucketHandEncoding:
    bucket: DrawHandBucket

    # original Hand.cards index
    # -> bucket-canonical index
    original_to_bucket: tuple[
        int,
        ...
    ]

    # bucket-canonical index
    # -> original Hand.cards index
    bucket_to_original: tuple[
        int,
        ...
    ]


def bucket_hand_encoding(
    hand: Hand,
) -> BucketHandEncoding:
    if len(hand.cards) != 5:
        raise ValueError(
            "Bucket hand encoding requires "
            "exactly five cards."
        )

    bucket_to_original = (
        draw_bucket_card_ordering(
            hand
        )
    )

    original_to_bucket_list = [
        0
        for _ in hand.cards
    ]

    for (
        bucket_index,
        original_index,
    ) in enumerate(
        bucket_to_original
    ):
        original_to_bucket_list[
            original_index
        ] = bucket_index

    return BucketHandEncoding(
        bucket=draw_hand_bucket(
            hand
        ),
        original_to_bucket=tuple(
            original_to_bucket_list
        ),
        bucket_to_original=(
            bucket_to_original
        ),
    )


def bucket_discard_action_for_hand(
    *,
    hand: Hand,
    action: DiscardAction,
) -> DiscardAction:
    """
    Convert physical Hand.cards indices into
    bucket-canonical indices.
    """
    encoding = bucket_hand_encoding(
        hand
    )

    _validate_discard_indices(
        action=action,
        hand_size=len(
            hand.cards
        ),
    )

    return DiscardAction(
        discard_indices=tuple(
            sorted(
                encoding.original_to_bucket[
                    original_index
                ]
                for original_index
                in action.discard_indices
            )
        )
    )


def actual_discard_action_for_bucket_hand(
    *,
    hand: Hand,
    action: DiscardAction,
) -> DiscardAction:
    """
    Convert bucket-canonical indices back into
    physical Hand.cards indices.
    """
    encoding = bucket_hand_encoding(
        hand
    )

    _validate_discard_indices(
        action=action,
        hand_size=len(
            hand.cards
        ),
    )

    return DiscardAction(
        discard_indices=tuple(
            sorted(
                encoding.bucket_to_original[
                    bucket_index
                ]
                for bucket_index
                in action.discard_indices
            )
        )
    )


def _validate_discard_indices(
    *,
    action: DiscardAction,
    hand_size: int,
) -> None:
    if any(
        index < 0
        or index >= hand_size
        for index
        in action.discard_indices
    ):
        raise ValueError(
            "Discard action contains an "
            "index outside the hand."
        )