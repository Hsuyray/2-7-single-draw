import argparse
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
import sys
from typing import Literal


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
from solver.cfr_trainer import (  # noqa: E402
    CFRTrainer,
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.information_state import (  # noqa: E402
    AbstractionMode,
    InformationState,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


SeedMode = Literal[
    "fixed",
    "sequential",
]


@dataclass(frozen=True)
class StrategySnapshot:
    iteration: int

    strategies: dict[
        InformationState,
        dict[
            object,
            float,
        ],
    ]

    strategy_weights: dict[
        InformationState,
        float,
    ]


@dataclass(frozen=True)
class Comparison:
    start_iteration: int
    end_iteration: int

    common_nodes: int
    strategic_nodes: int

    average_l1: float
    median_l1: float
    maximum_l1: float

    l1_ge_025: int
    l1_ge_050: int
    l1_ge_100: int

    weighted_nodes: int
    weighted_average_l1: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure stability of CFR average "
            "strategies across training "
            "iteration checkpoints."
        )
    )

    parser.add_argument(
        "--checkpoints",
        type=str,
        default="100,300,1000,3000",
        help=(
            "Comma-separated cumulative "
            "iteration checkpoints."
        ),
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
        choices=range(
            0,
            6,
        ),
        default=1,
    )

    parser.add_argument(
        "--traversal-mode",
        choices=(
            "full",
            "external_sampling",
        ),
        default="external_sampling",
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
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--seed-mode",
        choices=(
            "fixed",
            "sequential",
        ),
        default="fixed",
    )

    parser.add_argument(
        "--min-strategy-weight",
        type=float,
        default=0.01,
        help=(
            "Minimum cumulative strategy "
            "weight used for the weighted "
            "comparison."
        ),
    )

    return parser.parse_args()


