import argparse
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


ComparisonMode = Literal[
    "exact",
    "bucket",
    "both",
]


@dataclass(frozen=True)
class ReuseStatistics:
    abstraction: AbstractionMode
    iterations: int
    elapsed_seconds: float

    node_count: int
    total_visits: int

    average_visits: float
    median_visits: float
    maximum_visits: int

    single_visit_nodes: int
    ten_plus_visit_nodes: int
    hundred_plus_visit_nodes: int

    single_visit_ratio: float
    ten_plus_visit_ratio: float
    hundred_plus_visit_ratio: float

    total_strategy_updates: int
    total_regret_updates: int

    near_uniform_nodes: int
    near_uniform_ratio: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare CFR information-state "
            "reuse for exact and bucket "
            "abstractions."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
        help=(
            "Number of CFR iterations for "
            "each abstraction."
        ),
    )

    parser.add_argument(
        "--abstraction",
        choices=(
            "exact",
            "bucket",
            "both",
        ),
        default="both",
        help=(
            "Run exact, bucket, or both "
            "abstractions."
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
            "fixed repeats one deal; "
            "sequential uses a new deck seed "
            "for every iteration."
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


def make_game_factory(
    *,
    stack: float,
    seed: int,
    seed_mode: str,
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


def is_near_uniform(
    probabilities: tuple[
        float,
        ...,
    ],
    *,
    tolerance: float = 1e-9,
) -> bool:
    if not probabilities:
        return False

    uniform_probability = (
        1.0 / len(
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


def collect_statistics(
    *,
    trainer: CFRTrainer,
    abstraction: AbstractionMode,
    iterations: int,
    elapsed_seconds: float,
) -> ReuseStatistics:
    nodes = tuple(
        trainer.node_store.nodes.values()
    )

    if not nodes:
        raise RuntimeError(
            "Training produced no CFR nodes."
        )

    visit_counts = tuple(
        node.visit_count
        for node in nodes
    )

    node_count = len(
        nodes
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

    near_uniform_nodes = sum(
        is_near_uniform(
            tuple(
                node.average_strategy().values()
            )
        )
        for node in nodes
    )

    return ReuseStatistics(
        abstraction=abstraction,
        iterations=iterations,
        elapsed_seconds=elapsed_seconds,
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
        ten_plus_visit_nodes=(
            ten_plus_visit_nodes
        ),
        hundred_plus_visit_nodes=(
            hundred_plus_visit_nodes
        ),
        single_visit_ratio=(
            single_visit_nodes
            / node_count
        ),
        ten_plus_visit_ratio=(
            ten_plus_visit_nodes
            / node_count
        ),
        hundred_plus_visit_ratio=(
            hundred_plus_visit_nodes
            / node_count
        ),
        total_strategy_updates=sum(
            node.strategy_update_count
            for node in nodes
        ),
        total_regret_updates=sum(
            node.regret_update_count
            for node in nodes
        ),
        near_uniform_nodes=(
            near_uniform_nodes
        ),
        near_uniform_ratio=(
            near_uniform_nodes
            / node_count
        ),
    )


def train_and_measure(
    *,
    abstraction: AbstractionMode,
    args: argparse.Namespace,
) -> ReuseStatistics:
    game_factory = make_game_factory(
        stack=args.stack,
        seed=args.seed,
        seed_mode=args.seed_mode,
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
        f"Training {abstraction}..."
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

    return collect_statistics(
        trainer=trainer,
        abstraction=abstraction,
        iterations=args.iterations,
        elapsed_seconds=elapsed_seconds,
    )


def print_statistics(
    statistics: ReuseStatistics,
) -> None:
    print()
    print(
        f"{statistics.abstraction.upper()} "
        "reuse statistics"
    )

    print(
        f"  iterations: "
        f"{statistics.iterations:,}"
    )

    print(
        f"  elapsed: "
        f"{statistics.elapsed_seconds:.3f}s"
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
        f"  regret updates: "
        f"{statistics.total_regret_updates:,}"
    )

    print(
        f"  near-uniform nodes: "
        f"{statistics.near_uniform_nodes:,} "
        f"({statistics.near_uniform_ratio:.2%})"
    )


def print_comparison(
    *,
    exact: ReuseStatistics,
    bucket: ReuseStatistics,
) -> None:
    node_reduction = (
        exact.node_count
        - bucket.node_count
    )

    node_reduction_ratio = (
        node_reduction
        / exact.node_count
        if exact.node_count
        else 0.0
    )

    average_visit_multiplier = (
        bucket.average_visits
        / exact.average_visits
        if exact.average_visits
        else 0.0
    )

    print()
    print(
        "EXACT vs BUCKET"
    )

    print(
        f"  exact nodes: "
        f"{exact.node_count:,}"
    )

    print(
        f"  bucket nodes: "
        f"{bucket.node_count:,}"
    )

    print(
        f"  node reduction: "
        f"{node_reduction:,} "
        f"({node_reduction_ratio:.2%})"
    )

    print(
        f"  exact avg visits/node: "
        f"{exact.average_visits:.3f}"
    )

    print(
        f"  bucket avg visits/node: "
        f"{bucket.average_visits:.3f}"
    )

    print(
        f"  bucket reuse multiplier: "
        f"{average_visit_multiplier:.3f}x"
    )

    print(
        f"  exact single-visit ratio: "
        f"{exact.single_visit_ratio:.2%}"
    )

    print(
        f"  bucket single-visit ratio: "
        f"{bucket.single_visit_ratio:.2%}"
    )

    print(
        f"  exact near-uniform ratio: "
        f"{exact.near_uniform_ratio:.2%}"
    )

    print(
        f"  bucket near-uniform ratio: "
        f"{bucket.near_uniform_ratio:.2%}"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    print(
        "Training reuse diagnostic"
    )

    print(
        f"  iterations: "
        f"{args.iterations:,}"
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
        f"  seed mode: "
        f"{args.seed_mode}"
    )

    exact_statistics = None
    bucket_statistics = None

    if args.abstraction in {
        "exact",
        "both",
    }:
        exact_statistics = (
            train_and_measure(
                abstraction="exact",
                args=args,
            )
        )

        print_statistics(
            exact_statistics
        )

    if args.abstraction in {
        "bucket",
        "both",
    }:
        bucket_statistics = (
            train_and_measure(
                abstraction="bucket",
                args=args,
            )
        )

        print_statistics(
            bucket_statistics
        )

    if (
        exact_statistics is not None
        and bucket_statistics is not None
    ):
        print_comparison(
            exact=exact_statistics,
            bucket=bucket_statistics,
        )


if __name__ == "__main__":
    main()