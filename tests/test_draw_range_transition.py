import pytest

from solver.actions import (
    DiscardAction,
)
from solver.draw_range_transition import (
    clear_draw_transition_cache,
    draw_transition_cache_info,
    transition_exact_draw_range,
    transition_exact_hand,
    transition_exact_key,
)
from solver.hand import (
    Hand,
)
from solver.hand_abstraction import (
    exact_hand_key,
)


def test_stand_pat_returns_same_hand() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    hand_key = exact_hand_key(
        hand
    )

    result = transition_exact_hand(
        hand=hand,
        action=DiscardAction(
            ()
        ),
    )

    assert result == {
        hand_key: pytest.approx(
            1.0
        ),
    }


def test_draw_one_distribution_sums_to_one() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    result = transition_exact_hand(
        hand=hand,
        action=DiscardAction(
            (4,)
        ),
    )

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_draw_one_cannot_redraw_discarded_card() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    result = transition_exact_hand(
        hand=hand,
        action=DiscardAction(
            (4,)
        ),
    )

    original_key = exact_hand_key(
        hand
    )

    assert (
        original_key
        not in result
    )


def test_draw_two_distribution_sums_to_one() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    result = transition_exact_hand(
        hand=hand,
        action=DiscardAction(
            (3, 4)
        ),
    )

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_range_transition_uses_selected_draw_count() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    hand_key = exact_hand_key(
        hand
    )

    stand_pat = DiscardAction(
        ()
    )

    draw_one = DiscardAction(
        (4,)
    )

    strategies = {
        hand_key: {
            stand_pat: 0.25,
            draw_one: 0.75,
        }
    }

    result = transition_exact_draw_range(
        pre_draw_weights={
            hand_key: 1.0,
        },
        strategies=strategies,
        public_draw_count=0,
        normalize=False,
    )

    assert result == {
        hand_key: pytest.approx(
            0.25
        ),
    }


def test_range_transition_normalizes_result() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    hand_key = exact_hand_key(
        hand
    )

    strategies = {
        hand_key: {
            DiscardAction(
                (4,)
            ): 0.50,
        }
    }

    result = transition_exact_draw_range(
        pre_draw_weights={
            hand_key: 2.0,
        },
        strategies=strategies,
        public_draw_count=1,
        normalize=True,
    )

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_range_transition_preserves_reach_without_normalization() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    hand_key = exact_hand_key(
        hand
    )

    strategies = {
        hand_key: {
            DiscardAction(
                (4,)
            ): 0.25,
        }
    }

    result = transition_exact_draw_range(
        pre_draw_weights={
            hand_key: 2.0,
        },
        strategies=strategies,
        public_draw_count=1,
        normalize=False,
    )

    assert (
        sum(result.values())
        == pytest.approx(0.5)
    )


def test_multiple_private_patterns_are_combined() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    hand_key = exact_hand_key(
        hand
    )

    strategies = {
        hand_key: {
            DiscardAction(
                (3,)
            ): 0.20,
            DiscardAction(
                (4,)
            ): 0.30,
            DiscardAction(
                ()
            ): 0.50,
        }
    }

    result = transition_exact_draw_range(
        pre_draw_weights={
            hand_key: 1.0,
        },
        strategies=strategies,
        public_draw_count=1,
        normalize=False,
    )

    assert (
        sum(result.values())
        == pytest.approx(0.50)
    )


def test_invalid_public_draw_count_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        transition_exact_draw_range(
            pre_draw_weights={},
            strategies={},
            public_draw_count=6,
        )


def test_negative_range_weight_is_rejected() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    hand_key = exact_hand_key(
        hand
    )

    with pytest.raises(
        ValueError
    ):
        transition_exact_draw_range(
            pre_draw_weights={
                hand_key: -1.0,
            },
            strategies={},
            public_draw_count=1,
        )


def test_exact_transition_uses_cache() -> None:
    clear_draw_transition_cache()

    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    action = DiscardAction(
        (4,)
    )

    transition_exact_hand(
        hand=hand,
        action=action,
    )

    first_info = (
        draw_transition_cache_info()
    )

    transition_exact_hand(
        hand=hand,
        action=action,
    )

    second_info = (
        draw_transition_cache_info()
    )

    assert second_info.hits == (
        first_info.hits + 1
    )

    assert second_info.misses == (
        first_info.misses
    )


def test_suit_isomorphic_hands_share_cache_entry() -> None:
    clear_draw_transition_cache()

    first = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    second = Hand.from_strings(
        "2d",
        "3h",
        "5s",
        "7c",
        "Kd",
    )

    assert (
        exact_hand_key(first)
        == exact_hand_key(second)
    )

    action = DiscardAction(
        (4,)
    )

    transition_exact_hand(
        hand=first,
        action=action,
    )

    first_info = (
        draw_transition_cache_info()
    )

    transition_exact_hand(
        hand=second,
        action=action,
    )

    second_info = (
        draw_transition_cache_info()
    )

    assert second_info.hits == (
        first_info.hits + 1
    )


def test_cached_result_cannot_be_mutated() -> None:
    clear_draw_transition_cache()

    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    action = DiscardAction(
        (4,)
    )

    first_result = (
        transition_exact_hand(
            hand=hand,
            action=action,
        )
    )

    first_key = next(
        iter(first_result)
    )

    first_result[
        first_key
    ] = 999.0

    second_result = (
        transition_exact_hand(
            hand=hand,
            action=action,
        )
    )

    assert (
        second_result[first_key]
        != 999.0
    )

    assert (
        sum(second_result.values())
        == pytest.approx(1.0)
    )


def test_transition_exact_key_matches_hand_api() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    hand_key = exact_hand_key(
        hand
    )

    action = DiscardAction(
        (4,)
    )

    from_hand = transition_exact_hand(
        hand=hand,
        action=action,
    )

    from_key = transition_exact_key(
        hand_key=hand_key,
        action=action,
    )

    assert from_key == from_hand