def parse_checkpoints(
    raw: str,
) -> tuple[int, ...]:
    try:
        checkpoints = tuple(
            int(value.strip())
            for value in raw.split(",")
            if value.strip()
        )
    except ValueError as error:
        raise ValueError(
            "Checkpoints must be "
            "comma-separated integers."
        ) from error

    if len(checkpoints) < 2:
        raise ValueError(
            "At least two checkpoints "
            "are required."
        )

    if any(
        checkpoint <= 0
        for checkpoint in checkpoints
    ):
        raise ValueError(
            "All checkpoints must be "
            "positive."
        )

    if tuple(
        sorted(
            checkpoints
        )
    ) != checkpoints:
        raise ValueError(
            "Checkpoints must be in "
            "ascending order."
        )

    if len(
        set(
            checkpoints
        )
    ) != len(
        checkpoints
    ):
        raise ValueError(
            "Checkpoints must be unique."
        )

    return checkpoints


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.stack <= 0:
        raise ValueError(
            "Stack must be positive."
        )

    if args.min_strategy_weight < 0:
        raise ValueError(
            "Minimum strategy weight "
            "cannot be negative."
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


def make_game_factory(
    *,
    stack: float,
    seed: int,
    seed_mode: SeedMode,
):
    game_counter = 0

    def game_factory() -> SingleDrawGame:
        nonlocal game_counter

        if seed_mode == "fixed":
            game_seed = seed
        else:
            game_seed = (
                seed
                + game_counter
            )

        game_counter += 1

        return SingleDrawGame(
            config=GameConfig(
                player_count=2,
                starting_stack=stack,
                small_blind=1.0,
                big_blind=2.0,
                big_blind_ante=1.5,
            ),
            button_seat=0,
            deck_seed=game_seed,
        )

    return game_factory


def mapping_values(
    mapping,
    actions,
) -> tuple[float, ...]:
    if mapping is None:
        return ()

    if isinstance(
        mapping,
        dict,
    ):
        return tuple(
            float(
                mapping.get(
                    action,
                    0.0,
                )
            )
            for action in actions
        )

    try:
        return tuple(
            float(value)
            for value in mapping
        )
    except TypeError:
        return ()


def node_strategy_sum(
    node,
) -> tuple[float, ...]:
    names = (
        "strategy_sum",
        "strategy_sums",
        "cumulative_strategy",
        "cumulative_strategies",
    )

    for name in names:
        value = getattr(
            node,
            name,
            None,
        )

        if value is None:
            continue

        values = mapping_values(
            value,
            node.actions,
        )

        if values:
            return values

    return ()


def strategy_weight(
    node,
) -> float:
    return sum(
        node_strategy_sum(
            node
        )
    )


def make_snapshot(
    *,
    trainer: CFRTrainer,
    iteration: int,
) -> StrategySnapshot:
    strategies: dict[
        InformationState,
        dict[
            object,
            float,
        ],
    ] = {}

    weights: dict[
        InformationState,
        float,
    ] = {}

    for (
        information_state,
        node,
    ) in trainer.node_store.nodes.items():
        if len(
            node.actions
        ) <= 1:
            continue

        average = (
            node.average_strategy()
        )

        strategies[
            information_state
        ] = {
            action: float(
                average.get(
                    action,
                    0.0,
                )
            )
            for action in node.actions
        }

        weights[
            information_state
        ] = strategy_weight(
            node
        )

    return StrategySnapshot(
        iteration=iteration,
        strategies=strategies,
        strategy_weights=weights,
    )


def strategy_l1(
    first: dict[
        object,
        float,
    ],
    second: dict[
        object,
        float,
    ],
) -> float | None:
    if set(
        first
    ) != set(
        second
    ):
        return None

    return sum(
        abs(
            first[action]
            - second[action]
        )
        for action in first
    )


def compare_snapshots(
    *,
    first: StrategySnapshot,
    second: StrategySnapshot,
    min_strategy_weight: float,
) -> Comparison:
    common_states = (
        set(
            first.strategies
        )
        & set(
            second.strategies
        )
    )

    distances: list[
        float
    ] = []

    weighted_distances: list[
        tuple[
            float,
            float,
        ]
    ] = []

    for state in common_states:
        distance = strategy_l1(
            first.strategies[
                state
            ],
            second.strategies[
                state
            ],
        )

        if distance is None:
            continue

        distances.append(
            distance
        )

        weight = min(
            first.strategy_weights.get(
                state,
                0.0,
            ),
            second.strategy_weights.get(
                state,
                0.0,
            ),
        )

        if (
            weight
            >= min_strategy_weight
        ):
            weighted_distances.append(
                (
                    distance,
                    weight,
                )
            )

    if not distances:
        return Comparison(
            start_iteration=(
                first.iteration
            ),
            end_iteration=(
                second.iteration
            ),
            common_nodes=len(
                common_states
            ),
            strategic_nodes=0,
            average_l1=0.0,
            median_l1=0.0,
            maximum_l1=0.0,
            l1_ge_025=0,
            l1_ge_050=0,
            l1_ge_100=0,
            weighted_nodes=0,
            weighted_average_l1=0.0,
        )

    weighted_total = sum(
        weight
        for (
            _distance,
            weight,
        ) in weighted_distances
    )

    if weighted_total > 0:
        weighted_average = (
            sum(
                distance
                * weight
                for (
                    distance,
                    weight,
                ) in weighted_distances
            )
            / weighted_total
        )
    else:
        weighted_average = 0.0

    return Comparison(
        start_iteration=(
            first.iteration
        ),
        end_iteration=(
            second.iteration
        ),
        common_nodes=len(
            common_states
        ),
        strategic_nodes=len(
            distances
        ),
        average_l1=mean(
            distances
        ),
        median_l1=median(
            distances
        ),
        maximum_l1=max(
            distances
        ),
        l1_ge_025=sum(
            distance >= 0.25
            for distance in distances
        ),
        l1_ge_050=sum(
            distance >= 0.50
            for distance in distances
        ),
        l1_ge_100=sum(
            distance >= 1.00
            for distance in distances
        ),
        weighted_nodes=len(
            weighted_distances
        ),
        weighted_average_l1=(
            weighted_average
        ),
    )


def print_snapshot(
    snapshot: StrategySnapshot,
) -> None:
    weights = tuple(
        snapshot.strategy_weights.values()
    )

    zero_weight_nodes = sum(
        weight <= 1e-12
        for weight in weights
    )

    print(
        f"  iteration "
        f"{snapshot.iteration:,}: "
        f"{len(snapshot.strategies):,} "
        f"strategic nodes, "
        f"{zero_weight_nodes:,} "
        f"zero-weight"
    )


def print_comparison(
    comparison: Comparison,
) -> None:
    count = (
        comparison.strategic_nodes
    )

    print()
    print(
        f"{comparison.start_iteration:,} "
        f"-> "
        f"{comparison.end_iteration:,}"
    )

    print(
        f"  common strategic nodes: "
        f"{count:,}"
    )

    print(
        f"  average L1: "
        f"{comparison.average_l1:.6f}"
    )

    print(
        f"  median L1: "
        f"{comparison.median_l1:.6f}"
    )

    print(
        f"  maximum L1: "
        f"{comparison.maximum_l1:.6f}"
    )

    if count > 0:
        print(
            f"  L1 >= 0.25: "
            f"{comparison.l1_ge_025:,} "
            f"("
            f"{comparison.l1_ge_025 / count:.2%}"
            f")"
        )

        print(
            f"  L1 >= 0.50: "
            f"{comparison.l1_ge_050:,} "
            f"("
            f"{comparison.l1_ge_050 / count:.2%}"
            f")"
        )

        print(
            f"  L1 >= 1.00: "
            f"{comparison.l1_ge_100:,} "
            f"("
            f"{comparison.l1_ge_100 / count:.2%}"
            f")"
        )

    print(
        f"  weighted nodes: "
        f"{comparison.weighted_nodes:,}"
    )

    print(
        f"  weighted average L1: "
        f"{comparison.weighted_average_l1:.6f}"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    checkpoints = (
        parse_checkpoints(
            args.checkpoints
        )
    )

    (
        raise_sizes,
        bet_sizing_policy,
    ) = resolve_bet_sizing(
        args.bet_sizing
    )

    abstraction: AbstractionMode = (
        args.abstraction
    )

    seed_mode: SeedMode = (
        args.seed_mode
    )

    game_factory = make_game_factory(
        stack=args.stack,
        seed=args.seed,
        seed_mode=seed_mode,
    )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
        abstraction=abstraction,
        traversal_mode=(
            args.traversal_mode
        ),
        draw_action_mode="auto",
        random_seed=args.seed,
    )

    print(
        "Average-strategy convergence "
        "diagnostic"
    )

    print(
        f"  checkpoints: "
        f"{checkpoints}"
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
        f"  seed mode: "
        f"{args.seed_mode}"
    )

    print(
        f"  min strategy weight: "
        f"{args.min_strategy_weight:g}"
    )

    snapshots: list[
        StrategySnapshot
    ] = []

    completed = 0

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
            game_factory,
            iterations=(
                additional_iterations
            ),
        )

        snapshot = make_snapshot(
            trainer=trainer,
            iteration=checkpoint,
        )

        snapshots.append(
            snapshot
        )

        print_snapshot(
            snapshot
        )

        completed = checkpoint

    print()
    print(
        "=" * 72
    )

    print(
        "CONSECUTIVE SNAPSHOT COMPARISONS"
    )

    for index in range(
        1,
        len(
            snapshots
        ),
    ):
        comparison = (
            compare_snapshots(
                first=(
                    snapshots[
                        index - 1
                    ]
                ),
                second=(
                    snapshots[
                        index
                    ]
                ),
                min_strategy_weight=(
                    args.min_strategy_weight
                ),
            )
        )

        print_comparison(
            comparison
        )

    print()
    print(
        "=" * 72
    )

    print(
        "FIRST VS FINAL"
    )

    final_comparison = (
        compare_snapshots(
            first=snapshots[0],
            second=snapshots[-1],
            min_strategy_weight=(
                args.min_strategy_weight
            ),
        )
    )

    print_comparison(
        final_comparison
    )


if __name__ == "__main__":
    main()