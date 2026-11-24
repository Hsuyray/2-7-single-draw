"""
Linear CFR iteration weighting (day75,
docs/proposals/CFR-linear-weighting.md).
"""

import argparse

import pytest

from scripts.compare_average_modes import DualAverageTrainer
from scripts.fingerprint_node_store import fingerprint_trainer
from scripts.train_weighting_variant import build_trainer
from solver.cfr_trainer import CFRTrainer
from solver.single_draw_game import SingleDrawGame
from solver.solution_library import (
    new_solution_entry,
    training_argv,
)


def settings(**overrides) -> argparse.Namespace:
    values = dict(
        max_draw=5, abstraction="bucket", bet_sizing="fast",
        stack=20.0, seed=42, average_mode="simple",
        iteration_weighting="uniform",
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def train(trainer: CFRTrainer, config, iterations: int, seed: int = 42):
    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter
        counter += 1
        return SingleDrawGame(
            config=config, button_seat=0, deck_seed=seed + counter,
        )

    trainer.train(factory, iterations=iterations)
    return trainer


def variant(iterations: int, **overrides) -> CFRTrainer:
    trainer, config = build_trainer(settings(**overrides))
    return train(trainer, config, iterations)


def test_bad_settings_are_rejected() -> None:
    assert CFRTrainer().iteration_weighting == "uniform"

    with pytest.raises(ValueError, match="Iteration weighting"):
        CFRTrainer(
            traversal_mode="external_sampling",
            iteration_weighting="cubic",
        )

    with pytest.raises(ValueError, match="external sampling"):
        CFRTrainer(
            traversal_mode="full",
            iteration_weighting="linear",
        )


def test_explicit_uniform_is_the_original_trainer() -> None:
    assert fingerprint_trainer(
        variant(20, average_mode="reach", iteration_weighting="uniform")
    ) == fingerprint_trainer(
        variant(20, average_mode="reach")
    )


def test_variant_script_reproduces_day74_simple_average() -> None:
    # train_weighting_variant with simple + uniform is the day74
    # experiment's "simple" side table, so its 8k checkpoint is the
    # baseline for the linear run.
    dual_trainer, config = build_trainer(settings(average_mode="reach"))
    dual = DualAverageTrainer(**{
        name: getattr(dual_trainer, name)
        for name in (
            "max_draw", "raise_sizes", "bet_sizing_policy",
            "abstraction", "traversal_mode", "draw_action_mode",
            "random_seed", "game_config",
        )
    })
    train(dual, config, 20)
    simple = variant(20)

    side = {id(node): sums for node, sums in dual.simple_sums.values()}

    for dual_node, node in zip(
        dual.node_store.nodes.values(),
        simple.node_store.nodes.values(),
        strict=True,
    ):
        assert node.strategy_sum == side.get(
            id(dual_node),
            {action: 0.0 for action in dual_node.actions},
        )


@pytest.mark.parametrize("average_mode", ["reach", "simple"])
def test_linear_weights_iteration_t_by_t(average_mode: str) -> None:
    # Iteration 1 has weight 1, so after one iteration linear and
    # uniform are identical. Iteration 2 starts from that same state
    # and the same deal; with these deals no node is regret-updated
    # in both iterations, so the current strategies stay equal and
    # every iteration-2 increment under linear is exactly 2 x the
    # uniform one (regrets and average sums). Revisited nodes are
    # covered by test_linear_average_weight_is_t_on_a_repeated_deal.
    uniform_one = variant(1, average_mode=average_mode)
    linear_one = variant(1, average_mode=average_mode,
                         iteration_weighting="linear")

    assert fingerprint_trainer(linear_one) == fingerprint_trainer(
        uniform_one
    )

    before = {
        state: (dict(node.regret_sum), dict(node.strategy_sum),
                node.strategy_weight_sum)
        for state, node in uniform_one.node_store.nodes.items()
    }

    uniform_two = variant(2, average_mode=average_mode)
    linear_two = variant(2, average_mode=average_mode,
                         iteration_weighting="linear")

    assert list(linear_two.node_store.nodes) == list(
        uniform_two.node_store.nodes
    )

    def increments(trainer, state, node):
        regrets, sums, weight = before.get(
            state,
            (
                dict.fromkeys(node.actions, 0.0),
                dict.fromkeys(node.actions, 0.0),
                0.0,
            ),
        )
        return (
            {a: node.regret_sum[a] - regrets[a] for a in node.actions},
            {a: node.strategy_sum[a] - sums[a] for a in node.actions},
            node.strategy_weight_sum - weight,
        )

    changed = 0

    for state, u_node in uniform_two.node_store.nodes.items():
        l_node = linear_two.node_store.nodes[state]
        u_reg, u_sum, u_w = increments(uniform_two, state, u_node)
        l_reg, l_sum, l_w = increments(linear_two, state, l_node)

        for action in u_node.actions:
            assert l_reg[action] == pytest.approx(
                2.0 * u_reg[action], rel=1e-12, abs=1e-12
            )
            assert l_sum[action] == pytest.approx(
                2.0 * u_sum[action], rel=1e-12, abs=1e-12
            )

        assert l_w == pytest.approx(2.0 * u_w, rel=1e-12, abs=1e-12)
        changed += u_w > 0

    assert changed > 0


def test_linear_average_weight_is_t_on_a_repeated_deal(
    monkeypatch,
) -> None:
    # The same deal every iteration, so nodes are revisited with
    # earlier (t-weighted) regrets. Under simple averaging every
    # accumulation must carry weight t = the iteration in progress.
    from solver.cfr_node import CFRNode

    trainer, config = build_trainer(
        settings(iteration_weighting="linear")
    )
    seen: list[tuple[float, float]] = []
    original = CFRNode.accumulate_strategy

    def recording(node, realization_weight):
        seen.append(
            (realization_weight, trainer.completed_iterations + 1.0)
        )
        return original(node, realization_weight)

    monkeypatch.setattr(CFRNode, "accumulate_strategy", recording)

    def same_deal() -> SingleDrawGame:
        return SingleDrawGame(
            config=config, button_seat=0, deck_seed=7,
        )

    trainer.train(same_deal, iterations=6)

    assert {t for _, t in seen} == {1.0, 2.0, 3.0, 4.0, 5.0, 6.0}
    assert all(weight == t for weight, t in seen)

    revisited = [
        node for node in trainer.node_store.nodes.values()
        if node.regret_update_count >= 3
    ]
    assert revisited


def test_linear_differs_after_regrets_diverge() -> None:
    uniform = variant(30)
    linear = variant(30, iteration_weighting="linear")

    assert fingerprint_trainer(linear) != fingerprint_trainer(uniform)


def test_library_entries_carry_the_iteration_weighting() -> None:
    entry = new_solution_entry(
        stack=20, max_draw=5, abstraction="bucket",
        bet_sizing="full", seed=42, milestones=[8000],
        average_mode="simple", iteration_weighting="linear",
    )

    argv = training_argv(entry)

    assert argv[argv.index("--iteration-weighting") + 1] == "linear"

    del entry["abstraction"]["iteration_weighting"]

    argv = training_argv(entry)

    assert argv[argv.index("--iteration-weighting") + 1] == "uniform"
