import random

import pytest

from solver.actions import (
    DiscardAction,
)
from solver.draw_range_sampling import (
    DrawSamplingConfig,
    sample_exact_draw_range,
    sample_exact_hand_transition,
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


def test_sampling_config_rejects_zero_samples() -> None:
    with pytest.raises(
        ValueError
    ):
        DrawSamplingConfig(
            samples_per_hand_action=0,
        )


def test_stand_pat_sampling_preserves_hand() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    result = sample_exact_hand_transition(
        hand_key=hand_key,
        action=DiscardAction(
            ()
        ),
        sample_count=10,
        random_generator=random.Random(
            1
        ),
    )

    assert result == {
        hand_key: 1.0,
    }


def test_draw_one_sampling_sums_to_one() -> None:
    hand = make_hand()

    result = sample_exact_hand_transition(
        hand_key=exact_hand_key(
            hand
        ),
        action=DiscardAction(
            (4,)
        ),
        sample_count=500,
        random_generator=random.Random(
            1
        ),
    )

    assert result

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_draw_three_sampling_sums_to_one() -> None:
    hand = make_hand()

    result = sample_exact_hand_transition(
        hand_key=exact_hand_key(
            hand
        ),
        action=DiscardAction(
            (2, 3, 4)
        ),
        sample_count=500,
        random_generator=random.Random(
            2
        ),
    )

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_sampling_is_deterministic_with_seed() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    action = DiscardAction(
        (3, 4)
    )

    first = sample_exact_hand_transition(
        hand_key=hand_key,
        action=action,
        sample_count=500,
        random_generator=random.Random(
            42
        ),
    )

    second = sample_exact_hand_transition(
        hand_key=hand_key,
        action=action,
        sample_count=500,
        random_generator=random.Random(
            42
        ),
    )

    assert first == second


def test_sampling_can_differ_with_different_seeds() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    action = DiscardAction(
        (3, 4)
    )

    first = sample_exact_hand_transition(
        hand_key=hand_key,
        action=action,
        sample_count=100,
        random_generator=random.Random(
            1
        ),
    )

    second = sample_exact_hand_transition(
        hand_key=hand_key,
        action=action,
        sample_count=100,
        random_generator=random.Random(
            2
        ),
    )

    assert first != second


def test_sampled_range_transition_normalizes() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    result = sample_exact_draw_range(
        pre_draw_weights={
            hand_key: 2.0,
        },
        strategies={
            hand_key: {
                DiscardAction(
                    (4,)
                ): 0.75,
            },
        },
        public_draw_count=1,
        config=DrawSamplingConfig(
            samples_per_hand_action=500,
            seed=10,
        ),
        normalize=True,
    )

    assert result

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_sampled_range_preserves_reach_without_normalizing() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    result = sample_exact_draw_range(
        pre_draw_weights={
            hand_key: 2.0,
        },
        strategies={
            hand_key: {
                DiscardAction(
                    (4,)
                ): 0.25,
            },
        },
        public_draw_count=1,
        config=DrawSamplingConfig(
            samples_per_hand_action=500,
            seed=10,
        ),
        normalize=False,
    )

    assert (
        sum(result.values())
        == pytest.approx(0.5)
    )


def test_sampled_range_combines_private_patterns() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    result = sample_exact_draw_range(
        pre_draw_weights={
            hand_key: 1.0,
        },
        strategies={
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
            },
        },
        public_draw_count=1,
        config=DrawSamplingConfig(
            samples_per_hand_action=300,
            seed=3,
        ),
        normalize=False,
    )

    assert (
        sum(result.values())
        == pytest.approx(0.50)
    )


def test_sampled_range_returns_exact_hand_keys() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    result = sample_exact_draw_range(
        pre_draw_weights={
            hand_key: 1.0,
        },
        strategies={
            hand_key: {
                DiscardAction(
                    (4,)
                ): 1.0,
            },
        },
        public_draw_count=1,
        config=DrawSamplingConfig(
            samples_per_hand_action=100,
            seed=4,
        ),
    )

    assert all(
        isinstance(
            result_key,
            ExactHandKey,
        )
        for result_key
        in result
    )


def test_negative_pre_draw_weight_is_rejected() -> None:
    hand = make_hand()

    hand_key = exact_hand_key(
        hand
    )

    with pytest.raises(
        ValueError
    ):
        sample_exact_draw_range(
            pre_draw_weights={
                hand_key: -1.0,
            },
            strategies={},
            public_draw_count=1,
        )


def test_invalid_public_draw_count_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        sample_exact_draw_range(
            pre_draw_weights={},
            strategies={},
            public_draw_count=6,
        )