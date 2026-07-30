from itertools import islice

from solver.hand_abstraction import (
    ExactHandKey,
)
from solver.hand_universe import (
    count_exact_keys,
    iter_starting_hands,
    total_exact_key_combinations,
)


def test_count_exact_keys_preserves_raw_hand_count() -> None:
    hands = list(
        islice(
            iter_starting_hands(),
            100,
        )
    )

    counts = count_exact_keys(
        hands
    )

    assert (
        total_exact_key_combinations(
            counts
        )
        == 100
    )


def test_exact_key_counts_have_positive_multiplicity() -> None:
    hands = list(
        islice(
            iter_starting_hands(),
            100,
        )
    )

    counts = count_exact_keys(
        hands
    )

    assert counts

    assert all(
        isinstance(
            key,
            ExactHandKey,
        )
        for key in counts
    )

    assert all(
        count > 0
        for count in counts.values()
    )


def test_canonical_exact_keys_can_represent_multiple_raw_hands() -> None:
    hands = list(
        islice(
            iter_starting_hands(),
            100,
        )
    )

    counts = count_exact_keys(
        hands
    )

    assert any(
        count > 1
        for count in counts.values()
    )


def test_exact_key_count_cannot_exceed_raw_hand_count() -> None:
    hands = list(
        islice(
            iter_starting_hands(),
            250,
        )
    )

    counts = count_exact_keys(
        hands
    )

    assert (
        len(counts)
        <= len(hands)
    )