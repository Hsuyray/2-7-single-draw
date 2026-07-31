import pytest

from solver.bet_sizing import (
    BetSizingPolicy,
)


def make_policy() -> BetSizingPolicy:
    return BetSizingPolicy()


def test_open_bet_sizes_are_pot_fractions() -> None:
    policy = make_policy()

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=0.0,
        stack=20.0,
        amount_to_call=0.0,
        minimum_raise_to=2.0,
        maximum_raise_to=20.0,
    )

    assert sizes == (
        2.0,
        3.3,
        5.0,
        6.6,
        9.0,
        10.0,
        12.5,
        20.0,
    )


def test_sizes_above_stack_are_removed() -> None:
    policy = make_policy()

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=0.0,
        stack=7.0,
        amount_to_call=0.0,
        minimum_raise_to=2.0,
        maximum_raise_to=7.0,
    )

    assert sizes == (
        2.0,
        3.3,
        5.0,
        7.0,
    )


def test_near_all_in_size_collapses_to_jam() -> None:
    policy = BetSizingPolicy(
        pot_fractions=(
            0.50,
            0.90,
            1.00,
        ),
        include_all_in=True,
        all_in_threshold=0.90,
    )

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=0.0,
        stack=10.0,
        amount_to_call=0.0,
        minimum_raise_to=2.0,
        maximum_raise_to=10.0,
    )

    assert sizes == (
        5.0,
        10.0,
    )


def test_all_in_is_added_even_when_not_a_fraction() -> None:
    policy = BetSizingPolicy(
        pot_fractions=(
            0.50,
            1.00,
        ),
    )

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=0.0,
        stack=17.0,
        amount_to_call=0.0,
        minimum_raise_to=2.0,
        maximum_raise_to=17.0,
    )

    assert sizes == (
        5.0,
        10.0,
        17.0,
    )


def test_can_disable_all_in() -> None:
    policy = BetSizingPolicy(
        pot_fractions=(
            0.50,
            1.00,
        ),
        include_all_in=False,
    )

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=0.0,
        stack=17.0,
        amount_to_call=0.0,
        minimum_raise_to=2.0,
        maximum_raise_to=17.0,
    )

    assert sizes == (
        5.0,
        10.0,
    )


def test_minimum_raise_filters_small_sizes() -> None:
    policy = make_policy()

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=0.0,
        stack=20.0,
        amount_to_call=0.0,
        minimum_raise_to=5.0,
        maximum_raise_to=20.0,
    )

    assert sizes == (
        5.0,
        6.6,
        9.0,
        10.0,
        12.5,
        20.0,
    )


def test_facing_bet_uses_pot_after_call() -> None:
    policy = BetSizingPolicy(
        pot_fractions=(
            0.50,
            1.00,
        ),
        include_all_in=False,
    )

    sizes = policy.raise_to_candidates(
        pot=15.0,
        committed_this_round=0.0,
        stack=100.0,
        amount_to_call=5.0,
        minimum_raise_to=10.0,
        maximum_raise_to=100.0,
    )

    # Pot after call = 20.
    #
    # 50% raise:
    # call 5 + 50% * 20 = 15 raise-to.
    #
    # 100% raise:
    # call 5 + 100% * 20 = 25 raise-to.
    assert sizes == (
        15.0,
        25.0,
    )


def test_facing_bet_accounts_for_existing_commitment() -> None:
    policy = BetSizingPolicy(
        pot_fractions=(
            1.00,
        ),
        include_all_in=False,
    )

    sizes = policy.raise_to_candidates(
        pot=15.0,
        committed_this_round=2.0,
        stack=98.0,
        amount_to_call=3.0,
        minimum_raise_to=8.0,
        maximum_raise_to=100.0,
    )

    # Current commitment = 2
    # Call = 3
    # Pot after call = 18
    #
    # Raise-to = 2 + 3 + 18 = 23.
    assert sizes == (
        23.0,
    )


def test_duplicate_sizes_are_removed() -> None:
    policy = BetSizingPolicy(
        pot_fractions=(
            0.90,
            1.00,
            1.25,
        ),
        all_in_threshold=0.90,
    )

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=0.0,
        stack=10.0,
        amount_to_call=0.0,
        minimum_raise_to=2.0,
        maximum_raise_to=10.0,
    )

    assert sizes == (
        10.0,
    )


def test_chip_sizes_are_rounded_to_tenths() -> None:
    policy = BetSizingPolicy(
        pot_fractions=(
            0.33,
        ),
        include_all_in=False,
        chip_increment=0.1,
    )

    sizes = policy.raise_to_candidates(
        pot=7.0,
        committed_this_round=0.0,
        stack=100.0,
        amount_to_call=0.0,
        minimum_raise_to=1.0,
        maximum_raise_to=100.0,
    )

    assert sizes == (
        2.3,
    )


def test_zero_stack_has_no_raise_sizes() -> None:
    policy = make_policy()

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=10.0,
        stack=0.0,
        amount_to_call=0.0,
        minimum_raise_to=12.0,
        maximum_raise_to=10.0,
    )

    assert sizes == ()


def test_no_raise_available_when_maximum_is_only_call() -> None:
    policy = make_policy()

    sizes = policy.raise_to_candidates(
        pot=10.0,
        committed_this_round=2.0,
        stack=3.0,
        amount_to_call=3.0,
        minimum_raise_to=8.0,
        maximum_raise_to=5.0,
    )

    assert sizes == ()


def test_negative_pot_is_rejected() -> None:
    policy = make_policy()

    with pytest.raises(
        ValueError
    ):
        policy.raise_to_candidates(
            pot=-1.0,
            committed_this_round=0.0,
            stack=100.0,
            amount_to_call=0.0,
            minimum_raise_to=2.0,
            maximum_raise_to=100.0,
        )


def test_invalid_fraction_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        BetSizingPolicy(
            pot_fractions=(
                0.50,
                0.0,
            )
        )


def test_invalid_all_in_threshold_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        BetSizingPolicy(
            all_in_threshold=1.1
        )