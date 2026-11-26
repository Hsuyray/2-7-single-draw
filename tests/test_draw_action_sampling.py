"""
Draw-action sampling at the traverser's draw nodes (day76,
docs/proposals/CFR-draw-action-sampling.md).
"""

import itertools
import math
from statistics import fmean, pstdev

import pytest

from scripts.fingerprint_node_store import fingerprint_trainer
from solver.cfr_node import CFRNode
from solver.cfr_trainer import (
    DRAW_SAMPLE_FLOOR,
    CFRTrainer,
    GamePhase,
    draw_inclusion_probabilities,
    sampled_draw_estimates,
)
from solver.solution_library import (
    new_solution_entry,
    training_argv,
)
from tests.test_iteration_weighting import (
    settings,
    train,
    variant,
)
from scripts.train_weighting_variant import build_trainer
from solver.single_draw_game import SingleDrawGame


def test_bad_settings_are_rejected() -> None:
    assert CFRTrainer().draw_action_sampling == 0

    with pytest.raises(ValueError, match="non-negative integer"):
        CFRTrainer(
            traversal_mode="external_sampling",
            average_mode="simple",
            draw_action_sampling=-1,
        )

    # reach averaging weights the average by the traverser's reach
    # at traverser nodes, which sampling would leave out.
    with pytest.raises(ValueError, match="simple averaging"):
        CFRTrainer(
            traversal_mode="external_sampling",
            average_mode="reach",
            draw_action_sampling=4,
        )

    with pytest.raises(ValueError, match="simple averaging"):
        CFRTrainer(traversal_mode="full", draw_action_sampling=4)


def test_off_is_the_original_trainer() -> None:
    assert fingerprint_trainer(
        variant(20, draw_action_sampling=0)
    ) == fingerprint_trainer(
        variant(20)
    )


def test_inclusion_probabilities() -> None:
    actions = ("a", "b", "c", "d")
    inclusion = draw_inclusion_probabilities(
        actions=actions,
        strategy={"a": 0.7, "b": 0.2, "c": 0.1, "d": 0.0},
        target=4,
    )
    assert inclusion == pytest.approx(
        {"a": 1.0, "b": 0.8, "c": 0.4, "d": DRAW_SAMPLE_FLOOR}
    )


@pytest.mark.parametrize(
    "strategy",
    [
        {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25},
        {"a": 0.7, "b": 0.2, "c": 0.1, "d": 0.0},
        {"a": 0.01, "b": 0.01, "c": 0.0, "d": 0.98},
    ],
)
def test_estimates_are_exactly_unbiased(strategy) -> None:
    # Enumerate every keep / skip pattern with its probability: the
    # expected node value and regrets equal the exact ones.
    actions = ("a", "b", "c", "d")
    values = {"a": 3.0, "b": -2.0, "c": 7.5, "d": -11.0}
    inclusion = draw_inclusion_probabilities(
        actions=actions, strategy=strategy, target=2,
    )
    expected_value = 0.0
    expected_regrets = dict.fromkeys(actions, 0.0)
    total_probability = 0.0

    for kept in itertools.product((False, True), repeat=len(actions)):
        probability = math.prod(
            inclusion[a] if keep else 1.0 - inclusion[a]
            for a, keep in zip(actions, kept)
        )
        total_probability += probability
        value, regrets = sampled_draw_estimates(
            actions=actions,
            strategy=strategy,
            inclusion=inclusion,
            sampled_utilities={
                a: values[a] for a, keep in zip(actions, kept) if keep
            },
        )
        expected_value += probability * value
        for a in actions:
            expected_regrets[a] += probability * regrets[a]

    exact_value = sum(strategy[a] * values[a] for a in actions)
    assert total_probability == pytest.approx(1.0)
    assert expected_value == pytest.approx(exact_value)
    assert expected_regrets == pytest.approx(
        {a: values[a] - exact_value for a in actions}
    )


def test_sampling_trains_valid_reproducible_strategies() -> None:
    first = variant(30, draw_action_sampling=4)
    second = variant(30, draw_action_sampling=4)
    assert fingerprint_trainer(first) == fingerprint_trainer(second)
    assert fingerprint_trainer(first) != fingerprint_trainer(variant(30))

    for node in first.node_store.nodes.values():
        strategy = node.average_strategy()
        assert sum(strategy.values()) == pytest.approx(1.0)
        assert all(
            math.isfinite(p) and p >= 0.0 for p in strategy.values()
        )
        assert all(math.isfinite(r) for r in node.regret_sum.values())
        assert node.strategy_weight_sum >= 0.0


def first_draw_game(config) -> SingleDrawGame:
    game = SingleDrawGame(config=config, button_seat=0, deck_seed=7)
    trainer, _ = build_trainer(settings())
    # button calls, big blind checks: big blind (seat 1) draws first.
    while game.phase != GamePhase.DRAW:
        actions = trainer._legal_actions(game)
        game = trainer._apply_node_action(game=game, action=actions[1])
    assert game.acting_seat == 1
    return game


def test_traversal_matches_full_exploration_on_average(monkeypatch) -> None:
    # With learning frozen, the traverser's draw-node regrets and value
    # from a sampled traversal must average to those of the full one
    # (both are noisy only through the sampled opponent and, for the
    # sampled one, the kept draw actions).
    trainer, config = build_trainer(settings())
    train(trainer, config, 40)
    game = first_draw_game(config)
    actions = trainer._legal_actions(game)
    draw_node = trainer._get_node(game=game, acting_seat=1, actions=actions)

    recorded: list[dict] = []

    def add_regrets(node, regrets):
        if node is draw_node:
            recorded.append(dict(regrets))

    monkeypatch.setattr(CFRNode, "add_regrets", add_regrets)
    monkeypatch.setattr(
        CFRNode, "accumulate_strategy", lambda node, realization_weight: None
    )

    def run(sampling: int, runs: int):
        trainer.draw_action_sampling = sampling
        values = [
            trainer._external_sampling_cfr(
                game=game, traversing_seat=1, traverser_reach=1.0,
            )
            for _ in range(runs)
        ]
        regrets = recorded[-runs:]
        assert len(recorded) >= runs
        return values, regrets

    full_values, full_regrets = run(0, 100)
    sampled_values, sampled_regrets = run(4, 1000)

    def check(full, sampled):
        se = math.sqrt(
            pstdev(full) ** 2 / len(full)
            + pstdev(sampled) ** 2 / len(sampled)
        )
        assert abs(fmean(full) - fmean(sampled)) <= 4 * se + 1e-9

    check(full_values, sampled_values)
    for action in actions:
        check(
            [r[action] for r in full_regrets],
            [r[action] for r in sampled_regrets],
        )


def test_library_entries_carry_draw_action_sampling() -> None:
    entry = new_solution_entry(
        stack=20.0, max_draw=5, abstraction="bucket", bet_sizing="full",
        seed=42, milestones=[8000], average_mode="simple",
        draw_action_sampling=4,
    )
    argv = training_argv(entry)
    assert argv[argv.index("--draw-action-sampling") + 1] == "4"

    del entry["abstraction"]["draw_action_sampling"]
    argv = training_argv(entry)
    assert argv[argv.index("--draw-action-sampling") + 1] == "0"
