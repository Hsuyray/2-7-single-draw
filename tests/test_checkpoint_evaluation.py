import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from solver.best_response import (
    SampledBestResponse,
)
from solver.bet_sizing import (
    FAST_BET_SIZING,
)
from solver.cfr_trainer import (
    CFRTrainer,
)
from solver.checkpoint_evaluation import (
    EVALUATION_DECK_SEED_BASE,
    AssumedGameConfig,
    CheckpointConfigError,
    derive_seed,
    evaluate_baselines,
    evaluate_coverage,
    evaluate_head_to_head,
    evaluate_sampled_best_response,
    incompatible_fields,
    make_deal_factory,
    make_head_to_head_evaluator,
    make_profile_evaluator,
    setup_from_metadata,
    static_statistics,
    strategy_distance,
)
from solver.game_state import (
    GameConfig,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)
from solver.strategy_profile_evaluator import (
    CallStationPolicy,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

GAME_CONFIG = GameConfig(
    player_count=2,
    starting_stack=20.0,
    small_blind=1.0,
    big_blind=2.0,
    big_blind_ante=1.5,
)


def train_checkpoint(
    path: Path,
    *,
    iterations: int,
    seed: int,
) -> None:
    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=None,
        bet_sizing_policy=FAST_BET_SIZING,
        abstraction="bucket",
        traversal_mode="external_sampling",
        draw_action_mode="full",
        random_seed=seed,
        game_config=GAME_CONFIG,
    )

    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter
        counter += 1

        return SingleDrawGame(
            config=GAME_CONFIG,
            button_seat=0,
            deck_seed=seed + counter,
        )

    trainer.train(
        factory,
        iterations=iterations,
    )

    trainer.save_checkpoint(path)


@pytest.fixture(scope="module")
def checkpoints(
    tmp_path_factory,
):
    directory = tmp_path_factory.mktemp(
        "eval"
    )

    current = directory / "current.chk.gz"
    previous = directory / "previous.chk.gz"

    train_checkpoint(
        current,
        iterations=60,
        seed=42,
    )
    train_checkpoint(
        previous,
        iterations=30,
        seed=42,
    )

    return {
        "current_path": current,
        "previous_path": previous,
        "current": load_strategy_checkpoint(
            current
        ),
        "previous": load_strategy_checkpoint(
            previous
        ),
    }


@pytest.fixture(scope="module")
def setup(checkpoints):
    return setup_from_metadata(
        checkpoints["current"].metadata
    )


def test_setup_rebuilds_training_config(
    checkpoints,
    setup,
) -> None:
    assert setup.game_config == GAME_CONFIG
    assert setup.abstraction == "bucket"
    assert setup.max_draw == 1
    assert setup.raise_sizes is None
    assert setup.bet_sizing_policy == FAST_BET_SIZING
    assert setup.draw_action_mode == "full"
    assert setup.assumed_fields == ()


def test_missing_game_config_is_an_error(
    checkpoints,
) -> None:
    metadata = dataclasses.replace(
        checkpoints["current"].metadata,
        starting_stack=None,
    )

    with pytest.raises(
        CheckpointConfigError
    ):
        setup_from_metadata(metadata)

    assumed = setup_from_metadata(
        metadata,
        assumed=AssumedGameConfig(
            starting_stack=30.0,
            small_blind=9.0,
            big_blind=9.0,
            big_blind_ante=9.0,
        ),
    )

    # Only the missing field is filled in.
    assert assumed.assumed_fields == (
        "starting_stack",
    )
    assert assumed.game_config.starting_stack == 30.0
    assert assumed.game_config.small_blind == 1.0


def test_incompatible_fields(
    checkpoints,
) -> None:
    metadata = checkpoints["current"].metadata

    assert incompatible_fields(
        metadata,
        checkpoints["previous"].metadata,
    ) == []

    assert incompatible_fields(
        metadata,
        dataclasses.replace(
            metadata,
            max_draw=5,
        ),
    ) == ["max_draw"]

    # Floats compare with CHIP_EPSILON, not exactly.
    assert incompatible_fields(
        metadata,
        dataclasses.replace(
            metadata,
            small_blind=1.0 + 1e-12,
        ),
    ) == []


def test_derived_seeds_are_stable_and_disjoint_from_training() -> None:
    assert derive_seed(1, "a") == derive_seed(1, "a")
    assert derive_seed(1, "a") != derive_seed(1, "b")
    assert derive_seed(1, "a") != derive_seed(2, "a")
    assert 0 <= derive_seed(7, "x") < 2**31
    assert EVALUATION_DECK_SEED_BASE > 10**8


def test_static_statistics_counts_every_state(
    checkpoints,
) -> None:
    index = checkpoints["current"].strategy_index

    stats = static_statistics(index)

    assert stats["invalid_strategies"] == 0
    assert sum(
        phase["information_states"]
        for phase in stats["by_phase"].values()
    ) == len(index)


def test_coverage_matches_profile_evaluator(
    checkpoints,
    setup,
) -> None:
    index = checkpoints["current"].strategy_index

    section, visits = evaluate_coverage(
        index,
        setup,
        deals=150,
        seed=3,
        top=5,
    )

    # Same deals and policy seed, no observer.
    plain = make_profile_evaluator(
        index,
        setup,
        random_seed=section["policy_seed"],
    ).evaluate(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=section[
                "first_deck_seed"
            ],
        ),
        deals=150,
    )

    assert section["overall"]["matched"] == (
        plain.strategy_decisions
    )
    assert section["overall"]["missing"] == (
        plain.missing_strategy_decisions
    )
    assert section["self_play"][
        "seat_0_utility"
    ] == plain.seat_0_utility

    assert sum(visits.values()) == (
        plain.strategy_decisions
    )

    # Training and evaluation must agree on the
    # legal actions of every matched state.
    assert section["action_space_mismatches"] == 0

    assert section["self_play"][
        "max_zero_sum_error"
    ] < 1e-9


def test_coverage_is_deterministic_and_section_independent(
    checkpoints,
    setup,
) -> None:
    index = checkpoints["current"].strategy_index

    first, _ = evaluate_coverage(
        index,
        setup,
        deals=60,
        seed=5,
        top=5,
    )

    evaluate_sampled_best_response(
        index,
        setup,
        seed=5,
        repeats=1,
        response_deals=5,
        validation_deals=10,
        sweeps=1,
    )

    second, _ = evaluate_coverage(
        index,
        setup,
        deals=60,
        seed=5,
        top=5,
    )

    assert first == second


def test_button_one_is_not_in_training_distribution(
    checkpoints,
    setup,
) -> None:
    section, _ = evaluate_coverage(
        checkpoints["current"].strategy_index,
        setup,
        deals=30,
        seed=1,
        top=3,
        button_seat=1,
        label="coverage_button_1",
    )

    assert section["overall"]["matched"] == 0


def test_deterministic_policies_cancel_under_seat_swap(
    setup,
) -> None:
    # Identical deterministic policies on the same
    # deck: the duplicate pair value is exactly 0
    # if seats are really swapped.
    result = make_head_to_head_evaluator(
        setup,
        random_seed=1,
    ).evaluate(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=EVALUATION_DECK_SEED_BASE,
        ),
        first=CallStationPolicy(),
        second=CallStationPolicy(),
        deal_pairs=40,
    )

    assert abs(result.first_utility) < 1e-9
    assert result.first_missing_decisions == 0


