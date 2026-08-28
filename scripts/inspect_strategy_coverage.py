import argparse
from collections import Counter
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
            "Inspect which information states "
            "are missing from a trained "
            "StrategyIndex on fresh deals."
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

    parser.add_argument(
        "--top",
        type=int,
        default=15,
    )

    return parser.parse_args()


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


def main() -> None:
    args = parse_args()

    if args.iterations <= 0:
        raise ValueError(
            "Iterations must be positive."
        )

    if args.evaluation_deals <= 0:
        raise ValueError(
            "Evaluation deals must be positive."
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
        "Strategy coverage diagnostic"
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

    print()
    print(
        "Training..."
    )

    started = perf_counter()

    trainer.train(
        training_factory,
        iterations=args.iterations,
    )

    print(
        f"  CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  training time: "
        f"{perf_counter() - started:.3f}s"
    )

    strategy_index = (
        trainer.strategy_index()
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
                trainer.resolved_draw_action_mode
            ),
            random_seed=(
                args.policy_seed
            ),
        )
    )

    evaluation_factory = (
        make_sequential_factory(
            stack=args.stack,
            initial_seed=(
                args.evaluation_seed
            ),
        )
    )

    phase_matched = Counter()
    phase_missing = Counter()

    missing_public_nodes = Counter()
    missing_private_keys = Counter()
    missing_information_states = Counter()

    matched_information_states = set()
    missing_information_state_set = set()

    total_decisions = 0

    print()
    print(
        "Evaluating fresh deals..."
    )

    evaluation_started = (
        perf_counter()
    )

    for _ in range(
        args.evaluation_deals
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
                    abstraction=(
                        args.abstraction
                    ),
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
                phase_missing[
                    phase
                ] += 1

                missing_public_nodes[
                    state.public_node
                ] += 1

                missing_private_keys[
                    (
                        phase,
                        state.own_hand_key,
                    )
                ] += 1

                missing_information_states[
                    state
                ] += 1

                missing_information_state_set.add(
                    state
                )

                normalized_strategy = (
                    evaluator
                    ._uniform_strategy(
                        actions
                    )
                )

            else:
                phase_matched[
                    phase
                ] += 1

                matched_information_states.add(
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

            total_decisions += 1

    elapsed = (
        perf_counter()
        - evaluation_started
    )

    print()
    print(
        "=" * 72
    )

    print(
        "OVERALL COVERAGE"
    )

    total_matched = sum(
        phase_matched.values()
    )

    total_missing = sum(
        phase_missing.values()
    )

    print(
        f"  matched decisions: "
        f"{total_matched:,}"
    )

    print(
        f"  missing decisions: "
        f"{total_missing:,}"
    )

    print(
        f"  total decisions: "
        f"{total_decisions:,}"
    )

    print(
        f"  coverage: "
        f"{coverage(total_matched, total_missing):.2%}"
    )

    print(
        f"  unique matched states: "
        f"{len(matched_information_states):,}"
    )

    print(
        f"  unique missing states: "
        f"{len(missing_information_state_set):,}"
    )

    print()
    print(
        "=" * 72
    )

    print(
        "PHASE COVERAGE"
    )

    phases = (
        "predraw_betting",
        "draw",
        "postdraw_betting",
    )

    for phase in phases:
        matched = (
            phase_matched[
                phase
            ]
        )

        missing = (
            phase_missing[
                phase
            ]
        )

        total = (
            matched
            + missing
        )

        print()
        print(
            f"  {phase}"
        )

        print(
            f"    matched: "
            f"{matched:,}"
        )

        print(
            f"    missing: "
            f"{missing:,}"
        )

        print(
            f"    total: "
            f"{total:,}"
        )

        print(
            f"    coverage: "
            f"{coverage(matched, missing):.2%}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "TOP MISSING PUBLIC NODES"
    )

    for (
        rank,
        (
            public_node,
            count,
        ),
    ) in enumerate(
        missing_public_nodes.most_common(
            args.top
        ),
        start=1,
    ):
        print()
        print(
            f"  #{rank}: "
            f"{count:,} missing decisions"
        )

        print(
            f"    phase: "
            f"{public_node.phase}"
        )

        print(
            f"    acting seat: "
            f"{public_node.acting_seat}"
        )

        print(
            f"    pot: "
            f"{public_node.pot}"
        )

        print(
            f"    current bet: "
            f"{public_node.current_bet}"
        )

        print(
            f"    history length: "
            f"{len(public_node.action_history)}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "TOP MISSING PRIVATE KEYS"
    )

    for (
        rank,
        (
            (
                phase,
                private_key,
            ),
            count,
        ),
    ) in enumerate(
        missing_private_keys.most_common(
            args.top
        ),
        start=1,
    ):
        print(
            f"  #{rank}: "
            f"{count:,} "
            f"[{phase}] "
            f"{private_key}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "TOP REPEATED MISSING INFORMATION STATES"
    )

    for (
        rank,
        (
            state,
            count,
        ),
    ) in enumerate(
        missing_information_states.most_common(
            args.top
        ),
        start=1,
    ):
        print()
        print(
            f"  #{rank}: "
            f"{count:,} occurrences"
        )

        print(
            f"    phase: "
            f"{phase_name(state)}"
        )

        print(
            f"    observer: "
            f"{state.observer_seat}"
        )

        print(
            f"    private key: "
            f"{state.own_hand_key}"
        )

        print(
            f"    pot: "
            f"{state.public_node.pot}"
        )

        print(
            f"    history length: "
            f"{len(state.public_node.action_history)}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "PERFORMANCE"
    )

    print(
        f"  evaluation time: "
        f"{elapsed:.3f}s"
    )

    print(
        f"  deals/second: "
        f"{args.evaluation_deals / elapsed:,.2f}"
    )


if __name__ == "__main__":
    main()