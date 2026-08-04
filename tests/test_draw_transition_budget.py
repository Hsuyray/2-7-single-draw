import pytest

from solver.actions import (
    DiscardAction,
)
from solver.draw_range_transition import (
    DrawTransitionBudget,
    replacement_combination_count,
    transition_exact_draw_range,
    transition_exact_hand,
)
from solver.hand import (
    Hand,
)
from solver.hand_abstraction import (
    exact_hand_key,
)


def make_hand() -> Hand:
    return Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )


def test_draw_zero_combination_count() -> None:
    hand = make_hand()

    result = replacement_combination_count(
        hand_key=exact_hand_key(
            hand
        ),
        action=DiscardAction(
            ()
        ),
    )

    assert result == 1


def test_draw_one_combination_count() -> None:
    hand = make_hand()

    result = replacement_combination_count(
        hand_key=exact_hand_key(
            hand
        ),
        action=DiscardAction(
            (4,)
        ),
    )

    assert result == 47


def test_draw_two_combination_count() -> None:
    hand = make_hand()

    result = replacement_combination_count(
        hand_key=exact_hand_key(
            hand
        ),
        action=DiscardAction(
            (3, 4)
        ),
    )

    assert result == 1081


def test_draw_three_combination_count() -> None:
    hand = make_hand()

    result = replacement_combination_count(
        hand_key=exact_hand_key(
            hand
        ),
        action=DiscardAction(
            (2, 3, 4)
        ),
    )

    assert result == 16215


def test_budget_can_reject_draw_three() -> None:
    hand = make_hand()

    budget = DrawTransitionBudget(
        max_replacement_combinations=(
            2_000
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "exceeding the configured "
            "budget"
        ),
    ):
        transition_exact_hand(
            hand=hand,
            action=DiscardAction(
                (2, 3, 4)
            ),
            budget=budget,
        )


def test_budget_can_reject_draw_two() -> None:
    hand = make_hand()

    budget = DrawTransitionBudget(
        max_replacement_combinations=(
            1_000
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "requires 1081 replacement "
            "combinations"
        ),
    ):
        transition_exact_hand(
            hand=hand,
            action=DiscardAction(
                (3, 4)
            ),
            budget=budget,
        )


def test_budget_allows_draw_one() -> None:
    hand = make_hand()

    budget = DrawTransitionBudget(
        max_replacement_combinations=100,
    )

    result = transition_exact_hand(
        hand=hand,
        action=DiscardAction(
            (4,)
        ),
        budget=budget,
    )

    assert result

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_budget_allows_exact_limit() -> None:
    hand = make_hand()

    budget = DrawTransitionBudget(
        max_replacement_combinations=47,
    )

    result = transition_exact_hand(
        hand=hand,
        action=DiscardAction(
            (4,)
        ),
        budget=budget,
    )

    assert result


def test_budget_requires_positive_replacement_limit() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "replacement combinations "
            "must be positive"
        ),
    ):
        DrawTransitionBudget(
            max_replacement_combinations=0,
        )


def test_budget_requires_positive_pair_limit() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "hand-action pairs must be "
            "positive"
        ),
    ):
        DrawTransitionBudget(
            max_hand_action_pairs=0,
        )


def test_range_transition_respects_pair_budget() -> None:
    first_hand = make_hand()

    second_hand = Hand.from_strings(
        "2d",
        "4c",
        "6h",
        "8s",
        "Qd",
    )

    first_key = exact_hand_key(
        first_hand
    )

    second_key = exact_hand_key(
        second_hand
    )

    draw_one = DiscardAction(
        (4,)
    )

    strategies = {
        first_key: {
            draw_one: 1.0,
        },
        second_key: {
            draw_one: 1.0,
        },
    }

    budget = DrawTransitionBudget(
        max_replacement_combinations=100,
        max_hand_action_pairs=1,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "hand-action pair budget"
        ),
    ):
        transition_exact_draw_range(
            pre_draw_weights={
                first_key: 1.0,
                second_key: 1.0,
            },
            strategies=strategies,
            public_draw_count=1,
            budget=budget,
        )


def test_zero_probability_action_does_not_use_pair_budget() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    result = transition_exact_draw_range(
        pre_draw_weights={
            hand_key: 1.0,
        },
        strategies={
            hand_key: {
                DiscardAction(
                    (3,)
                ): 0.0,
                DiscardAction(
                    (4,)
                ): 1.0,
            },
        },
        public_draw_count=1,
        budget=DrawTransitionBudget(
            max_replacement_combinations=100,
            max_hand_action_pairs=1,
        ),
    )

    assert result

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_zero_weight_hand_does_not_use_pair_budget() -> None:
    first_hand = make_hand()

    second_hand = Hand.from_strings(
        "2d",
        "4c",
        "6h",
        "8s",
        "Qd",
    )

    first_key = exact_hand_key(
        first_hand
    )

    second_key = exact_hand_key(
        second_hand
    )

    draw_one = DiscardAction(
        (4,)
    )

    result = transition_exact_draw_range(
        pre_draw_weights={
            first_key: 1.0,
            second_key: 0.0,
        },
        strategies={
            first_key: {
                draw_one: 1.0,
            },
            second_key: {
                draw_one: 1.0,
            },
        },
        public_draw_count=1,
        budget=DrawTransitionBudget(
            max_replacement_combinations=100,
            max_hand_action_pairs=1,
        ),
    )

    assert result

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )