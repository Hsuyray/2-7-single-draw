from solver.game_state import (
    GameConfig,
)
from solver.strategy_index import (
    StrategyIndex,
)
from solver.strategy_profile_evaluator import (
    StrategyProfileEvaluator,
)
from solver.single_draw_game import (
    SingleDrawGame,
)


def make_game(
    seed: int = 42,
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


def test_evaluation_requires_positive_deals() -> None:
    evaluator = StrategyProfileEvaluator(
        strategy_index=(
            StrategyIndex.from_strategies(
                {}
            )
        ),
        abstraction="bucket",
        max_draw=1,
        raise_sizes=(),
    )

    try:
        evaluator.evaluate(
            lambda: make_game(),
            deals=0,
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_empty_strategy_uses_uniform_fallback() -> None:
    evaluator = StrategyProfileEvaluator(
        strategy_index=(
            StrategyIndex.from_strategies(
                {}
            )
        ),
        abstraction="bucket",
        max_draw=0,
        raise_sizes=(),
        random_seed=42,
    )

    result = evaluator.evaluate(
        lambda: make_game(),
        deals=5,
    )

    assert (
        result.deals
        == 5
    )

    assert (
        result.missing_strategy_decisions
        > 0
    )

    assert (
        result.strategy_coverage
        == 0.0
    )


def test_profile_evaluation_is_zero_sum() -> None:
    evaluator = StrategyProfileEvaluator(
        strategy_index=(
            StrategyIndex.from_strategies(
                {}
            )
        ),
        abstraction="bucket",
        max_draw=0,
        raise_sizes=(),
        random_seed=7,
    )

    seed = 100

    def factory() -> SingleDrawGame:
        nonlocal seed

        game = make_game(
            seed
        )

        seed += 1

        return game

    result = evaluator.evaluate(
        factory,
        deals=20,
    )

    assert (
        result.zero_sum_error
        < 1e-9
    )