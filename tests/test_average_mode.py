"""
Average-strategy weighting in external sampling (day75,
docs/proposals/CFR-average-weighting.md).

    reach   original: traverser's nodes, weight = own reach (default)
    simple  Lanctot et al. 2009: opponent's sampled nodes, weight 1
"""

import pytest

from scripts.compare_average_modes import DualAverageTrainer
from scripts.fingerprint_node_store import fingerprint_trainer
from solver.bet_sizing import FAST_BET_SIZING
from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.single_draw_game import SingleDrawGame
from solver.solution_library import (
    new_solution_entry,
    training_argv,
)


CONFIG = GameConfig(
    player_count=2,
    starting_stack=20.0,
    small_blind=1.0,
    big_blind=2.0,
    big_blind_ante=1.5,
)

ITERATIONS = 30


def trained(
    trainer_class=CFRTrainer,
    **settings,
) -> CFRTrainer:
    trainer = trainer_class(
        max_draw=5,
        raise_sizes=None,
        bet_sizing_policy=FAST_BET_SIZING,
        abstraction="bucket",
        traversal_mode="external_sampling",
        random_seed=42,
        game_config=CONFIG,
        **settings,
    )

    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter
        counter += 1
        return SingleDrawGame(
            config=CONFIG,
            button_seat=0,
            deck_seed=42 + counter,
        )

    trainer.train(factory, iterations=ITERATIONS)

    return trainer


def regret_view(trainer: CFRTrainer) -> list:
    return [
        (
            state,
            node.actions,
            dict(node.regret_sum),
            node.regret_update_count,
        )
        for state, node in trainer.node_store.nodes.items()
    ]


def test_default_is_reach_and_bad_settings_are_rejected() -> None:
    assert CFRTrainer().average_mode == "reach"

    with pytest.raises(ValueError, match="Average mode"):
        CFRTrainer(
            traversal_mode="external_sampling",
            average_mode="linear",
        )

    with pytest.raises(ValueError, match="external sampling"):
        CFRTrainer(
            traversal_mode="full",
            average_mode="simple",
        )


def test_explicit_reach_is_the_original_trainer() -> None:
    assert fingerprint_trainer(
        trained(average_mode="reach")
    ) == fingerprint_trainer(trained())


def test_simple_changes_only_the_average() -> None:
    # Regrets, sampling and node creation are those of the original
    # trainer: same nodes in the same order, identical regrets.
    reach = trained()
    simple = trained(average_mode="simple")

    assert regret_view(simple) == regret_view(reach)

    assert any(
        simple.node_store.nodes[state].strategy_sum
        != node.strategy_sum
        for state, node in reach.node_store.nodes.items()
    )


def test_simple_matches_the_experiment_side_table() -> None:
    # The day74 experiment (scripts/compare_average_modes.py) recorded
    # simple averages in a side table of an unmodified trainer. The
    # trainer option must reproduce them exactly.
    dual = trained(DualAverageTrainer)
    simple = trained(average_mode="simple")

    side = {
        id(node): sums
        for node, sums in dual.simple_sums.values()
    }

    for (state, dual_node), node in zip(
        dual.node_store.nodes.items(),
        simple.node_store.nodes.values(),
        strict=True,
    ):
        expected = side.get(
            id(dual_node),
            {action: 0.0 for action in dual_node.actions},
        )

        assert node.strategy_sum == expected, state


def test_simple_adds_weight_one_per_opponent_visit() -> None:
    # Each accumulation adds a full probability vector with weight 1,
    # so the weight sum counts visits and every sum is its own
    # stored average times that count.
    simple = trained(average_mode="simple")

    visited = 0

    for node in simple.node_store.nodes.values():
        assert node.strategy_weight_sum == float(
            node.strategy_update_count
        )
        assert sum(node.strategy_sum.values()) == pytest.approx(
            node.strategy_weight_sum
        )
        visited += node.strategy_update_count > 0

    assert visited > 0


def test_library_entries_carry_the_average_mode() -> None:
    entry = new_solution_entry(
        stack=20, max_draw=5, abstraction="bucket",
        bet_sizing="full", seed=42, milestones=[8000],
        average_mode="simple",
    )

    argv = training_argv(entry)

    assert argv[argv.index("--average-mode") + 1] == "simple"

    # Entries written before the option existed were trained with
    # "reach" and must keep resuming with it.
    del entry["abstraction"]["average_mode"]

    argv = training_argv(entry)

    assert argv[argv.index("--average-mode") + 1] == "reach"
