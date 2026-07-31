from itertools import islice

from solver.draw_hand_bucket import (
    DrawHandBucket,
)
from solver.hand_abstraction import (
    ExactHandKey,
)
from solver.hand_universe import (
    iter_starting_hands,
)
from solver.starting_range_builder import (
    StartingRangeBuilder,
)


def sample_hands(
    count: int = 100,
):
    return list(
        islice(
            iter_starting_hands(),
            count,
        )
    )


def test_exact_builder_preserves_raw_count() -> None:
    hands = sample_hands(
        100
    )

    builder = StartingRangeBuilder(
        abstraction="exact"
    )

    starting_range = (
        builder.build_from_hands(
            hands
        )
    )

    assert (
        starting_range.total_weight
        == 100.0
    )


def test_exact_builder_produces_exact_keys() -> None:
    hands = sample_hands(
        100
    )

    builder = StartingRangeBuilder(
        abstraction="exact"
    )

    starting_range = (
        builder.build_from_hands(
            hands
        )
    )

    assert all(
        isinstance(
            hand_key,
            ExactHandKey,
        )
        for hand_key
        in starting_range.weights
    )


def test_bucket_builder_preserves_raw_count() -> None:
    hands = sample_hands(
        100
    )

    builder = StartingRangeBuilder(
        abstraction="bucket"
    )

    starting_range = (
        builder.build_from_hands(
            hands
        )
    )

    assert (
        starting_range.total_weight
        == 100.0
    )


def test_bucket_builder_produces_draw_buckets() -> None:
    hands = sample_hands(
        100
    )

    builder = StartingRangeBuilder(
        abstraction="bucket"
    )

    starting_range = (
        builder.build_from_hands(
            hands
        )
    )

    assert all(
        isinstance(
            hand_key,
            DrawHandBucket,
        )
        for hand_key
        in starting_range.weights
    )


def test_bucket_abstraction_merges_raw_hands() -> None:
    hands = sample_hands(
        500
    )

    builder = StartingRangeBuilder(
        abstraction="bucket"
    )

    starting_range = (
        builder.build_from_hands(
            hands
        )
    )

    assert (
        starting_range.hand_count
        < len(hands)
    )


def test_normalized_exact_range_sums_to_one() -> None:
    hands = sample_hands(
        100
    )

    builder = StartingRangeBuilder(
        abstraction="exact"
    )

    starting_range = (
        builder.build_from_hands(
            hands
        )
    )

    normalized = (
        starting_range.normalized()
    )

    assert abs(
        sum(normalized.values())
        - 1.0
    ) < 1e-9