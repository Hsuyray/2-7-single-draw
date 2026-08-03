from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.bet_sizing_profiles import (
    FAST_BET_SIZING,
    FULL_BET_SIZING,
)


def test_fast_profile_is_policy() -> None:
    assert isinstance(
        FAST_BET_SIZING,
        BetSizingPolicy,
    )


def test_full_profile_is_policy() -> None:
    assert isinstance(
        FULL_BET_SIZING,
        BetSizingPolicy,
    )


def test_fast_profile_uses_reduced_tree() -> None:
    assert (
        FAST_BET_SIZING.pot_fractions
        == (
            0.33,
            0.66,
            1.00,
        )
    )


def test_full_profile_contains_requested_sizes() -> None:
    assert (
        FULL_BET_SIZING.pot_fractions
        == (
            0.20,
            0.33,
            0.50,
            0.66,
            0.90,
            1.00,
            1.25,
        )
    )


def test_both_profiles_include_all_in() -> None:
    assert (
        FAST_BET_SIZING.include_all_in
        is True
    )

    assert (
        FULL_BET_SIZING.include_all_in
        is True
    )