from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.strategy_index import StrategyIndex
from solver.training_factory import (
    TrainingGameFactory,
)


def test_trainer_builds_strategy_index() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    factory = TrainingGameFactory(
        config=config,
        initial_seed=42,
    )

    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        abstraction="bucket",
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=42,
    )

    trainer.train(
        factory,
        iterations=5,
    )

    index = trainer.strategy_index()

    assert isinstance(
        index,
        StrategyIndex,
    )

    assert len(
        index.public_nodes()
    ) > 0


def test_strategy_index_contains_trained_states() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    factory = TrainingGameFactory(
        config=config,
        initial_seed=42,
    )

    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        abstraction="bucket",
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=42,
    )

    trainer.train(
        factory,
        iterations=5,
    )

    strategies = (
        trainer.average_strategies()
    )

    index = trainer.strategy_index()

    assert strategies

    state = next(
        iter(strategies)
    )

    expected = strategies[state]

    result = (
        index.strategy_for_state(
            state
        )
    )

    assert result == expected


def test_range_query_works_from_trainer_output() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    factory = TrainingGameFactory(
        config=config,
        initial_seed=42,
    )

    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        abstraction="bucket",
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=42,
    )

    trainer.train(
        factory,
        iterations=10,
    )

    strategies = (
        trainer.average_strategies()
    )

    index = trainer.strategy_index()

    state = next(
        iter(strategies)
    )

    range_strategy = (
        index.range_strategy(
            public_node=(
                state.public_node
            ),
            observer_seat=(
                state.observer_seat
            ),
        )
    )

    assert (
        state.own_hand_key
        in range_strategy
    )

    assert (
        range_strategy[
            state.own_hand_key
        ]
        == strategies[state]
    )

