import argparse
from pathlib import Path
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
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


SeedMode = Literal[
    "fixed",
    "sequential",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare CFR current regret-matched "
            "strategy against cumulative average "
            "strategy."
        )
    )

    parser.add_argument(
        "--iterations",
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
        "--min-visits",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--min-updates",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--sort-by",
        choices=(
            "visits",
            "l1",
            "strategy-weight",
        ),
        default="l1",
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
            "Stack must be positive."
        )

    if args.min_visits < 0:
        raise ValueError(
            "Minimum visits cannot be negative."
        )

    if args.min_updates < 0:
        raise ValueError(
            "Minimum updates cannot be negative."
        )

    if args.limit <= 0:
        raise ValueError(
            "Limit must be positive."
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


def node_regrets(
    node,
) -> tuple[float, ...]:
    possible_names = (
        "regret_sum",
        "regrets",
        "cumulative_regret",
        "cumulative_regrets",
    )

    for name in possible_names:
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


def node_strategy_sum(
    node,
) -> tuple[float, ...]:
    possible_names = (
        "strategy_sum",
        "strategy_sums",
        "cumulative_strategy",
        "cumulative_strategies",
    )

    for name in possible_names:
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


def regret_matching_strategy(
    regrets: tuple[float, ...],
) -> tuple[float, ...]:
    if not regrets:
        return ()

    positive_regrets = tuple(
        max(
            regret,
            0.0,
        )
        for regret in regrets
    )

    total_positive = sum(
        positive_regrets
    )

    if total_positive > 0:
        return tuple(
            regret
            / total_positive
            for regret in positive_regrets
        )

    uniform_probability = (
        1.0
        / len(regrets)
    )

    return tuple(
        uniform_probability
        for _ in regrets
    )


def average_strategy_values(
    node,
) -> tuple[float, ...]:
    strategy = (
        node.average_strategy()
    )

    return tuple(
        float(
            strategy.get(
                action,
                0.0,
            )
        )
        for action in node.actions
    )


def l1_distance(
    first: tuple[float, ...],
    second: tuple[float, ...],
) -> float:
    if len(first) != len(second):
        raise ValueError(
            "Strategy vectors must have "
            "equal length."
        )

    return sum(
        abs(
            left
            - right
        )
        for left, right in zip(
            first,
            second,
            strict=True,
        )
    )


def strategy_weight(
    node,
) -> float:
    values = node_strategy_sum(
        node
    )

    return sum(
        values
    )


def collect_candidates(
    *,
    trainer: CFRTrainer,
    min_visits: int,
    min_updates: int,
    sort_by: str,
):
    candidates = []

    for (
        information_state,
        node,
    ) in trainer.node_store.nodes.items():
        if len(
            node.actions
        ) <= 1:
            continue

        if (
            node.visit_count
            < min_visits
        ):
            continue

        if (
            node.strategy_update_count
            < min_updates
        ):
            continue

        regrets = node_regrets(
            node
        )

        if not regrets:
            continue

        current_strategy = (
            regret_matching_strategy(
                regrets
            )
        )

        average_strategy = (
            average_strategy_values(
                node
            )
        )

        distance = l1_distance(
            current_strategy,
            average_strategy,
        )

        weight = strategy_weight(
            node
        )

        candidates.append(
            {
                "information_state": (
                    information_state
                ),
                "node": node,
                "regrets": regrets,
                "current": current_strategy,
                "average": average_strategy,
                "strategy_sum": (
                    node_strategy_sum(
                        node
                    )
                ),
                "strategy_weight": weight,
                "l1": distance,
            }
        )

    if sort_by == "visits":
        candidates.sort(
            key=lambda item: (
                item["node"].visit_count
            ),
            reverse=True,
        )

    elif sort_by == "l1":
        candidates.sort(
            key=lambda item: (
                item["l1"]
            ),
            reverse=True,
        )

    elif sort_by == "strategy-weight":
        candidates.sort(
            key=lambda item: (
                item["strategy_weight"]
            ),
        )

    return candidates


def format_values(
    values: tuple[float, ...],
) -> str:
    if not values:
        return "<not found>"

    return (
        "["
        + ", ".join(
            f"{value:.6f}"
            for value in values
        )
        + "]"
    )


def print_node(
    *,
    rank: int,
    candidate,
) -> None:
    information_state = (
        candidate[
            "information_state"
        ]
    )

    node = candidate[
        "node"
    ]

    regrets = candidate[
        "regrets"
    ]

    strategy_sum = candidate[
        "strategy_sum"
    ]

    current = candidate[
        "current"
    ]

    average = candidate[
        "average"
    ]

    print()
    print(
        "=" * 88
    )

    print(
        f"NODE #{rank}"
    )

    print(
        f"  phase: "
        f"{phase_label(information_state.phase)}"
    )

    print(
        f"  visits: "
        f"{node.visit_count:,}"
    )

    print(
        f"  strategy updates: "
        f"{node.strategy_update_count:,}"
    )

    print(
        f"  regret updates: "
        f"{node.regret_update_count:,}"
    )

    print(
        f"  action count: "
        f"{len(node.actions)}"
    )

    print(
        f"  strategy weight: "
        f"{candidate['strategy_weight']:.9f}"
    )

    print(
        f"  current-average L1: "
        f"{candidate['l1']:.6f}"
    )

    print(
        f"  information state: "
        f"{information_state}"
    )

    print()
    print(
        "  raw regrets:"
    )

    print(
        "    "
        + format_values(
            regrets
        )
    )

    print(
        "  cumulative strategy sum:"
    )

    print(
        "    "
        + format_values(
            strategy_sum
        )
    )

    print()
    print(
        "  strategy comparison:"
    )

    for (
        index,
        action,
    ) in enumerate(
        node.actions
    ):
        current_probability = (
            current[
                index
            ]
        )

        average_probability = (
            average[
                index
            ]
        )

        difference = (
            current_probability
            - average_probability
        )

        print(
            f"    [{index}] "
            f"current="
            f"{current_probability:>9.4%}  "
            f"average="
            f"{average_probability:>9.4%}  "
            f"diff="
            f"{difference:>+9.4%}  "
            f"{action}"
        )


def print_summary(
    candidates,
) -> None:
    if not candidates:
        print(
            "  No nodes matched the filters."
        )
        return

    zero_weight = sum(
        candidate[
            "strategy_weight"
        ]
        <= 1e-12
        for candidate in candidates
    )

    large_divergence = sum(
        candidate[
            "l1"
        ]
        >= 0.5
        for candidate in candidates
    )

    extreme_divergence = sum(
        candidate[
            "l1"
        ]
        >= 1.0
        for candidate in candidates
    )

    print(
        f"  matching nodes: "
        f"{len(candidates):,}"
    )

    print(
        f"  zero strategy weight: "
        f"{zero_weight:,} "
        f"("
        f"{zero_weight / len(candidates):.2%}"
        f")"
    )

    print(
        f"  L1 >= 0.5: "
        f"{large_divergence:,} "
        f"("
        f"{large_divergence / len(candidates):.2%}"
        f")"
    )

    print(
        f"  L1 >= 1.0: "
        f"{extreme_divergence:,} "
        f"("
        f"{extreme_divergence / len(candidates):.2%}"
        f")"
    )

    # Weighted view: down-weights near-zero-reach
    # off-path nodes so we can see whether the
    # branches that actually carry strategy
    # weight are converging.
    nonzero_candidates = [
        candidate
        for candidate in candidates
        if candidate["strategy_weight"] > 1e-12
    ]

    total_weight = sum(
        candidate["strategy_weight"]
        for candidate in nonzero_candidates
    )

    print(
        f"  nonzero-weight nodes: "
        f"{len(nonzero_candidates):,}"
    )

    if total_weight > 0:
        weighted_l1 = sum(
            candidate["l1"]
            * candidate["strategy_weight"]
            for candidate in nonzero_candidates
        ) / total_weight

        print(
            f"  weight-weighted avg L1: "
            f"{weighted_l1:.6f}"
        )

        top_weight_candidates = sorted(
            nonzero_candidates,
            key=lambda item: item["strategy_weight"],
            reverse=True,
        )[: max(1, len(nonzero_candidates) // 4)]

        top_weight_avg_l1 = sum(
            candidate["l1"]
            for candidate in top_weight_candidates
        ) / len(top_weight_candidates)

        print(
            f"  top-quartile-by-weight "
            f"avg L1 ({len(top_weight_candidates)} nodes): "
            f"{top_weight_avg_l1:.6f}"
        )
    else:
        print(
            "  weight-weighted avg L1: "
            "n/a (no nonzero-weight nodes)"
        )


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
        "Current vs average strategy diagnostic"
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
        f"  min visits: "
        f"{args.min_visits:,}"
    )

    print(
        f"  min updates: "
        f"{args.min_updates:,}"
    )

    print(
        f"  sort by: "
        f"{args.sort_by}"
    )

    print(
        "Training..."
    )

    trainer.train(
        game_factory,
        iterations=args.iterations,
    )

    candidates = collect_candidates(
        trainer=trainer,
        min_visits=(
            args.min_visits
        ),
        min_updates=(
            args.min_updates
        ),
        sort_by=(
            args.sort_by
        ),
    )

    print()
    print(
        "Diagnostic summary"
    )

    print(
        f"  total CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print_summary(
        candidates
    )

    displayed = candidates[
        : args.limit
    ]

    print(
        f"  displaying: "
        f"{len(displayed):,}"
    )

    for (
        rank,
        candidate,
    ) in enumerate(
        displayed,
        start=1,
    ):
        print_node(
            rank=rank,
            candidate=candidate,
        )


if __name__ == "__main__":
    main()