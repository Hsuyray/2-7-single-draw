"""
Coarse groupings of responder information states for grouped
SampledBestResponse (docs/A2_DESIGN.md section 12, option A).

A group key may depend only on the responder's own information,
so a response that plays one action per group is a legal
strategy and its gain is a lower bound on exploitability.

coarse_grouping(state, actions) =
    (observer seat, public node, coarse hand class, actions)

Coarse hand classes:

  postdraw  PostdrawStrengthBucket.bucket_id runs 0 (best,
            7-5-4-3-2) to 127 (worst) in strength order; eight
            consecutive buckets form one class (16 classes).

  predraw / draw  from DrawHandBucket:
            ("straight_or_flush",)
            ("no_pair", highest rank class, low cards)
            ("one_pair", unpaired low cards)
            ("worse_than_pair",)       two pair or worse
            where rank classes are 2-3, 4-5, 6-7, 8-9, T-J, Q-K-A
            (0..5) and a "low card" is 7 or lower (class <= 2).

Other hand keys (exact abstraction) fall back to the key itself,
which makes the grouping per information set for them.
"""

from collections.abc import Hashable

from solver.draw_hand_bucket import (
    DrawHandBucket,
)
from solver.information_state import (
    InformationState,
)
from solver.legal_actions import (
    SolverAction,
)
from solver.postdraw_strength_bucket import (
    POSTDRAW_BUCKET_COUNT,
    PostdrawStrengthBucket,
)


POSTDRAW_CLASS_COUNT = 16

LOW_RANK_CLASS_MAX = 2


def coarse_hand_class(
    hand_key,
) -> Hashable:
    if isinstance(
        hand_key,
        PostdrawStrengthBucket,
    ):
        return (
            "postdraw",
            hand_key.bucket_id
            * POSTDRAW_CLASS_COUNT
            // POSTDRAW_BUCKET_COUNT,
        )

    if isinstance(
        hand_key,
        DrawHandBucket,
    ):
        return _draw_class(hand_key)

    return hand_key


def _draw_class(
    bucket: DrawHandBucket,
) -> tuple:
    if bucket.is_straight or bucket.is_flush:
        return ("straight_or_flush",)

    if bucket.unique_rank_count == 5:
        low_cards = sum(
            1
            for rank_class in bucket.rank_classes
            if rank_class <= LOW_RANK_CLASS_MAX
        )

        return (
            "no_pair",
            max(bucket.rank_classes),
            low_cards,
        )

    if bucket.unique_rank_count == 4:
        unpaired_low = sum(
            1
            for rank_class, multiplicity in zip(
                bucket.rank_classes,
                bucket.rank_multiplicities,
            )
            if multiplicity == 1
            and rank_class <= LOW_RANK_CLASS_MAX
        )

        return (
            "one_pair",
            unpaired_low,
        )

    return ("worse_than_pair",)


def coarse_grouping(
    state: InformationState,
    actions: tuple[
        SolverAction,
        ...,
    ],
) -> Hashable:
    return (
        state.observer_seat,
        state.public_node,
        coarse_hand_class(
            state.own_hand_key
        ),
        actions,
    )
