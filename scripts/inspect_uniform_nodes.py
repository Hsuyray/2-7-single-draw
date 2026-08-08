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
            "Inspect highly visited CFR nodes "
            "whose average strategies remain "
            "near uniform."
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
        "--min-strategy-updates",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--uniform-tolerance",
        type=float,
        default=1e-9,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
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

    if args.min_visits < 0:
        raise ValueError(
            "Minimum visits cannot be "
            "negative."
        )

    if args.min_strategy_updates < 0:
        raise ValueError(
            "Minimum strategy updates cannot "
            "be negative."
        )

    if args.uniform_tolerance < 0:
        raise ValueError(
            "Uniform tolerance cannot be "
            "negative."
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
) -> tuple[
    float,
    ...,
]:
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


def near_uniform(
    probabilities: tuple[
        float,
        ...,
    ],
    *,
    tolerance: float,
) -> bool:
    if len(probabilities) <= 1:
        return False

    target = (
        1.0
        / len(
            probabilities
        )
    )

    return all(
        abs(
            probability
            - target
        )
        <= tolerance
        for probability in probabilities
    )


def get_node_regrets(
    node,
) -> tuple[
    float,
    ...,
]:
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


def get_node_strategy_sum(
    node,
) -> tuple[
    float,
    ...,
]:
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


def format_values(
    values: tuple[
        float,
        ...,
    ],
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


def format_strategy(
    node,
) -> tuple[
    tuple[
        object,
        float,
    ],
    ...,
]:
    average = (
        node.average_strategy()
    )

    return tuple(
        (
            action,
            float(
                average.get(
                    action,
                    0.0,
                )
            ),
        )
        for action in node.actions
    )


def collect_candidates(
    *,
    trainer: CFRTrainer,
    min_visits: int,
    min_strategy_updates: int,
    uniform_tolerance: float,
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
            < min_strategy_updates
        ):
            continue

        strategy = (
            format_strategy(
                node
            )
        )

        probabilities = tuple(
            probability
            for (
                _action,
                probability,
            ) in strategy
        )

        if not near_uniform(
            probabilities,
            tolerance=(
                uniform_tolerance
            ),
        ):
            continue

        candidates.append(
            (
                information_state,
                node,
                strategy,
            )
        )

    candidates.sort(
        key=lambda item: (
            item[1].visit_count,
            item[1].strategy_update_count,
        ),
        reverse=True,
    )

    return candidates


def print_node(
    *,
    rank: int,
    information_state,
    node,
    strategy,
) -> None:
    print()
    print(
        "=" * 80
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
        f"  information state: "
        f"{information_state}"
    )

    print()
    print(
        "  actions:"
    )

    for (
        index,
        action,
    ) in enumerate(
        node.actions
    ):
        print(
            f"    [{index}] "
            f"{action}"
        )

    regrets = (
        get_node_regrets(
            node
        )
    )

    strategy_sum = (
        get_node_strategy_sum(
            node
        )
    )

    print()
    print(
        "  regrets:"
    )
    print(
        "    "
        + format_values(
            regrets
        )
    )

    print(
        "  strategy sum:"
    )
    print(
        "    "
        + format_values(
            strategy_sum
        )
    )

    print()
    print(
        "  average strategy:"
    )

    for (
        action,
        probability,
    ) in strategy:
        print(
            f"    "
            f"{probability:>10.6%}  "
            f"{action}"
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
        "Highly visited near-uniform "
        "node diagnostic"
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
        f"  min strategy updates: "
        f"{args.min_strategy_updates:,}"
    )

    print(
        f"  uniform tolerance: "
        f"{args.uniform_tolerance:g}"
    )

    print(
        "Training..."
    )

    trainer.train(
        game_factory,
        iterations=args.iterations,
    )

    candidates = (
        collect_candidates(
            trainer=trainer,
            min_visits=(
                args.min_visits
            ),
            min_strategy_updates=(
                args.min_strategy_updates
            ),
            uniform_tolerance=(
                args.uniform_tolerance
            ),
        )
    )

    print()
    print(
        "Diagnostic summary"
    )

    print(
        f"  total CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  matching nodes: "
        f"{len(candidates):,}"
    )

    if not candidates:
        print(
            "  No highly visited "
            "near-uniform strategic nodes "
            "matched the filters."
        )

        return

    displayed = (
        candidates[
            : args.limit
        ]
    )

    print(
        f"  displaying: "
        f"{len(displayed):,}"
    )

    for (
        rank,
        (
            information_state,
            node,
            strategy,
        ),
    ) in enumerate(
        displayed,
        start=1,
    ):
        print_node(
            rank=rank,
            information_state=(
                information_state
            ),
            node=node,
            strategy=strategy,
        )


if __name__ == "__main__":
    main()