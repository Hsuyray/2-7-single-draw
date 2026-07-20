import pytest

from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.single_draw_game import SingleDrawGame
from solver.training_factory import TrainingGameFactory


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