def test_head_to_head_and_baselines(
    checkpoints,
    setup,
) -> None:
    current = checkpoints["current"].strategy_index

    self_match = evaluate_head_to_head(
        current,
        current,
        setup,
        seed=11,
        deal_pairs=150,
    )

    assert abs(self_match["utility"]) <= (
        4 * self_match["standard_error"]
        + 1e-9
    )
    assert self_match["max_zero_sum_error"] < 1e-9

    baselines = evaluate_baselines(
        current,
        setup,
        seed=11,
        deal_pairs=20,
    )

    assert set(baselines["opponents"]) == {
        "uniform",
        "call_station",
    }

    assert baselines == evaluate_baselines(
        current,
        setup,
        seed=11,
        deal_pairs=20,
    )


def test_strategy_distance_to_itself_is_zero(
    checkpoints,
    setup,
) -> None:
    index = checkpoints["current"].strategy_index

    _, visits = evaluate_coverage(
        index,
        setup,
        deals=40,
        seed=2,
        top=1,
    )

    distance = strategy_distance(
        index,
        index,
        visits=visits,
    )

    assert distance["visit_weighted_l1"] == 0.0
    assert distance["only_in_current"] == 0
    assert distance["only_in_previous"] == 0

    to_previous = strategy_distance(
        index,
        checkpoints["previous"].strategy_index,
        visits=visits,
    )

    assert to_previous["visit_weighted_l1"] > 0.0


def test_sbr_standard_error_fields(
    checkpoints,
    setup,
) -> None:
    result = SampledBestResponse(
        strategy_index=checkpoints[
            "current"
        ].strategy_index,
        abstraction=setup.abstraction,
        responder_seat=0,
        max_draw=setup.max_draw,
        raise_sizes=setup.raise_sizes,
        bet_sizing_policy=setup.bet_sizing_policy,
        draw_action_mode=setup.draw_action_mode,
        random_seed=3,
    ).optimize(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=EVALUATION_DECK_SEED_BASE,
        ),
        deals=5,
        max_sweeps=1,
        validation_deals=20,
    )

    count = result.validation_deals

    assert result.improvement_sum_squares >= (
        count
        * result.improvement**2
        - 1e-9
    )
    assert result.improvement_standard_error >= 0.0
    assert result.baseline_standard_error > 0.0


def run_script(
    *arguments: str,
    hash_seed: str,
) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = hash_seed

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.evaluate_checkpoint",
            *arguments,
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_script_is_reproducible_across_processes(
    checkpoints,
    tmp_path,
) -> None:
    common = (
        str(checkpoints["current_path"]),
        "--previous",
        str(checkpoints["previous_path"]),
        "--preset",
        "quick",
        "--deals",
        "80",
        "--button1-deals",
        "10",
        "--sbr-repeats",
        "2",
        "--sbr-response-deals",
        "5",
        "--sbr-validation-deals",
        "20",
        "--sbr-sweeps",
        "1",
        "--match-deal-pairs",
        "20",
    )

    reports = []

    # Different hash seeds: the report must not
    # depend on set or dict hash order.
    for name, hash_seed in (
        ("a", "1"),
        ("b", "2"),
    ):
        out_dir = tmp_path / name

        completed = run_script(
            *common,
            "--out-dir",
            str(out_dir),
            hash_seed=hash_seed,
        )

        assert completed.returncode == 0, (
            completed.stderr
        )

        (report,) = out_dir.glob("*.json")
        reports.append(report)

    data = json.loads(
        reports[0].read_text(
            encoding="utf-8"
        )
    )

    assert data["previous"]["compatible"]
    assert data["current_vs_average"][
        "available"
    ] is False

    same = run_script(
        "--compare",
        str(reports[0]),
        str(reports[1]),
        hash_seed="0",
    )

    assert same.returncode == 0, same.stdout

    different_seed = tmp_path / "c"

    completed = run_script(
        *common,
        "--seed",
        "1",
        "--out-dir",
        str(different_seed),
        hash_seed="1",
    )

    assert completed.returncode == 0, (
        completed.stderr
    )

    (report_c,) = different_seed.glob("*.json")

    differs = run_script(
        "--compare",
        str(reports[0]),
        str(report_c),
        hash_seed="0",
    )

    assert differs.returncode == 1
