from itertools import combinations

from solver.actions import DiscardAction
from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand import Hand


def generate_discard_actions(
    *,
    hand_size: int = 5,
    max_draw: int = 3,
) -> tuple[DiscardAction, ...]:
    """
    Generate the complete discard action space.

    For a five-card hand with max_draw=3:
        stand pat: 1
        draw one: 5
        draw two: 10
        draw three: 10
        total: 26
    """
    _validate_draw_parameters(
        hand_size=hand_size,
        max_draw=max_draw,
    )

    actions: list[DiscardAction] = []

    for draw_count in range(
        max_draw + 1
    ):
        for discard_indices in combinations(
            range(hand_size),
            draw_count,
        ):
            actions.append(
                DiscardAction(
                    discard_indices
                )
            )

    return tuple(actions)


def candidate_discard_actions(
    hand: Hand,
    *,
    max_draw: int = 3,
    draw_two_candidates: int = 3,
    draw_three_candidates: int = 3,
) -> tuple[DiscardAction, ...]:
    """
    Generate a reduced, bucket-consistent action set.

    Hands assigned to the same DrawHandBucket will
    always receive the same discard actions.

    The candidate set contains:
        - stand pat
        - all five one-card discards
        - selected two-card discards
        - selected three-card discards
    """
    hand_size = len(hand.cards)

    _validate_draw_parameters(
        hand_size=hand_size,
        max_draw=max_draw,
    )

    if hand_size != 5:
        raise ValueError(
            "Candidate discard abstraction "
            "requires a five-card hand."
        )

    if draw_two_candidates < 0:
        raise ValueError(
            "draw_two_candidates cannot "
            "be negative."
        )

    if draw_three_candidates < 0:
        raise ValueError(
            "draw_three_candidates cannot "
            "be negative."
        )

    bucket = draw_hand_bucket(hand)

    full_actions = generate_discard_actions(
        hand_size=hand_size,
        max_draw=max_draw,
    )

    selected_actions: set[
        DiscardAction
    ] = {
        DiscardAction(())
    }

    # Preserve every one-card discard.
    if max_draw >= 1:
        selected_actions.update(
            action
            for action in full_actions
            if action.draw_count == 1
        )

    if max_draw >= 2:
        selected_actions.update(
            _best_bucket_actions(
                bucket,
                full_actions,
                draw_count=2,
                candidate_count=(
                    draw_two_candidates
                ),
            )
        )

    if max_draw >= 3:
        selected_actions.update(
            _best_bucket_actions(
                bucket,
                full_actions,
                draw_count=3,
                candidate_count=(
                    draw_three_candidates
                ),
            )
        )

    # Preserve deterministic ordering.
    return tuple(
        action
        for action in full_actions
        if action in selected_actions
    )


def _best_bucket_actions(
    bucket: DrawHandBucket,
    actions: tuple[DiscardAction, ...],
    *,
    draw_count: int,
    candidate_count: int,
) -> tuple[DiscardAction, ...]:
    if candidate_count == 0:
        return ()

    matching_actions = (
        action
        for action in actions
        if action.draw_count == draw_count
    )

    ranked_actions = sorted(
        matching_actions,
        key=lambda action: (
            _bucket_keep_score(
                bucket,
                action,
            ),
            action.discard_indices,
        ),
    )

    return tuple(
        ranked_actions[:candidate_count]
    )


def _bucket_keep_score(
    bucket: DrawHandBucket,
    action: DiscardAction,
) -> tuple[
    int,
    int,
    tuple[int, ...],
    int,
]:
    """
    Score the cards retained after a discard using
    only information stored in DrawHandBucket.

    Lower tuples are preferred.
    """
    discarded_indices = set(
        action.discard_indices
    )

    kept_indices = tuple(
        index
        for index in range(
            len(bucket.rank_classes)
        )
        if index not in discarded_indices
    )

    kept_rank_classes = tuple(
        bucket.rank_classes[index]
        for index in kept_indices
    )

    kept_multiplicities = tuple(
        bucket.rank_multiplicities[index]
        for index in kept_indices
    )

    kept_flush_flags = tuple(
        bucket.flush_risk_positions[index]
        for index in kept_indices
    )

    # Penalize retaining duplicated ranks.
    duplicate_penalty = sum(
        multiplicity - 1
        for multiplicity
        in kept_multiplicities
        if multiplicity > 1
    )

    # Penalize retaining cards involved in a known
    # four-card or five-card flush structure.
    flush_penalty = sum(
        kept_flush_flags
    )

    # Compare retained lowball ranks from high to low.
    high_to_low_classes = tuple(
        sorted(
            kept_rank_classes,
            reverse=True,
        )
    )

    return (
        duplicate_penalty,
        flush_penalty,
        high_to_low_classes,
        sum(kept_rank_classes),
    )


def _validate_draw_parameters(
    *,
    hand_size: int,
    max_draw: int,
) -> None:
    if hand_size < 0:
        raise ValueError(
            "Hand size cannot be negative."
        )

    if max_draw < 0:
        raise ValueError(
            "Maximum draw cannot be negative."
        )

    if max_draw > hand_size:
        raise ValueError(
            "Maximum draw cannot exceed "
            "hand size."
        )