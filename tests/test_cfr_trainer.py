import pytest

from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.single_draw_game import SingleDrawGame
from solver.training_factory import TrainingGameFactory
from solver.hand_abstraction import ExactHandKey
from solver.made_hand_bucket import MadeHandBucket
from solver.draw_hand_bucket import DrawHandBucket
from solver.bet_sizing_profiles import (
    FAST_BET_SIZING,
)


def make_heads_up_game() -> SingleDrawGame:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    return SingleDrawGame(
        config=config,
        button_seat=0,
        shuffle_deck=False,
    )


def make_three_player_game() -> SingleDrawGame:
    config = GameConfig(
        player_count=3,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    return SingleDrawGame(
        config=config,
        button_seat=0,
        shuffle_deck=False,
    )


def test_iterations_must_be_positive() -> None:
    trainer = CFRTrainer(
        max_draw=0,
    )

    with pytest.raises(ValueError):
        trainer.train(
            make_heads_up_game,
            iterations=0,
        )


def test_negative_iterations_are_rejected() -> None:
    trainer = CFRTrainer(
        max_draw=0,
    )

    with pytest.raises(ValueError):
        trainer.train(
            make_heads_up_game,
            iterations=-1,
        )


def test_prototype_rejects_multiplayer_game() -> None:
    trainer = CFRTrainer(
        max_draw=0,
    )

    with pytest.raises(ValueError):
        trainer.train(
            make_three_player_game,
            iterations=1,
        )


def test_one_iteration_creates_nodes() -> None:
    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        make_heads_up_game,
        iterations=1,
    )

    assert trainer.completed_iterations == 1
    assert len(trainer.node_store) > 0


def test_multiple_iterations_are_counted() -> None:
    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        make_heads_up_game,
        iterations=2,
    )

    assert trainer.completed_iterations == 2


def test_training_updates_regrets() -> None:
    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        make_heads_up_game,
        iterations=2,
    )

    has_nonzero_regret = any(
        abs(regret) > 1e-12
        for node in trainer.node_store.nodes.values()
        for regret in node.regret_sum.values()
    )

    assert has_nonzero_regret is True


def test_average_strategies_sum_to_one() -> None:
    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        make_heads_up_game,
        iterations=2,
    )

    strategies = trainer.average_strategies()

    assert strategies

    for strategy in strategies.values():
        assert sum(strategy.values()) == pytest.approx(
            1.0
        )


def test_average_strategy_probabilities_are_valid() -> None:
    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        make_heads_up_game,
        iterations=2,
    )

    for strategy in (
        trainer.average_strategies().values()
    ):
        for probability in strategy.values():
            assert 0.0 <= probability <= 1.0


def test_training_does_not_modify_factory_game() -> None:
    original_game = make_heads_up_game()

    original_pot = original_game.pot
    original_phase = original_game.phase
    original_history = tuple(
        original_game.action_history
    )

    def factory() -> SingleDrawGame:
        return original_game

    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        factory,
        iterations=1,
    )

    assert original_game.pot == original_pot
    assert original_game.phase == original_phase
    assert tuple(
        original_game.action_history
    ) == original_history


def test_trainer_uses_multiple_sampled_deals() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    factory = TrainingGameFactory(
        config=config,
        initial_seed=42,
        alternate_button=True,
    )

    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        factory,
        iterations=5,
    )

    assert factory.games_created == 5
    assert trainer.completed_iterations == 5
    assert len(trainer.node_store) > 0


def test_trainer_uses_exact_abstraction_by_default() -> None:
    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
    )

    trainer.train(
        make_heads_up_game,
        iterations=1,
    )

    assert all(
        isinstance(
            state.own_hand_key,
            ExactHandKey,
        )
        for state in trainer.node_store.nodes
    )


def test_trainer_can_use_bucket_abstraction() -> None:
    trainer = CFRTrainer(
        max_draw=0,
        raise_sizes=(),
        abstraction="bucket",
    )

    trainer.train(
        make_heads_up_game,
        iterations=1,
    )

    for state in trainer.node_store.nodes:
        if state.phase == "postdraw_betting":
            assert isinstance(
                state.own_hand_key,
                MadeHandBucket,
            )
        else:
            assert isinstance(
                state.own_hand_key,
                DrawHandBucket,
            )


def test_full_traversal_is_default() -> None:
    trainer = CFRTrainer()

    assert trainer.traversal_mode == "full"


