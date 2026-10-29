import dataclasses

import pytest

from scripts.inspect_sbr_budget import (
    FallbackProbeSBR,
    run_one,
)
from solver.best_response import (
    SampledBestResponse,
)
from solver.checkpoint_evaluation import (
    EVALUATION_DECK_SEED_BASE,
    evaluate_sampled_best_response,
    make_deal_factory,
    setup_from_metadata,
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
        tmp_path_factory.mktemp("probe")
        / "probe.chk.gz"
    )

    train_checkpoint(
        path,
        iterations=40,
        seed=7,
    )

    loaded = load_strategy_checkpoint(path)

    return (
        loaded.strategy_index,
        setup_from_metadata(
            loaded.metadata
        ),
    )


def optimize(
    optimizer_type,
    index,
    setup,
    **extra,
):
    optimizer = optimizer_type(
        strategy_index=index,
        abstraction=setup.abstraction,
        responder_seat=1,
        max_draw=setup.max_draw,
        raise_sizes=setup.raise_sizes,
        bet_sizing_policy=setup.bet_sizing_policy,
        draw_action_mode=setup.draw_action_mode,
        random_seed=13,
        **extra,
    )

    result = optimizer.optimize(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=EVALUATION_DECK_SEED_BASE,
        ),
        deals=8,
        max_sweeps=2,
        validation_game_factory=make_deal_factory(
            setup.game_config,
            first_deck_seed=(
                EVALUATION_DECK_SEED_BASE
                + 10_000
            ),
        ),
        validation_deals=25,
    )

    return (
        optimizer,
        result,
    )


def test_probe_does_not_change_production_result(
    trained,
) -> None:
    index, setup = trained

    _, plain = optimize(
        SampledBestResponse,
        index,
        setup,
    )

    probe, probed = optimize(
        FallbackProbeSBR,
        index,
        setup,
        probe_seed=99,
    )

    assert dataclasses.asdict(plain) == (
        dataclasses.asdict(probed)
    )

    assert probe.probe_count == 25

    assert (
        plain.response_policy_decisions
        + plain.response_fallback_decisions
        > 0
    )

    assert (
        plain.response_fallback_tie_decisions
        <= plain.response_fallback_decisions
    )


def test_probe_is_deterministic(
    trained,
) -> None:
    index, setup = trained

    first, _ = optimize(
        FallbackProbeSBR,
        index,
        setup,
        probe_seed=5,
    )

    second, _ = optimize(
        FallbackProbeSBR,
        index,
        setup,
        probe_seed=5,
    )

    assert first.probe_total == second.probe_total
    assert (
        first.probe_gain_sum_squares
        == second.probe_gain_sum_squares
    )


def test_run_one_reproduces_evaluate_checkpoint_sbr(
    trained,
) -> None:
    index, setup = trained

    section, _ = evaluate_sampled_best_response(
        index,
        setup,
        seed=21,
        repeats=1,
        response_deals=6,
        validation_deals=15,
        sweeps=2,
    )

    for seat in (0, 1):
        run = run_one(
            index,
            setup,
            seed=21,
            seat=seat,
            repeat=0,
            response_deals=6,
            validation_deals=15,
            sweeps=2,
        )

        assert run["gain_argmax"] == (
            section["runs"][f"seat_{seat}"][0][
                "gain"
            ]
        )

        assert 0.0 <= run["fallback_share"] <= 1.0
