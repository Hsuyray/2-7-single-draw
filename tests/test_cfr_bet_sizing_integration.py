from solver.bet_sizing_profiles import (
    FAST_BET_SIZING,
)
from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.legal_actions import (
    BettingAction,
)
from solver.training_factory import (
    TrainingGameFactory,
)


def _make_factory() -> TrainingGameFactory:
    config = GameConfig(
        player_count=2,
        starting_stack=10.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    return TrainingGameFactory(
        config=config,
        button_seat=0,
        initial_seed=42,
        alternate_button=True,
    )


def _make_trainer() -> CFRTrainer:
    return CFRTrainer(
        max_draw=1,
        raise_sizes=None,
        bet_sizing_policy=(
            FAST_BET_SIZING
        ),
        traversal_mode=(
            "external_sampling"
        ),
        abstraction="bucket",
        draw_action_mode="auto",
        random_seed=42,
    )


def _observed_raise_sizes(
    trainer: CFRTrainer,
) -> set[float]:
    strategies = (
        trainer.average_strategies()
    )

    raise_sizes: set[float] = set()

    for strategy in strategies.values():
        for action in strategy:
            if not isinstance(
                action,
                BettingAction,
            ):
                continue

            if action.raise_to is None:
                continue

            raise_sizes.add(
                action.raise_to
            )

    return raise_sizes


def test_policy_training_completes_iteration() -> None:
    factory = _make_factory()
    trainer = _make_trainer()

    trainer.train(
        factory,
        iterations=1,
    )

    assert (
        trainer.completed_iterations
        == 1
    )

    assert (
        factory.games_created
        == 1
    )


def test_policy_training_creates_nodes() -> None:
    factory = _make_factory()
    trainer = _make_trainer()

    trainer.train(
        factory,
        iterations=1,
    )

    strategies = (
        trainer.average_strategies()
    )

    assert strategies


def test_policy_training_creates_raise_actions() -> None:
    factory = _make_factory()
    trainer = _make_trainer()

    trainer.train(
        factory,
        iterations=1,
    )

    raise_sizes = (
        _observed_raise_sizes(
            trainer
        )
    )

    assert raise_sizes


def test_policy_raise_sizes_respect_stack() -> None:
    factory = _make_factory()
    trainer = _make_trainer()

    trainer.train(
        factory,
        iterations=1,
    )

    raise_sizes = (
        _observed_raise_sizes(
            trainer
        )
    )

    assert raise_sizes

    assert all(
        0 < raise_to <= 10.0
        for raise_to in raise_sizes
    )


def test_policy_training_is_reproducible() -> None:
    first_factory = _make_factory()
    first_trainer = _make_trainer()

    second_factory = _make_factory()
    second_trainer = _make_trainer()

    first_trainer.train(
        first_factory,
        iterations=1,
    )

    second_trainer.train(
        second_factory,
        iterations=1,
    )

    assert (
        first_trainer.average_strategies()
        == second_trainer.average_strategies()
    )

    assert (
        _observed_raise_sizes(
            first_trainer
        )
        == _observed_raise_sizes(
            second_trainer
        )
    )


def test_empty_raise_sizes_still_disable_raises() -> None:
    factory = _make_factory()

    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        bet_sizing_policy=(
            FAST_BET_SIZING
        ),
        traversal_mode=(
            "external_sampling"
        ),
        abstraction="bucket",
        draw_action_mode="auto",
        random_seed=42,
    )

    trainer.train(
        factory,
        iterations=1,
    )

    assert (
        _observed_raise_sizes(
            trainer
        )
        == set()
    )

