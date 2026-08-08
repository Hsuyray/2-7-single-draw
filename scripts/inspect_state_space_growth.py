import argparse
from collections import Counter
from dataclasses import (
    fields,
    is_dataclass,
)
from enum import Enum
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
            "Inspect CFR information-state "
            "growth and separate public-tree "
            "growth from private-hand growth."
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
        default="sequential",
    )

    parser.add_argument(
        "--float-decimals",
        type=int,
        default=6,
        help=(
            "Decimal precision used when "
            "building normalized public-node "
            "signatures."
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

    if not checkpoints:
        raise ValueError(
            "At least one checkpoint "
            "is required."
        )

    if any(
        checkpoint <= 0
        for checkpoint in checkpoints
    ):
        raise ValueError(
            "Checkpoints must be positive."
        )

    if tuple(
        sorted(
            checkpoints
        )
    ) != checkpoints:
        raise ValueError(
            "Checkpoints must be ascending."
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

    if args.float_decimals < 0:
        raise ValueError(
            "Float decimals cannot be "
            "negative."
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


def normalize_value(
    value,
    *,
    float_decimals: int,
):
    if isinstance(
        value,
        float,
    ):
        return round(
            value,
            float_decimals,
        )

    if isinstance(
        value,
        Enum,
    ):
        return value.value

    if is_dataclass(
        value
    ):
        return (
            type(value).__name__,
            tuple(
                (
                    field.name,
                    normalize_value(
                        getattr(
                            value,
                            field.name,
                        ),
                        float_decimals=(
                            float_decimals
                        ),
                    ),
                )
                for field in fields(
                    value
                )
            ),
        )

    if isinstance(
        value,
        tuple,
    ):
        return tuple(
            normalize_value(
                item,
                float_decimals=(
                    float_decimals
                ),
            )
            for item in value
        )

    if isinstance(
        value,
        list,
    ):
        return tuple(
            normalize_value(
                item,
                float_decimals=(
                    float_decimals
                ),
            )
            for item in value
        )

    if isinstance(
        value,
        dict,
    ):
        return tuple(
            sorted(
                (
                    normalize_value(
                        key,
                        float_decimals=(
                            float_decimals
                        ),
                    ),
                    normalize_value(
                        item,
                        float_decimals=(
                            float_decimals
                        ),
                    ),
                )
                for key, item in (
                    value.items()
                )
            )
        )

    return value


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


def collect_statistics(
    trainer: CFRTrainer,
    *,
    float_decimals: int,
) -> dict:
    states = tuple(
        trainer.node_store.nodes.keys()
    )

    public_nodes = {
        state.public_node
        for state in states
    }

    normalized_public_nodes = {
        normalize_value(
            state.public_node,
            float_decimals=(
                float_decimals
            ),
        )
        for state in states
    }

    private_keys = {
        state.own_hand_key
        for state in states
    }

    phases = Counter(
        phase_label(
            state.phase
        )
        for state in states
    )

    public_by_phase: dict[
        str,
        set,
    ] = {}

    normalized_public_by_phase: dict[
        str,
        set,
    ] = {}

    private_by_phase: dict[
        str,
        set,
    ] = {}

    states_per_public = Counter()

    normalized_states_per_public = (
        Counter()
    )

    for state in states:
        phase = phase_label(
            state.phase
        )

        public_by_phase.setdefault(
            phase,
            set(),
        ).add(
            state.public_node
        )

        normalized_public = (
            normalize_value(
                state.public_node,
                float_decimals=(
                    float_decimals
                ),
            )
        )

        normalized_public_by_phase.setdefault(
            phase,
            set(),
        ).add(
            normalized_public
        )

        private_by_phase.setdefault(
            phase,
            set(),
        ).add(
            state.own_hand_key
        )

        states_per_public[
            state.public_node
        ] += 1

        normalized_states_per_public[
            normalized_public
        ] += 1

    public_occupancies = tuple(
        states_per_public.values()
    )

    normalized_occupancies = tuple(
        normalized_states_per_public.values()
    )

    return {
        "states": len(
            states
        ),
        "public_nodes": len(
            public_nodes
        ),
        "normalized_public_nodes": len(
            normalized_public_nodes
        ),
        "private_keys": len(
            private_keys
        ),
        "phases": phases,
        "public_by_phase": {
            phase: len(values)
            for phase, values
            in public_by_phase.items()
        },
        "normalized_public_by_phase": {
            phase: len(values)
            for phase, values
            in (
                normalized_public_by_phase
                .items()
            )
        },
        "private_by_phase": {
            phase: len(values)
            for phase, values
            in private_by_phase.items()
        },
        "avg_states_per_public": (
            sum(
                public_occupancies
            )
            / len(
                public_occupancies
            )
            if public_occupancies
            else 0.0
        ),
        "max_states_per_public": (
            max(
                public_occupancies
            )
            if public_occupancies
            else 0
        ),
        "avg_states_per_normalized_public": (
            sum(
                normalized_occupancies
            )
            / len(
                normalized_occupancies
            )
            if normalized_occupancies
            else 0.0
        ),
        "max_states_per_normalized_public": (
            max(
                normalized_occupancies
            )
            if normalized_occupancies
            else 0
        ),
    }


def print_phase_table(
    statistics: dict,
) -> None:
    phases = sorted(
        statistics[
            "phases"
        ]
    )

    print(
        "  phase breakdown:"
    )

    for phase in phases:
        state_count = (
            statistics[
                "phases"
            ][
                phase
            ]
        )

        public_count = (
            statistics[
                "public_by_phase"
            ].get(
                phase,
                0,
            )
        )

        normalized_public_count = (
            statistics[
                "normalized_public_by_phase"
            ].get(
                phase,
                0,
            )
        )

        private_count = (
            statistics[
                "private_by_phase"
            ].get(
                phase,
                0,
            )
        )

        print(
            f"    {phase}:"
        )

        print(
            f"      information states: "
            f"{state_count:,}"
        )

        print(
            f"      public nodes: "
            f"{public_count:,}"
        )

        print(
            f"      normalized public: "
            f"{normalized_public_count:,}"
        )

        print(
            f"      private keys: "
            f"{private_count:,}"
        )


def print_statistics(
    *,
    iteration: int,
    statistics: dict,
) -> None:
    public_nodes = (
        statistics[
            "public_nodes"
        ]
    )

    normalized_public_nodes = (
        statistics[
            "normalized_public_nodes"
        ]
    )

    float_duplicates = (
        public_nodes
        - normalized_public_nodes
    )

    if public_nodes > 0:
        fragmentation_ratio = (
            float_duplicates
            / public_nodes
        )
    else:
        fragmentation_ratio = 0.0

    print()
    print(
        "=" * 72
    )

    print(
        f"ITERATION {iteration:,}"
    )

    print(
        f"  information states: "
        f"{statistics['states']:,}"
    )

    print(
        f"  exact public nodes: "
        f"{public_nodes:,}"
    )

    print(
        f"  normalized public nodes: "
        f"{normalized_public_nodes:,}"
    )

    print(
        f"  possible float-fragmented "
        f"public nodes: "
        f"{float_duplicates:,} "
        f"({fragmentation_ratio:.2%})"
    )

    print(
        f"  unique private keys: "
        f"{statistics['private_keys']:,}"
    )

    print(
        f"  avg states/public node: "
        f"{statistics['avg_states_per_public']:.3f}"
    )

    print(
        f"  max states/public node: "
        f"{statistics['max_states_per_public']:,}"
    )

    print(
        "  avg states/normalized "
        "public node: "
        f"{statistics['avg_states_per_normalized_public']:.3f}"
    )

    print(
        "  max states/normalized "
        "public node: "
        f"{statistics['max_states_per_normalized_public']:,}"
    )

    print_phase_table(
        statistics
    )


def print_growth(
    *,
    previous_iteration: int,
    previous: dict,
    current_iteration: int,
    current: dict,
) -> None:
    print()
    print(
        f"{previous_iteration:,} "
        f"-> "
        f"{current_iteration:,}"
    )

    state_growth = (
        current[
            "states"
        ]
        - previous[
            "states"
        ]
    )

    public_growth = (
        current[
            "public_nodes"
        ]
        - previous[
            "public_nodes"
        ]
    )

    normalized_public_growth = (
        current[
            "normalized_public_nodes"
        ]
        - previous[
            "normalized_public_nodes"
        ]
    )

    private_growth = (
        current[
            "private_keys"
        ]
        - previous[
            "private_keys"
        ]
    )

    print(
        f"  new information states: "
        f"{state_growth:,}"
    )

    print(
        f"  new public nodes: "
        f"{public_growth:,}"
    )

    print(
        f"  new normalized public nodes: "
        f"{normalized_public_growth:,}"
    )

    print(
        f"  new private keys: "
        f"{private_growth:,}"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    checkpoints = parse_checkpoints(
        args.checkpoints
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
        "CFR state-space growth diagnostic"
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
        f"  normalized float decimals: "
        f"{args.float_decimals}"
    )

    completed = 0

    snapshots: list[
        tuple[
            int,
            dict,
        ]
    ] = []

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

        statistics = (
            collect_statistics(
                trainer,
                float_decimals=(
                    args.float_decimals
                ),
            )
        )

        snapshots.append(
            (
                checkpoint,
                statistics,
            )
        )

        print_statistics(
            iteration=checkpoint,
            statistics=statistics,
        )

        completed = checkpoint

    if len(
        snapshots
    ) >= 2:
        print()
        print(
            "=" * 72
        )

        print(
            "GROWTH"
        )

        for index in range(
            1,
            len(
                snapshots
            ),
        ):
            (
                previous_iteration,
                previous,
            ) = snapshots[
                index - 1
            ]

            (
                current_iteration,
                current,
            ) = snapshots[
                index
            ]

            print_growth(
                previous_iteration=(
                    previous_iteration
                ),
                previous=previous,
                current_iteration=(
                    current_iteration
                ),
                current=current,
            )


if __name__ == "__main__":
    main()