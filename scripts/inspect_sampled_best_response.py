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


from solver.best_response import (  # noqa: E402
    SampledBestResponse,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train a CFR strategy, optimize a "
            "sampled information-set response "
            "on training deals, and evaluate "
            "it on independent held-out deals."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--response-deals",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--validation-deals",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--sweeps",
        type=int,
        default=2,
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
        "--response-seed",
        type=int,
        default=100000,
    )

    parser.add_argument(
        "--validation-seed",
        type=int,
        default=200000,
    )

    parser.add_argument(
        "--response-policy-seed",
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

    if args.response_deals <= 0:
        raise ValueError(
            "Response deals must be positive."
        )

    if args.validation_deals <= 0:
        raise ValueError(
            "Validation deals must be positive."
        )

    if args.sweeps <= 0:
        raise ValueError(
            "Sweeps must be positive."
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
    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter

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
                + counter
            ),
        )

        counter += 1

        return game

    return factory


def print_result(
    *,
    seat: int,
    result,
    elapsed: float,
) -> None:
    print()

    print(
        "=" * 72
    )

    print(
        f"SEAT {seat} RESPONSE"
    )

    print(
        f"  response-training deals: "
        f"{result.training_deals:,}"
    )

    print(
        f"  validation deals: "
        f"{result.validation_deals:,}"
    )

    print(
        f"  sweeps: "
        f"{result.sweeps:,}"
    )

    print()

    print(
        f"  held-out CFR profile value: "
        f"{result.baseline_value:+.6f}"
    )

    print(
        f"  held-out response value: "
        f"{result.response_value:+.6f}"
    )

    print(
        f"  held-out response gain: "
        f"{result.improvement:+.6f}"
    )

    print()

    print(
        f"  responder information states: "
        f"{result.information_states:,}"
    )

    print(
        f"  changed actions: "
        f"{result.changed_actions:,}"
    )

    print()

    print(
        f"  opponent strategy hits: "
        f"{result.opponent_strategy_hits:,}"
    )

    print(
        f"  opponent strategy misses: "
        f"{result.opponent_strategy_misses:,}"
    )

    print(
        f"  opponent strategy coverage: "
        f"{result.opponent_strategy_coverage:.2%}"
    )

    print()

    print(
        f"  elapsed: "
        f"{elapsed:.3f}s"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    if (
        args.response_seed
        == args.validation_seed
    ):
        raise ValueError(
            "Response and validation seeds "
            "must be different."
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
        abstraction=(
            args.abstraction
        ),
        traversal_mode=(
            "external_sampling"
        ),
        draw_action_mode="auto",
        random_seed=(
            args.training_seed
        ),
    )

    print(
        "Held-out sampled response diagnostic"
    )

    print(
        f"  CFR training iterations: "
        f"{args.iterations:,}"
    )

    print(
        f"  response-training deals: "
        f"{args.response_deals:,}"
    )

    print(
        f"  validation deals: "
        f"{args.validation_deals:,}"
    )

    print(
        f"  sweeps: "
        f"{args.sweeps:,}"
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
        f"  max draw: "
        f"{args.max_draw}"
    )

    print(
        f"  CFR training seed: "
        f"{args.training_seed:,}"
    )

    print(
        f"  response seed: "
        f"{args.response_seed:,}"
    )

    print(
        f"  validation seed: "
        f"{args.validation_seed:,}"
    )

    print()

    print(
        "Training CFR..."
    )

    training_start = (
        perf_counter()
    )

    trainer.train(
        training_factory,
        iterations=(
            args.iterations
        ),
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
        f"  training time: "
        f"{training_elapsed:.3f}s"
    )

    strategy_index = (
        trainer.strategy_index()
    )

    results = {}

    for responder_seat in (
        0,
        1,
    ):
        response_factory = (
            make_sequential_factory(
                stack=args.stack,
                initial_seed=(
                    args.response_seed
                ),
            )
        )

        validation_factory = (
            make_sequential_factory(
                stack=args.stack,
                initial_seed=(
                    args.validation_seed
                ),
            )
        )

        optimizer = (
            SampledBestResponse(
                strategy_index=(
                    strategy_index
                ),
                abstraction=(
                    args.abstraction
                ),
                responder_seat=(
                    responder_seat
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
                    args.response_policy_seed
                    + responder_seat
                ),
            )
        )

        print()

        print(
            f"Optimizing seat "
            f"{responder_seat} response..."
        )

        started = (
            perf_counter()
        )

        result = (
            optimizer.optimize(
                response_factory,
                deals=(
                    args.response_deals
                ),
                max_sweeps=(
                    args.sweeps
                ),
                validation_game_factory=(
                    validation_factory
                ),
                validation_deals=(
                    args.validation_deals
                ),
            )
        )

        elapsed = (
            perf_counter()
            - started
        )

        results[
            responder_seat
        ] = result

        print_result(
            seat=responder_seat,
            result=result,
            elapsed=elapsed,
        )

    seat_0 = results[0]
    seat_1 = results[1]

    total_response_gain = (
        seat_0.improvement
        + seat_1.improvement
    )

    average_response_gain = (
        total_response_gain
        / 2.0
    )

    profile_zero_sum_error = abs(
        seat_0.baseline_value
        + seat_1.baseline_value
    )

    print()

    print(
        "=" * 72
    )

    print(
        "SUMMARY"
    )

    print(
        f"  seat 0 held-out gain: "
        f"{seat_0.improvement:+.6f}"
    )

    print(
        f"  seat 1 held-out gain: "
        f"{seat_1.improvement:+.6f}"
    )

    print()

    print(
        f"  total held-out gain: "
        f"{total_response_gain:+.6f}"
    )

    print(
        f"  average held-out gain: "
        f"{average_response_gain:+.6f}"
    )

    print()

    print(
        f"  held-out profile "
        f"zero-sum error: "
        f"{profile_zero_sum_error:.12f}"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "  This is still NOT exact "
        "exploitability."
    )

    print(
        "  The response policy was learned "
        "on one sampled deal set and "
        "evaluated on a separate held-out "
        "deal set."
    )


if __name__ == "__main__":
    main()