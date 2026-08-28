from solver.best_response import (
    SampledBestResponse,
)
from solver.game_state import (
    GameConfig,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_index import (
    StrategyIndex,
)


def make_game(
    seed: int,
) -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=20.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=seed,
    )


def test_responder_seat_must_be_valid() -> None:
    strategy_index = (
        StrategyIndex.from_strategies(
            {}
        )
    )

    try:
        SampledBestResponse(
            strategy_index=(
                strategy_index
            ),
            abstraction="bucket",
            responder_seat=2,
            max_draw=0,
            raise_sizes=(),
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_optimize_requires_positive_deals() -> None:
    strategy_index = (
        StrategyIndex.from_strategies(
            {}
        )
    )

    optimizer = SampledBestResponse(
        strategy_index=(
            strategy_index
        ),
        abstraction="bucket",
        responder_seat=0,
        max_draw=0,
        raise_sizes=(),
    )

    try:
        optimizer.optimize(
            lambda: make_game(42),
            deals=0,
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_sampled_response_returns_finite_values() -> None:
    strategy_index = (
        StrategyIndex.from_strategies(
            {}
        )
    )

    optimizer = SampledBestResponse(
        strategy_index=(
            strategy_index
        ),
        abstraction="bucket",
        responder_seat=0,
        max_draw=0,
        raise_sizes=(),
    )

    seed = 100

    def factory() -> SingleDrawGame:
        nonlocal seed

        game = make_game(
            seed
        )

        seed += 1

        return game

    result = optimizer.optimize(
        factory,
        deals=3,
        max_sweeps=1,
    )

    assert (
        result.deals
        == 3
    )

    assert (
        result.response_value
        == result.response_value
    )

    assert (
        result.baseline_value
        == result.baseline_value
    )

    assert (
        result.information_states
        > 0
    )


def test_response_improvement_can_be_measured_on_held_out_deals() -> None:
    strategy_index = (
        StrategyIndex.from_strategies(
            {}
        )
    )

    optimizer = SampledBestResponse(
        strategy_index=(
            strategy_index
        ),
        abstraction="bucket",
        responder_seat=0,
        max_draw=0,
        raise_sizes=(),
        random_seed=42,
    )

    training_seed = 200
    validation_seed = 1000

    def training_factory() -> SingleDrawGame:
        nonlocal training_seed

        game = make_game(
            training_seed
        )

        training_seed += 1

        return game

    def validation_factory() -> SingleDrawGame:
        nonlocal validation_seed

        game = make_game(
            validation_seed
        )

        validation_seed += 1

        return game

    result = optimizer.optimize(
        training_factory,
        deals=5,
        max_sweeps=2,
        validation_game_factory=(
            validation_factory
        ),
        validation_deals=7,
    )

    assert (
        result.training_deals
        == 5
    )

    assert (
        result.validation_deals
        == 7
    )

    assert (
        result.baseline_value
        == result.baseline_value
    )

    assert (
        result.response_value
        == result.response_value
    )

    assert (
        result.improvement
        == (
            result.response_value
            - result.baseline_value
        )
    )