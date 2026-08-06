import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import (
    mean,
    median,
)
import sys
from time import perf_counter
from typing import Literal


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from solver.cfr_trainer import (  # noqa: E402
    CFRTrainer,
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.information_state import (  # noqa: E402
    AbstractionMode,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


SeedMode = Literal[
    "fixed",
    "sequential",
]


@dataclass(frozen=True)
class PhaseStatistics:
    phase: str

    node_count: int
    total_visits: int

    average_visits: float
    median_visits: float
    maximum_visits: int

    single_visit_nodes: int
    single_visit_ratio: float

    ten_plus_visit_nodes: int
    ten_plus_visit_ratio: float

    hundred_plus_visit_nodes: int
    hundred_plus_visit_ratio: float

    total_strategy_updates: int
    average_strategy_updates: float

    total_regret_updates: int
    average_regret_updates: float

    near_uniform_nodes: int
    near_uniform_ratio: float

    one_action_nodes: int
    one_action_ratio: float

    action_count_distribution: tuple[
        tuple[
            int,
            int,
        ],
        ...,
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze CFR reuse and strategy "
            "development separately for each "
            "game phase."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=10000,
        help=(
            "Number of CFR training "
            "iterations."
        ),
    )

    parser.add_argument(
        "--abstraction",
        choices=(
            "exact",
            "bucket",
        ),
        default="bucket",
        help=(
            "Private-hand abstraction used "
            "during training."
        ),
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
        help=(
            "Starting stack in chips."
        ),
    )

    parser.add_argument(
        "--max-draw",
        type=int,
        choices=range(
            0,
            6,
        ),
        default=1,
        help=(
            "Maximum number of cards that "
            "may be discarded."
        ),
    )

    parser.add_argument(
        "--traversal-mode",
        choices=(
            "full",
            "external_sampling",
        ),
        default="external_sampling",
        help=(
            "CFR traversal algorithm."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help=(
            "Base deck and trainer seed."
        ),
    )

    parser.add_argument(
        "--seed-mode",
        choices=(
            "fixed",
            "sequential",
        ),
        default="sequential",
        help=(
            "fixed repeats one complete deal; "
            "sequential changes the deck seed "
            "for each iteration."
        ),
    )

    parser.add_argument(
        "--uniform-tolerance",
        type=float,
        default=1e-9,
        help=(
            "Maximum probability difference "
            "from a uniform strategy for a "
            "node to be counted as uniform."
        ),
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.iterations <= 0:
        raise ValueError(
            "Iterations must be positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Starting stack must be positive."
        )

    if args.uniform_tolerance < 0:
        raise ValueError(
            "Uniform tolerance cannot be "
            "negative."
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


def phase_label(
    phase,
) -> str:
    value = getattr(
        phase,
        "value",
        None,
    )

    if value is not None:
        return str(
            value
        )

    return str(
        phase
    )


def is_near_uniform(
    probabilities: tuple[
        float,
        ...,
    ],
    *,
    tolerance: float,
) -> bool:
    if not probabilities:
        return False

    uniform_probability = (
        1.0
        / len(
            probabilities
        )
    )

    return all(
        abs(
            probability
            - uniform_probability
        )
        <= tolerance
        for probability in probabilities
    )


def collect_phase_statistics(
    *,
    trainer: CFRTrainer,
    uniform_tolerance: float,
) -> tuple[
    PhaseStatistics,
    ...,
]:
    nodes_by_phase: dict[
        str,
        list,
    ] = {}

    for (
        information_state,
        node,
    ) in trainer.node_store.nodes.items():
        phase = phase_label(
            information_state.phase
        )

        nodes_by_phase.setdefault(
            phase,
            [],
        ).append(
            node
        )

    statistics: list[
        PhaseStatistics
    ] = []

    for phase in sorted(
        nodes_by_phase
    ):
        nodes = tuple(
            nodes_by_phase[
                phase
            ]
        )

        node_count = len(
            nodes
        )

        visit_counts = tuple(
            node.visit_count
            for node in nodes
        )

        strategy_update_counts = tuple(
            node.strategy_update_count
            for node in nodes
        )

        regret_update_counts = tuple(
            node.regret_update_count
            for node in nodes
        )

        action_counts = tuple(
            len(
                node.actions
            )
            for node in nodes
        )

        single_visit_nodes = sum(
            count == 1
            for count in visit_counts
        )

        ten_plus_visit_nodes = sum(
            count >= 10
            for count in visit_counts
        )

        hundred_plus_visit_nodes = sum(
            count >= 100
            for count in visit_counts
        )

        one_action_nodes = sum(
            count == 1
            for count in action_counts
        )

        near_uniform_nodes = sum(
            is_near_uniform(
                tuple(
                    node.average_strategy()
                    .values()
                ),
                tolerance=(
                    uniform_tolerance
                ),
            )
            for node in nodes
        )

        action_distribution = tuple(
            sorted(
                Counter(
                    action_counts
                ).items()
            )
        )

        statistics.append(
            PhaseStatistics(
                phase=phase,
                node_count=node_count,
                total_visits=sum(
                    visit_counts
                ),
                average_visits=mean(
                    visit_counts
                ),
                median_visits=median(
                    visit_counts
                ),
                maximum_visits=max(
                    visit_counts
                ),
                single_visit_nodes=(
                    single_visit_nodes
                ),
                single_visit_ratio=(
                    single_visit_nodes
                    / node_count
                ),
                ten_plus_visit_nodes=(
                    ten_plus_visit_nodes
                ),
                ten_plus_visit_ratio=(
                    ten_plus_visit_nodes
                    / node_count
                ),
                hundred_plus_visit_nodes=(
                    hundred_plus_visit_nodes
                ),
                hundred_plus_visit_ratio=(
                    hundred_plus_visit_nodes
                    / node_count
                ),
                total_strategy_updates=sum(
                    strategy_update_counts
                ),
                average_strategy_updates=mean(
                    strategy_update_counts
                ),
                total_regret_updates=sum(
                    regret_update_counts
                ),
                average_regret_updates=mean(
                    regret_update_counts
                ),
                near_uniform_nodes=(
                    near_uniform_nodes
                ),
                near_uniform_ratio=(
                    near_uniform_nodes
                    / node_count
                ),
                one_action_nodes=(
                    one_action_nodes
                ),
                one_action_ratio=(
                    one_action_nodes
                    / node_count
                ),
                action_count_distribution=(
                    action_distribution
                ),
            )
        )

    return tuple(
        statistics
    )


def print_action_distribution(
    distribution: tuple[
        tuple[
            int,
            int,
        ],
        ...,
    ],
    *,
    node_count: int,
) -> None:
    print(
        "  action count distribution:"
    )

    for (
        action_count,
        count,
    ) in distribution:
        ratio = (
            count
            / node_count
        )

        print(
            f"    {action_count:>2} actions: "
            f"{count:>8,} "
            f"({ratio:>7.2%})"
        )


def print_phase_statistics(
    statistics: PhaseStatistics,
) -> None:
    print()
    print(
        statistics.phase.upper()
    )

    print(
        f"  nodes: "
        f"{statistics.node_count:,}"
    )

    print(
        f"  total visits: "
        f"{statistics.total_visits:,}"
    )

    print(
        f"  average visits/node: "
        f"{statistics.average_visits:.3f}"
    )

    print(
        f"  median visits/node: "
        f"{statistics.median_visits:.3f}"
    )

    print(
        f"  maximum visits: "
        f"{statistics.maximum_visits:,}"
    )

    print(
        f"  visit count = 1: "
        f"{statistics.single_visit_nodes:,} "
        f"({statistics.single_visit_ratio:.2%})"
    )

    print(
        f"  visit count >= 10: "
        f"{statistics.ten_plus_visit_nodes:,} "
        f"({statistics.ten_plus_visit_ratio:.2%})"
    )

    print(
        f"  visit count >= 100: "
        f"{statistics.hundred_plus_visit_nodes:,} "
        f"({statistics.hundred_plus_visit_ratio:.2%})"
    )

    print(
        f"  strategy updates: "
        f"{statistics.total_strategy_updates:,}"
    )

    print(
        f"  average strategy updates/node: "
        f"{statistics.average_strategy_updates:.3f}"
    )

    print(
        f"  regret updates: "
        f"{statistics.total_regret_updates:,}"
    )

    print(
        f"  average regret updates/node: "
        f"{statistics.average_regret_updates:.3f}"
    )

    print(
        f"  near-uniform nodes: "
        f"{statistics.near_uniform_nodes:,} "
        f"({statistics.near_uniform_ratio:.2%})"
    )

    print(
        f"  one-action nodes: "
        f"{statistics.one_action_nodes:,} "
        f"({statistics.one_action_ratio:.2%})"
    )

    print_action_distribution(
        statistics.action_count_distribution,
        node_count=(
            statistics.node_count
        ),
    )


def print_overall_summary(
    statistics: tuple[
        PhaseStatistics,
        ...,
    ],
) -> None:
    total_nodes = sum(
        phase.node_count
        for phase in statistics
    )

    total_visits = sum(
        phase.total_visits
        for phase in statistics
    )

    total_near_uniform = sum(
        phase.near_uniform_nodes
        for phase in statistics
    )

    total_single_visit = sum(
        phase.single_visit_nodes
        for phase in statistics
    )

    print()
    print(
        "OVERALL"
    )

    print(
        f"  phases: "
        f"{len(statistics)}"
    )

    print(
        f"  nodes: "
        f"{total_nodes:,}"
    )

    print(
        f"  total visits: "
        f"{total_visits:,}"
    )

    print(
        f"  average visits/node: "
        f"{total_visits / total_nodes:.3f}"
    )

    print(
        f"  single-visit nodes: "
        f"{total_single_visit:,} "
        f"({total_single_visit / total_nodes:.2%})"
    )

    print(
        f"  near-uniform nodes: "
        f"{total_near_uniform:,} "
        f"({total_near_uniform / total_nodes:.2%})"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
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
        raise_sizes=(),
        abstraction=abstraction,
        traversal_mode=(
            args.traversal_mode
        ),
        draw_action_mode="auto",
        random_seed=args.seed,
    )

    print(
        "Phase-aware CFR diagnostic"
    )

    print(
        f"  iterations: "
        f"{args.iterations:,}"
    )

    print(
        f"  abstraction: "
        f"{args.abstraction}"
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
        f"  traversal: "
        f"{args.traversal_mode}"
    )

    print(
        f"  draw actions: "
        f"{trainer.resolved_draw_action_mode}"
    )

    print(
        f"  seed: "
        f"{args.seed}"
    )

    print(
        f"  seed mode: "
        f"{args.seed_mode}"
    )

    print(
        f"  uniform tolerance: "
        f"{args.uniform_tolerance:g}"
    )

    started_at = perf_counter()

    trainer.train(
        game_factory,
        iterations=args.iterations,
    )

    elapsed_seconds = (
        perf_counter()
        - started_at
    )

    print(
        f"  elapsed: "
        f"{elapsed_seconds:.3f}s"
    )

    statistics = (
        collect_phase_statistics(
            trainer=trainer,
            uniform_tolerance=(
                args.uniform_tolerance
            ),
        )
    )

    if not statistics:
        raise RuntimeError(
            "Training produced no phase "
            "statistics."
        )

    for phase_statistics in (
        statistics
    ):
        print_phase_statistics(
            phase_statistics
        )

    print_overall_summary(
        statistics
    )


if __name__ == "__main__":
    main()