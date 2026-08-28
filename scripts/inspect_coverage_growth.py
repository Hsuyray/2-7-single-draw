import argparse
from copy import deepcopy
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
from solver.information_state import (  # noqa: E402
    InformationState,
)
from solver.single_draw_game import (  # noqa: E402
    GamePhase,
    SingleDrawGame,
)
from solver.strategy_profile_evaluator import (  # noqa: E402
    StrategyProfileEvaluator,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Track strategy lookup coverage "
            "while one CFR trainer continues "
            "training."
        )
    )

    parser.add_argument(
        "--checkpoints",
        type=str,
        default="500,1000,2000,4000",
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


def parse_checkpoints(
    raw: str,
) -> tuple[int, ...]:
    try:
        values = tuple(
            int(value.strip())
            for value in raw.split(",")
            if value.strip()
        )
    except ValueError as error:
        raise ValueError(
            "Checkpoints must be "
            "comma-separated integers."
        ) from error

    if not values:
        raise ValueError(
            "At least one checkpoint "
            "is required."
        )

    if any(
        value <= 0
        for value in values
    ):
        raise ValueError(
            "Checkpoints must be positive."
        )

    if values != tuple(
        sorted(values)
    ):
        raise ValueError(
            "Checkpoints must be ascending."
        )

    if len(
        set(values)
    ) != len(values):
        raise ValueError(
            "Checkpoints must be unique."
        )

    return values


def resolve_bet_sizing(
    mode: str,
) -> tuple[
    tuple[float, ...] | None,
    BetSizingPolicy | None,
]:
    if mode == "none":
        return (), None

    if mode == "fast":
        return None, FAST_BET_SIZING

    if mode == "full":
        return None, FULL_BET_SIZING

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


def phase_name(
    state: InformationState,
) -> str:
    value = getattr(
        state.phase,
        "value",
        None,
    )

    if value is not None:
        return str(value)

    return str(state.phase)


def coverage(
    matched: int,
    missing: int,
) -> float:
    total = (
        matched
        + missing
    )

    if total == 0:
        return 1.0

    return (
        matched
        / total
    )


def evaluate_coverage(
    *,
    trainer: CFRTrainer,
    abstraction: str,
    max_draw: int,
    raise_sizes,
    bet_sizing_policy,
    stack: float,
    evaluation_deals: int,
    evaluation_seed: int,
    policy_seed: int,
) -> dict:
    strategy_index = (
        trainer.strategy_index()
    )

    evaluator = (
        StrategyProfileEvaluator(
            strategy_index=(
                strategy_index
            ),
            abstraction=abstraction,
            max_draw=max_draw,
            raise_sizes=raise_sizes,
            bet_sizing_policy=(
                bet_sizing_policy
            ),
            draw_action_mode=(
                trainer.resolved_draw_action_mode
            ),
            random_seed=(
                policy_seed
            ),
        )
    )

    evaluation_factory = (
        make_sequential_factory(
            stack=stack,
            initial_seed=(
                evaluation_seed
            ),
        )
    )

    phase_matched = {
        "predraw_betting": 0,
        "draw": 0,
        "postdraw_betting": 0,
    }

    phase_missing = {
        "predraw_betting": 0,
        "draw": 0,
        "postdraw_betting": 0,
    }

    unique_matched = set()
    unique_missing = set()

    for _ in range(
        evaluation_deals
    ):
        game = deepcopy(
            evaluation_factory()
        )

        while (
            game.phase
            != GamePhase.COMPLETE
        ):
            acting_seat = (
                game.acting_seat
            )

            if acting_seat is None:
                raise RuntimeError(
                    "Non-terminal game has "
                    "no acting player."
                )

            actions = (
                evaluator._solver_actions(
                    game
                )
            )

            if not actions:
                raise RuntimeError(
                    "Non-terminal game has "
                    "no legal solver actions."
                )

            state = (
                InformationState.from_game(
                    game,
                    observer_seat=(
                        acting_seat
                    ),
                    abstraction=abstraction,
                )
            )

            phase = phase_name(
                state
            )

            strategy = (
                strategy_index
                .strategy_for_hand(
                    public_node=(
                        state.public_node
                    ),
                    observer_seat=(
                        acting_seat
                    ),
                    hand_key=(
                        state.own_hand_key
                    ),
                )
            )

            if strategy is None:
                phase_missing.setdefault(
                    phase,
                    0,
                )

                phase_missing[
                    phase
                ] += 1

                unique_missing.add(
                    state
                )

                normalized_strategy = (
                    evaluator
                    ._uniform_strategy(
                        actions
                    )
                )

            else:
                phase_matched.setdefault(
                    phase,
                    0,
                )

                phase_matched[
                    phase
                ] += 1

                unique_matched.add(
                    state
                )

                normalized_strategy = (
                    evaluator
                    ._normalized_strategy(
                        actions=actions,
                        strategy=strategy,
                    )
                )

            action = (
                evaluator._sample_action(
                    actions=actions,
                    strategy=(
                        normalized_strategy
                    ),
                )
            )

            game = (
                evaluator._apply_action(
                    game=game,
                    action=action,
                )
            )

    total_matched = sum(
        phase_matched.values()
    )

    total_missing = sum(
        phase_missing.values()
    )

    phase_coverage = {}

    for phase in (
        "predraw_betting",
        "draw",
        "postdraw_betting",
    ):
        phase_coverage[
            phase
        ] = coverage(
            phase_matched.get(
                phase,
                0,
            ),
            phase_missing.get(
                phase,
                0,
            ),
        )

    return {
        "overall": coverage(
            total_matched,
            total_missing,
        ),
        "predraw": (
            phase_coverage[
                "predraw_betting"
            ]
        ),
        "draw": (
            phase_coverage[
                "draw"
            ]
        ),
        "postdraw": (
            phase_coverage[
                "postdraw_betting"
            ]
        ),
        "matched": total_matched,
        "missing": total_missing,
        "unique_matched": len(
            unique_matched
        ),
        "unique_missing": len(
            unique_missing
        ),
    }


def print_result(
    *,
    checkpoint: int,
    trainer: CFRTrainer,
    result: dict,
    elapsed: float,
) -> None:
    print()

    print(
        "=" * 72
    )

    print(
        f"ITERATION {checkpoint:,}"
    )

    print(
        f"  CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  cumulative training time: "
        f"{elapsed:.3f}s"
    )

    print()

    print(
        f"  overall coverage: "
        f"{result['overall']:.2%}"
    )

    print(
        f"  predraw coverage: "
        f"{result['predraw']:.2%}"
    )

    print(
        f"  draw coverage: "
        f"{result['draw']:.2%}"
    )

    print(
        f"  postdraw coverage: "
        f"{result['postdraw']:.2%}"
    )

    print()

    print(
        f"  matched decisions: "
        f"{result['matched']:,}"
    )

    print(
        f"  missing decisions: "
        f"{result['missing']:,}"
    )

    print(
        f"  unique matched states: "
        f"{result['unique_matched']:,}"
    )

    print(
        f"  unique missing states: "
        f"{result['unique_missing']:,}"
    )


def main() -> None:
    args = parse_args()

    checkpoints = (
        parse_checkpoints(
            args.checkpoints
        )
    )

    if args.evaluation_deals <= 0:
        raise ValueError(
            "Evaluation deals must be positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Stack must be positive."
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
        "Strategy coverage growth diagnostic"
    )

    print(
        f"  checkpoints: "
        f"{checkpoints}"
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

    completed = 0

    training_started = (
        perf_counter()
    )

    results = []

    for checkpoint in checkpoints:
        additional_iterations = (
            checkpoint
            - completed
        )

        print()

        print(
            f"Training to "
            f"{checkpoint:,} iterations..."
        )

        trainer.train(
            training_factory,
            iterations=(
                additional_iterations
            ),
        )

        print(
            "Evaluating fixed fresh-deal "
            "sample..."
        )

        result = evaluate_coverage(
            trainer=trainer,
            abstraction=(
                args.abstraction
            ),
            max_draw=args.max_draw,
            raise_sizes=raise_sizes,
            bet_sizing_policy=(
                bet_sizing_policy
            ),
            stack=args.stack,
            evaluation_deals=(
                args.evaluation_deals
            ),
            evaluation_seed=(
                args.evaluation_seed
            ),
            policy_seed=(
                args.policy_seed
            ),
        )

        elapsed = (
            perf_counter()
            - training_started
        )

        print_result(
            checkpoint=checkpoint,
            trainer=trainer,
            result=result,
            elapsed=elapsed,
        )

        results.append(
            (
                checkpoint,
                result,
            )
        )

        completed = checkpoint

    print()

    print(
        "=" * 72
    )

    print(
        "COVERAGE CURVE"
    )

    print()

    print(
        "iterations | overall | predraw | draw | postdraw"
    )

    for (
        checkpoint,
        result,
    ) in results:
        print(
            f"{checkpoint:>10,} | "
            f"{result['overall']:>7.2%} | "
            f"{result['predraw']:>7.2%} | "
            f"{result['draw']:>7.2%} | "
            f"{result['postdraw']:>8.2%}"
        )


if __name__ == "__main__":
    main()