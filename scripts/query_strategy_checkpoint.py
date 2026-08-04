import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from solver.actions import (  # noqa: E402
    DiscardAction,
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.information_state import (  # noqa: E402
    InformationState,
)
from solver.legal_actions import (  # noqa: E402
    BettingAction,
    SolverAction,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)
from solver.strategy_checkpoint import (  # noqa: E402
    LoadedStrategyCheckpoint,
    load_strategy_checkpoint,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Query one root information-state "
            "strategy from a saved 2-7 Single "
            "Draw checkpoint."
        )
    )

    parser.add_argument(
        "checkpoint",
        type=Path,
        help=(
            "Path to the compressed strategy "
            "checkpoint."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help=(
            "Deck seed used to create the "
            "private root hand."
        ),
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
        help=(
            "Starting stack used by the "
            "training game."
        ),
    )

    parser.add_argument(
        "--button-seat",
        type=int,
        choices=(
            0,
            1,
        ),
        default=0,
        help=(
            "Button seat used to create the "
            "root game."
        ),
    )

    parser.add_argument(
        "--observer-seat",
        type=int,
        choices=(
            0,
            1,
        ),
        default=None,
        help=(
            "Seat whose private strategy is "
            "queried. By default, use the "
            "current acting seat."
        ),
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.stack <= 0:
        raise ValueError(
            "Starting stack must be positive."
        )


def make_root_game(
    *,
    stack: float,
    button_seat: int,
    seed: int,
) -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=stack,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=button_seat,
        deck_seed=seed,
    )


def action_label(
    action: SolverAction,
) -> str:
    if isinstance(
        action,
        BettingAction,
    ):
        action_type = (
            action.action_type
        )

        action_name = getattr(
            action_type,
            "value",
            str(action_type),
        )

        raise_to = getattr(
            action,
            "raise_to",
            None,
        )

        if raise_to is not None:
            return (
                f"{action_name} "
                f"to {raise_to:g}"
            )

        return str(
            action_name
        )

    if isinstance(
        action,
        DiscardAction,
    ):
        if not action.discard_indices:
            return "stand pat"

        indices = ", ".join(
            str(index)
            for index
            in action.discard_indices
        )

        return (
            f"discard "
            f"{action.draw_count}: "
            f"({indices})"
        )

    return repr(
        action
    )


def print_checkpoint_summary(
    loaded: LoadedStrategyCheckpoint,
) -> None:
    metadata = loaded.metadata

    print(
        "Checkpoint:"
    )

    print(
        f"  game: "
        f"{metadata.game}"
    )

    print(
        f"  abstraction: "
        f"{metadata.abstraction}"
    )

    print(
        f"  iterations: "
        f"{metadata.completed_iterations}"
    )

    print(
        f"  information states: "
        f"{loaded.strategy_count}"
    )

    print(
        f"  max draw: "
        f"{metadata.max_draw}"
    )

    print(
        f"  draw actions: "
        f"{metadata.draw_action_mode}"
    )

    print(
        f"  raise sizes: "
        f"{metadata.raise_sizes}"
    )


def print_game_summary(
    *,
    game: SingleDrawGame,
    observer_seat: int,
) -> None:
    acting_seat = game.acting_seat

    hand = game.hands[
        observer_seat
    ]

    print(
        "Query:"
    )

    print(
        f"  phase: "
        f"{game.phase}"
    )

    print(
        f"  acting seat: "
        f"{acting_seat}"
    )

    print(
        f"  observer seat: "
        f"{observer_seat}"
    )

    print(
        f"  button seat: "
        f"{game.button_seat}"
    )

    print(
        f"  private hand: "
        f"{hand}"
    )


def print_strategy(
    strategy: dict[
        SolverAction,
        float,
    ],
) -> None:
    ordered_actions = sorted(
        strategy.items(),
        key=lambda item: (
            -item[1],
            action_label(
                item[0]
            ),
        ),
    )

    print(
        "Strategy:"
    )

    for action, probability in (
        ordered_actions
    ):
        print(
            f"  {action_label(action):<24}"
            f"{probability:>9.4%}"
        )

    print(
        f"  total:"
        f"{sum(strategy.values()):>27.4%}"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    loaded = (
        load_strategy_checkpoint(
            args.checkpoint
        )
    )

    game = make_root_game(
        stack=args.stack,
        button_seat=args.button_seat,
        seed=args.seed,
    )

    acting_seat = game.acting_seat

    if acting_seat is None:
        raise RuntimeError(
            "Root game does not have an "
            "acting player."
        )

    observer_seat = (
        acting_seat
        if args.observer_seat is None
        else args.observer_seat
    )

    state = InformationState.from_game(
        game,
        observer_seat=observer_seat,
        abstraction=(
            loaded.metadata.abstraction
        ),
    )

    strategy = (
        loaded.strategy_index
        .strategy_for_state(
            state
        )
    )

    print_checkpoint_summary(
        loaded
    )

    print()

    print_game_summary(
        game=game,
        observer_seat=observer_seat,
    )

    print()

    if strategy is None:
        print(
            "Strategy not found."
        )

        print(
            "This exact information state "
            "was not visited during training."
        )

        print(
            "Try another --seed, or train "
            "for more iterations."
        )

        return

    print_strategy(
        strategy
    )


if __name__ == "__main__":
    main()