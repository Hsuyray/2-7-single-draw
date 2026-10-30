import pytest

from scripts.inspect_sbr_power import (
    run_sbr,
)
from solver.checkpoint_evaluation import (
    EVALUATION_DECK_SEED_BASE,
    setup_from_metadata,
)
from solver.exploitability_power import (
    FOLD,
    faces_voluntary_raise,
    judge_estimator,
    plant_fold_leak,
    reference_exploit_gain,
)
from solver.response_grouping import (
    coarse_grouping,
    coarse_hand_class,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)
from tests.test_checkpoint_evaluation import (
    train_checkpoint,
)


@pytest.fixture(scope="module")
def trained(
    tmp_path_factory,
):
    path = (
        tmp_path_factory.mktemp("power")
        / "power.chk.gz"
    )

    train_checkpoint(
        path,
        iterations=40,
        seed=11,
    )

    loaded = load_strategy_checkpoint(path)

    return (
        loaded.strategy_index,
        setup_from_metadata(
            loaded.metadata
        ),
    )


def test_plant_fold_leak(
    trained,
) -> None:
    index, _ = trained

    original = index.strategies()

    unchanged = plant_fold_leak(
        index,
        leaky_seat=1,
        probability=0.0,
    ).strategies()

    assert unchanged == original

    leaky = plant_fold_leak(
        index,
        leaky_seat=1,
        probability=0.5,
    ).strategies()

    planted = 0

    for state, strategy in leaky.items():
        assert set(strategy) == set(
            original[state]
        )
        assert abs(
            sum(strategy.values()) - 1.0
        ) < 1e-9

        if (
            state.observer_seat == 1
            and FOLD in strategy
            and faces_voluntary_raise(
                state,
                leaky_seat=1,
            )
        ):
            planted += 1
            assert strategy[FOLD] == pytest.approx(
                0.5
                + 0.5 * original[state][FOLD]
            )

        else:
            assert strategy == original[state]

    assert planted > 0


def test_leak_ignores_blinds(
    trained,
) -> None:
    index, _ = trained

    original = index.strategies()

    leaky_button = plant_fold_leak(
        index,
        leaky_seat=0,
        probability=1.0,
    ).strategies()

    root_states = [
        state
        for state in original
        if state.observer_seat == 0
        and not state.public_node.action_history
        and FOLD in original[state]
    ]

    # Seat 0 may fold to the big blind at the
    # root; that is not a voluntary raise.
    assert root_states
    for state in root_states:
        assert leaky_button[state] == original[state]

    # For seat 1 every bet it can fold to is a
    # voluntary raise by seat 0, so the day51 rule
    # ("any FOLD state") and the day52 rule agree,
    # and the day51 seat-0 responder results stand.
    for state, strategy in original.items():
        if (
            state.observer_seat == 1
            and FOLD in strategy
        ):
            assert faces_voluntary_raise(
                state,
                leaky_seat=1,
            )


def test_coarse_grouping_uses_only_own_information(
    trained,
) -> None:
    index, _ = trained

    states = list(index.strategies())

    keys = set()

    for state in states:
        actions = tuple(
            sorted(
                index.strategy_for_state(state),
                key=repr,
            )
        )

        key = coarse_grouping(state, actions)

        assert key[0] == state.observer_seat
        assert key[1] == state.public_node
        assert key[2] == coarse_hand_class(
            state.own_hand_key
        )
        assert key[3] == actions

        keys.add(key)

    assert len(keys) < len(states)


def test_judge_estimator() -> None:
    good = {
        0.0: {"mean": 0.01, "se": 0.1},
        0.5: {"mean": 0.8, "se": 0.1},
        1.0: {"mean": 2.0, "se": 0.1},
    }

    assert judge_estimator(
        good,
        reference_at_largest_leak=3.0,
    )["pass"]

    uninformative = judge_estimator(
        good,
        reference_at_largest_leak=0.09,
        reference_standard_error=0.05,
    )
    assert uninformative["status"] == "INVALID"
    assert not uninformative["pass"]

    weak = judge_estimator(
        good,
        reference_at_largest_leak=5.0,
    )
    assert not weak["P1_power"]

    negative = dict(good)
    negative[0.0] = {"mean": -0.5, "se": 0.1}
    assert not judge_estimator(
        negative,
        reference_at_largest_leak=3.0,
    )["P3_validity"]

    falling = dict(good)
    falling[0.5] = {"mean": 2.6, "se": 0.1}
    assert not judge_estimator(
        falling,
        reference_at_largest_leak=3.0,
    )["P2_monotone"]


def test_full_leak_is_found_by_reference_and_grouped_sbr(
    trained,
) -> None:
    index, setup = trained

    leaky = plant_fold_leak(
        index,
        leaky_seat=1,
        probability=1.0,
    )

    reference = reference_exploit_gain(
        leaky,
        setup,
        responder_seat=0,
        deals=300,
        first_deck_seed=EVALUATION_DECK_SEED_BASE,
        random_seed=3,
    )

    # The tiny checkpoint has low coverage, and
    # unstored states are not leaky, so only a
    # clear positive gain is required here.
    assert reference.gain > (
        2 * reference.gain_standard_error
    )

    common = dict(
        seat=0,
        repeat=0,
        seed=5,
        response_deals=20,
        validation_deals=60,
        sweeps=2,
    )

    grouped = run_sbr(
        leaky,
        setup,
        grouping=coarse_grouping,
        **common,
    )

    per_state = run_sbr(
        leaky,
        setup,
        grouping=None,
        **common,
    )

    assert grouped["gain"] > 0.0
    assert grouped["policy_keys"] < (
        per_state["policy_keys"]
    )

    # Deterministic under a fixed seed.
    assert run_sbr(
        leaky,
        setup,
        grouping=coarse_grouping,
        **common,
    ) | {"elapsed_s": 0} == grouped | {
        "elapsed_s": 0
    }
