import pytest

from solver.actions import (
    DiscardAction,
)
from solver.draw_range_sampling import (
    DrawSamplingConfig,
)
from solver.draw_range_transition import (
    DrawTransitionBudget,
)
from solver.draw_transition_policy import (
    DrawTransitionConfig,
    DrawTransitionResult,
    transition_draw_range,
)
from solver.hand import (
    Hand,
)
from solver.hand_abstraction import (
    ExactHandKey,
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


def make_inputs(
    *,
    draw_count: int,
) -> tuple[
    dict[ExactHandKey, float],
    dict,
]:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    discard_indices = tuple(
        range(
            5 - draw_count,
            5,
        )
    )

    action = DiscardAction(
        discard_indices
    )

    return (
        {
            hand_key: 1.0,
        },
        {
            hand_key: {
                action: 1.0,
            },
        },
    )


def test_exact_mode_uses_exact_transition() -> None:
    (
        weights,
        strategies,
    ) = make_inputs(
        draw_count=1
    )

    result = transition_draw_range(
        pre_draw_weights=weights,
        strategies=strategies,
        public_draw_count=1,
        config=DrawTransitionConfig(
            mode="exact",
            exact_budget=(
                DrawTransitionBudget(
                    max_replacement_combinations=100,
                )
            ),
        ),
    )

    assert isinstance(
        result,
        DrawTransitionResult,
    )

    assert result.method == "exact"

    assert (
        result.total_weight
        == pytest.approx(1.0)
    )


def test_sample_mode_uses_sampling() -> None:
    (
        weights,
        strategies,
    ) = make_inputs(
        draw_count=1
    )

    result = transition_draw_range(
        pre_draw_weights=weights,
        strategies=strategies,
        public_draw_count=1,
        config=DrawTransitionConfig(
            mode="sample",
            sampling=DrawSamplingConfig(
                samples_per_hand_action=100,
                seed=1,
            ),
        ),
    )

    assert result.method == "sample"

    assert (
        result.total_weight
        == pytest.approx(1.0)
    )


def test_auto_mode_prefers_exact_when_allowed() -> None:
    (
        weights,
        strategies,
    ) = make_inputs(
        draw_count=1
    )

    result = transition_draw_range(
        pre_draw_weights=weights,
        strategies=strategies,
        public_draw_count=1,
        config=DrawTransitionConfig(
            mode="auto",
            exact_budget=(
                DrawTransitionBudget(
                    max_replacement_combinations=100,
                )
            ),
            sampling=DrawSamplingConfig(
                samples_per_hand_action=100,
                seed=1,
            ),
        ),
    )

    assert result.method == "exact"


def test_auto_mode_falls_back_to_sampling() -> None:
    (
        weights,
        strategies,
    ) = make_inputs(
        draw_count=2
    )

    result = transition_draw_range(
        pre_draw_weights=weights,
        strategies=strategies,
        public_draw_count=2,
        config=DrawTransitionConfig(
            mode="auto",
            exact_budget=(
                DrawTransitionBudget(
                    max_replacement_combinations=100,
                )
            ),
            sampling=DrawSamplingConfig(
                samples_per_hand_action=200,
                seed=7,
            ),
        ),
    )

    assert result.method == "sample"

    assert result.weights

    assert (
        result.total_weight
        == pytest.approx(1.0)
    )


def test_exact_mode_does_not_fall_back() -> None:
    (
        weights,
        strategies,
    ) = make_inputs(
        draw_count=2
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "exceeding the configured "
            "budget"
        ),
    ):
        transition_draw_range(
            pre_draw_weights=weights,
            strategies=strategies,
            public_draw_count=2,
            config=DrawTransitionConfig(
                mode="exact",
                exact_budget=(
                    DrawTransitionBudget(
                        max_replacement_combinations=100,
                    )
                ),
            ),
        )


def test_sampling_is_deterministic_through_policy() -> None:
    (
        weights,
        strategies,
    ) = make_inputs(
        draw_count=2
    )

    config = DrawTransitionConfig(
        mode="sample",
        sampling=DrawSamplingConfig(
            samples_per_hand_action=200,
            seed=42,
        ),
    )

    first = transition_draw_range(
        pre_draw_weights=weights,
        strategies=strategies,
        public_draw_count=2,
        config=config,
    )

    second = transition_draw_range(
        pre_draw_weights=weights,
        strategies=strategies,
        public_draw_count=2,
        config=config,
    )

    assert (
        first.weights
        == second.weights
    )


def test_result_exposes_hand_count() -> None:
    (
        weights,
        strategies,
    ) = make_inputs(
        draw_count=1
    )

    result = transition_draw_range(
        pre_draw_weights=weights,
        strategies=strategies,
        public_draw_count=1,
        config=DrawTransitionConfig(
            mode="sample",
            sampling=DrawSamplingConfig(
                samples_per_hand_action=100,
                seed=2,
            ),
        ),
    )

    assert (
        result.hand_count
        == len(result.weights)
    )

    assert result.hand_count > 0


def test_invalid_mode_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Unknown draw transition mode"
        ),
    ):
        DrawTransitionConfig(
            mode="invalid",  # type: ignore[arg-type]
        )