def test_invalid_traversal_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        CFRTrainer(
            traversal_mode="invalid",  # type: ignore[arg-type]
        )


def test_external_sampling_creates_nodes() -> None:
    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    trainer.train(
        make_heads_up_game,
        iterations=2,
    )

    assert trainer.completed_iterations == 2
    assert len(trainer.node_store) > 0


def test_external_sampling_updates_regrets() -> None:
    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    trainer.train(
        make_heads_up_game,
        iterations=5,
    )

    has_nonzero_regret = any(
        abs(regret) > 1e-12
        for node
        in trainer.node_store.nodes.values()
        for regret in node.regret_sum.values()
    )

    assert has_nonzero_regret is True


def test_external_sampling_is_reproducible() -> None:
    first_trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    second_trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    first_trainer.train(
        make_heads_up_game,
        iterations=5,
    )

    second_trainer.train(
        make_heads_up_game,
        iterations=5,
    )

    assert (
        first_trainer.node_store.nodes.keys()
        == second_trainer.node_store.nodes.keys()
    )

    for information_state in (
        first_trainer.node_store.nodes
    ):
        first_node = (
            first_trainer.node_store.nodes[
                information_state
            ]
        )

        second_node = (
            second_trainer.node_store.nodes[
                information_state
            ]
        )

        assert (
            first_node.regret_sum
            == second_node.regret_sum
        )
        assert (
            first_node.strategy_sum
            == second_node.strategy_sum
        )


def test_external_sampling_explores_fewer_nodes() -> None:
    full_trainer = CFRTrainer(
        max_draw=3,
        raise_sizes=(),
        traversal_mode="full",
        random_seed=42,
    )

    sampled_trainer = CFRTrainer(
        max_draw=3,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    full_trainer.train(
        make_heads_up_game,
        iterations=1,
    )

    sampled_trainer.train(
        make_heads_up_game,
        iterations=1,
    )

    assert (
        len(sampled_trainer.node_store)
        < len(full_trainer.node_store)
    )


def test_external_sampling_average_strategies_are_valid() -> None:
    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    trainer.train(
        make_heads_up_game,
        iterations=5,
    )

    strategies = trainer.average_strategies()

    assert strategies

    for strategy in strategies.values():
        assert sum(
            strategy.values()
        ) == pytest.approx(1.0)

        for probability in strategy.values():
            assert (
                0.0
                <= probability
                <= 1.0
            )


def test_bucket_abstraction_uses_full_draw_actions() -> None:
    trainer = CFRTrainer(
        abstraction="bucket",
    )

    assert (
        trainer.resolved_draw_action_mode
        == "full"
    )


def test_draw_action_mode_can_be_overridden() -> None:
    exact_trainer = CFRTrainer(
        abstraction="exact",
        draw_action_mode="candidate",
    )

    bucket_trainer = CFRTrainer(
        abstraction="bucket",
        draw_action_mode="full",
    )

    assert (
        exact_trainer.resolved_draw_action_mode
        == "candidate"
    )

    assert (
        bucket_trainer.resolved_draw_action_mode
        == "full"
    )


def test_trainer_disables_raises_with_empty_tuple() -> None:
    trainer = CFRTrainer(
        raise_sizes=(),
    )

    assert (
        trainer.uses_bet_sizing_policy
        is False
    )


def test_trainer_uses_policy_when_raise_sizes_is_none() -> None:
    trainer = CFRTrainer(
        raise_sizes=None,
        bet_sizing_policy=(
            FAST_BET_SIZING
        ),
    )

    assert (
        trainer.uses_bet_sizing_policy
        is True
    )

    assert (
        trainer.bet_sizing_policy
        is FAST_BET_SIZING
    )


def test_trainer_supports_explicit_raise_sizes() -> None:
    trainer = CFRTrainer(
        raise_sizes=(
            6.0,
            10.0,
        ),
    )

    assert (
        trainer.raise_sizes
        == (
            6.0,
            10.0,
        )
    )

    assert (
        trainer.uses_bet_sizing_policy
        is False
    )


def test_trainer_rejects_negative_raise_size() -> None:
    try:
        CFRTrainer(
            raise_sizes=(
                -1.0,
            ),
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_bucket_candidate_draw_actions_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "requires full draw actions"
        ),
    ):
        CFRTrainer(
            abstraction="bucket",
            draw_action_mode="candidate",
        )