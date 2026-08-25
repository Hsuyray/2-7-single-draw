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
from solver.cfr_trainer import CFRTrainer  # noqa: E402
from solver.game_state import GameConfig  # noqa: E402
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


SeedMode = Literal[
    "fixed",
    "sequential",
]


@dataclass(frozen=True)
class Snapshot:
    iteration: int
    strategies: dict
    weights: dict
    phases: dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure average-strategy "
            "convergence on a fixed cohort "
            "of information states."
        )
    )

    parser.add_argument(
        "--checkpoints",
        type=str,
        default="100,300,1000",
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
        default="sequential",
    )

    parser.add_argument(
        "--anchor-weight",
        type=float,
        default=0.01,
    )

    return parser.parse_args()


def parse_checkpoints(
    raw: str,
) -> tuple[int, ...]:
    values = tuple(
        int(item.strip())
        for item in raw.split(",")
        if item.strip()
    )

    if len(values) < 2:
        raise ValueError(
            "At least two checkpoints "
            "are required."
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


def strategy_sum_values(
    node,
) -> tuple[float, ...]:
    value = getattr(
        node,
        "strategy_sum",
        None,
    )

    if value is None:
        return ()

    if isinstance(
        value,
        dict,
    ):
        return tuple(
            float(
                value.get(
                    action,
                    0.0,
                )
            )
            for action in node.actions
        )

    return tuple(
        float(item)
        for item in value
    )


def strategy_weight(
    node,
) -> float:
    return sum(
        strategy_sum_values(
            node
        )
    )


def make_snapshot(
    trainer: CFRTrainer,
    *,
    iteration: int,
) -> Snapshot:
    strategies = {}
    weights = {}
    phases = {}

    for (
        state,
        node,
    ) in trainer.node_store.nodes.items():
        if len(
            node.actions
        ) <= 1:
            continue

        average = (
            node.average_strategy()
        )

        strategies[state] = {
            action: float(
                average.get(
                    action,
                    0.0,
                )
            )
            for action in node.actions
        }

        weights[state] = (
            strategy_weight(
                node
            )
        )

        phases[state] = (
            state.phase
        )

    return Snapshot(
        iteration=iteration,
        strategies=strategies,
        weights=weights,
        phases=phases,
    )


def strategy_l1(
    first: dict,
    second: dict,
) -> float | None:
    if set(first) != set(second):
        return None

    return sum(
        abs(
            first[action]
            - second[action]
        )
        for action in first
    )


def phase_name(
    phase,
) -> str:
    value = getattr(
        phase,
        "value",
        None,
    )

    if value is not None:
        return str(value)

    return str(phase)


def collect_distances(
    *,
    first: Snapshot,
    second: Snapshot,
    cohort: set,
) -> dict[
    str,
    list[float],
]:
    result: dict[
        str,
        list[float],
    ] = {
        "overall": [],
    }

    for state in cohort:
        first_strategy = (
            first.strategies.get(
                state
            )
        )

        second_strategy = (
            second.strategies.get(
                state
            )
        )

        if (
            first_strategy is None
            or second_strategy is None
        ):
            continue

        distance = (
            strategy_l1(
                first_strategy,
                second_strategy,
            )
        )

        if distance is None:
            continue

        result[
            "overall"
        ].append(
            distance
        )

        phase = phase_name(
            second.phases.get(
                state,
                first.phases.get(
                    state
                ),
            )
        )

        result.setdefault(
            phase,
            [],
        ).append(
            distance
        )

    return result


def print_distance_summary(
    *,
    label: str,
    distances: list[
        float
    ],
) -> None:
    if not distances:
        print(
            f"  {label}: no nodes"
        )
        return

    count = len(
        distances
    )

    ge_025 = sum(
        value >= 0.25
        for value in distances
    )

    ge_050 = sum(
        value >= 0.50
        for value in distances
    )

    ge_100 = sum(
        value >= 1.00
        for value in distances
    )

    print(
        f"  {label}:"
    )

    print(
        f"    nodes: "
        f"{count:,}"
    )

    print(
        f"    mean L1: "
        f"{mean(distances):.6f}"
    )

    print(
        f"    median L1: "
        f"{median(distances):.6f}"
    )

    print(
        f"    max L1: "
        f"{max(distances):.6f}"
    )

    print(
        f"    L1 >= 0.25: "
        f"{ge_025:,} "
        f"({ge_025 / count:.2%})"
    )

    print(
        f"    L1 >= 0.50: "
        f"{ge_050:,} "
        f"({ge_050 / count:.2%})"
    )

    print(
        f"    L1 >= 1.00: "
        f"{ge_100:,} "
        f"({ge_100 / count:.2%})"
    )


def main() -> None:
    args = parse_args()

    if args.stack <= 0:
        raise ValueError(
            "Stack must be positive."
        )

    if args.anchor_weight < 0:
        raise ValueError(
            "Anchor weight cannot "
            "be negative."
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

    game_factory = make_game_factory(
        stack=args.stack,
        seed=args.seed,
        seed_mode=args.seed_mode,
    )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
        abstraction=args.abstraction,
        traversal_mode=(
            args.traversal_mode
        ),
        draw_action_mode="auto",
        random_seed=args.seed,
    )

    snapshots: list[
        Snapshot
    ] = []

    completed = 0

    print(
        "Anchored average-strategy "
        "convergence diagnostic"
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
        f"  seed mode: "
        f"{args.seed_mode}"
    )

    print(
        f"  anchor weight: "
        f"{args.anchor_weight:g}"
    )

    for checkpoint in checkpoints:
        additional = (
            checkpoint
            - completed
        )

        print()
        print(
            f"Training to "
            f"{checkpoint:,}..."
        )

        trainer.train(
            game_factory,
            iterations=additional,
        )

        snapshot = (
            make_snapshot(
                trainer,
                iteration=checkpoint,
            )
        )

        snapshots.append(
            snapshot
        )

        print(
            f"  strategic nodes: "
            f"{len(snapshot.strategies):,}"
        )

        completed = checkpoint

    anchor = snapshots[0]

    cohort = {
        state
        for state, weight
        in anchor.weights.items()
        if (
            weight
            >= args.anchor_weight
        )
    }

    print()
    print(
        "=" * 72
    )

    print(
        "ANCHOR COHORT"
    )

    print(
        f"  anchor iteration: "
        f"{anchor.iteration:,}"
    )

    print(
        f"  anchor strategic nodes: "
        f"{len(anchor.strategies):,}"
    )

    print(
        f"  active anchor cohort: "
        f"{len(cohort):,}"
    )

    phase_counts = {}

    for state in cohort:
        phase = phase_name(
            anchor.phases[
                state
            ]
        )

        phase_counts[
            phase
        ] = (
            phase_counts.get(
                phase,
                0,
            )
            + 1
        )

    for (
        phase,
        count,
    ) in sorted(
        phase_counts.items()
    ):
        print(
            f"    {phase}: "
            f"{count:,}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "FIXED-COHORT "
        "CONSECUTIVE COMPARISONS"
    )

    for index in range(
        1,
        len(snapshots),
    ):
        first = (
            snapshots[
                index - 1
            ]
        )

        second = (
            snapshots[
                index
            ]
        )

        print()
        print(
            f"{first.iteration:,} "
            f"-> "
            f"{second.iteration:,}"
        )

        result = (
            collect_distances(
                first=first,
                second=second,
                cohort=cohort,
            )
        )

        print_distance_summary(
            label="OVERALL",
            distances=result[
                "overall"
            ],
        )

        for phase in (
            "predraw_betting",
            "draw",
            "postdraw_betting",
        ):
            print_distance_summary(
                label=phase,
                distances=result.get(
                    phase,
                    [],
                ),
            )

    print()
    print(
        "=" * 72
    )

    print(
        "ANCHOR VS FINAL"
    )

    result = collect_distances(
        first=snapshots[0],
        second=snapshots[-1],
        cohort=cohort,
    )

    print_distance_summary(
        label="OVERALL",
        distances=result[
            "overall"
        ],
    )

    for phase in (
        "predraw_betting",
        "draw",
        "postdraw_betting",
    ):
        print_distance_summary(
            label=phase,
            distances=result.get(
                phase,
                [],
            ),
        )


if __name__ == "__main__":
    main()