import argparse
from pathlib import Path
import sys
from time import perf_counter


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from solver.bet_sizing import (  # noqa: E402
    FAST_BET_SIZING,
    FULL_BET_SIZING,
    BetSizingPolicy,
)
from solver.cfr_trainer import CFRTrainer  # noqa: E402
from solver.game_state import GameConfig  # noqa: E402
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)
from solver.strategy_profile_evaluator import (  # noqa: E402
    StrategyProfileEvaluator,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train a CFR strategy and evaluate "
            "its average-strategy profile on "
            "fresh Monte Carlo deals."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--evaluation-deals",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--abstraction",
        choices=(
            "exact",
            "bucket",
        ),
        default="bucket",
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--max-draw",
        type=int,
        choices=range(0, 6),
        default=1,
    )

    parser.add_argument(
        "--bet-sizing",
        choices=(
            "none",
            "fast",
            "full",
        ),
        default="fast",
    )

    parser.add_argument(
        "--training-seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--evaluation-seed",
        type=int,
        default=100000,
    )

    parser.add_argument(
        "--policy-seed",
        type=int,
        default=777,
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.iterations <= 0:
        raise ValueError(
            "Iterations must be positive."
        )

    if args.evaluation_deals <= 0:
        raise ValueError(
            "Evaluation deals must be "
            "positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Stack must be positive."
        )


def resolve_bet_sizing(
    mode: str,
) -> tuple[
    tuple[float, ...] | None,
    BetSizingPolicy | None,
]:
    if mode == "none":
        return (
            (),
            None,
        )

    if mode == "fast":
        return (
            None,
            FAST_BET_SIZING,
        )

    if mode == "full":
        return (
            None,
            FULL_BET_SIZING,
        )

    raise ValueError(
        "Unknown bet sizing mode."
    )


def make_sequential_factory(
    *,
    stack: float,
    initial_seed: int,
):
    game_counter = 0

    def game_factory() -> SingleDrawGame:
        nonlocal game_counter

        game = SingleDrawGame(
            config=GameConfig(
                player_count=2,
                starting_stack=stack,
                small_blind=1.0,
                big_blind=2.0,
                big_blind_ante=1.5,
            ),
            button_seat=0,
            deck_seed=(
                initial_seed
                + game_counter
            ),
        )

        game_counter += 1

        return game

    return game_factory


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    (
        raise_sizes,
        bet_sizing_policy,
    ) = resolve_bet_sizing(
        args.bet_sizing
    )

    training_factory = (
        make_sequential_factory(
            stack=args.stack,
            initial_seed=(
                args.training_seed
            ),
        )
    )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
        abstraction=args.abstraction,
        traversal_mode=(
            "external_sampling"
        ),
        draw_action_mode="auto",
        random_seed=(
            args.training_seed
        ),
    )

    print(
        "Strategy profile evaluation"
    )

    print(
        f"  training iterations: "
        f"{args.iterations:,}"
    )

    print(
        f"  evaluation deals: "
        f"{args.evaluation_deals:,}"
    )

    print(
        f"  abstraction: "
        f"{args.abstraction}"
    )

    print(
        f"  bet sizing: "
        f"{args.bet_sizing}"
    )

    print(
        f"  stack: "
        f"{args.stack:g}"
    )

    print(
        f"  max draw: "
        f"{args.max_draw}"
    )

    print(
        f"  training seeds: "
        f"{args.training_seed:,}..."
    )

    print(
        f"  evaluation seeds: "
        f"{args.evaluation_seed:,}..."
    )

    print()

    print(
        "Training..."
    )

    training_start = (
        perf_counter()
    )

    trainer.train(
        training_factory,
        iterations=args.iterations,
    )

    training_elapsed = (
        perf_counter()
        - training_start
    )

    print(
        f"  CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  completed iterations: "
        f"{trainer.completed_iterations:,}"
    )

    print(
        f"  training time: "
        f"{training_elapsed:.3f}s"
    )

    print()

    print(
        "Building average strategy index..."
    )

    strategy_index = (
        trainer.strategy_index()
    )

    print(
        f"  information states: "
        f"{len(strategy_index):,}"
    )

    evaluation_factory = (
        make_sequential_factory(
            stack=args.stack,
            initial_seed=(
                args.evaluation_seed
            ),
        )
    )

    evaluator = (
        StrategyProfileEvaluator(
            strategy_index=(
                strategy_index
            ),
            abstraction=(
                args.abstraction
            ),
            max_draw=args.max_draw,
            raise_sizes=raise_sizes,
            bet_sizing_policy=(
                bet_sizing_policy
            ),
            draw_action_mode=(
                trainer
                .resolved_draw_action_mode
            ),
            random_seed=(
                args.policy_seed
            ),
        )
    )

    print()

    print(
        "Evaluating fresh deals..."
    )

    evaluation_start = (
        perf_counter()
    )

    result = evaluator.evaluate(
        evaluation_factory,
        deals=(
            args.evaluation_deals
        ),
    )

    evaluation_elapsed = (
        perf_counter()
        - evaluation_start
    )

    print()

    print(
        "=" * 72
    )

    print(
        "RESULT"
    )

    print(
        f"  deals: "
        f"{result.deals:,}"
    )

    print(
        f"  seat 0 utility/deal: "
        f"{result.seat_0_utility:+.6f}"
    )

    print(
        f"  seat 1 utility/deal: "
        f"{result.seat_1_utility:+.6f}"
    )

    print(
        f"  zero-sum error: "
        f"{result.zero_sum_error:.12f}"
    )

    print()

    print(
        f"  matched strategy decisions: "
        f"{result.strategy_decisions:,}"
    )

    print(
        f"  missing strategy decisions: "
        f"{result.missing_strategy_decisions:,}"
    )

    print(
        f"  total decisions: "
        f"{result.total_decisions:,}"
    )

    print(
        f"  strategy coverage: "
        f"{result.strategy_coverage:.2%}"
    )

    print()

    print(
        f"  evaluation time: "
        f"{evaluation_elapsed:.3f}s"
    )

    print(
        f"  deals/second: "
        f"{result.deals / evaluation_elapsed:,.2f}"
    )

    print()

    if (
        result.zero_sum_error
        > 1e-9
    ):
        print(
            "WARNING: profile utility is "
            "not numerically zero-sum."
        )

    if (
        result.strategy_coverage
        < 0.90
    ):
        print(
            "WARNING: strategy coverage is "
            "below 90%; profile value is "
            "strongly affected by uniform "
            "fallback play."
        )

    elif (
        result.strategy_coverage
        < 0.99
    ):
        print(
            "NOTE: strategy coverage is "
            "below 99%; some evaluation "
            "decisions still use uniform "
            "fallback."
        )

    else:
        print(
            "Strategy lookup coverage is "
            "at least 99%."
        )


if __name__ == "__main__":
    main()