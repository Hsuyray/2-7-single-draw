from dataclasses import dataclass
from typing import Literal, TypeAlias

from solver.actions import DiscardAction
from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.discard_actions import (
    candidate_discard_actions,
    generate_discard_actions,
)
from solver.game_state import ActionType
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


DrawActionMode = Literal[
    "full",
    "candidate",
]


@dataclass(frozen=True)
class BettingAction:
    action_type: ActionType
    raise_to: float | None = None

    def __post_init__(self) -> None:
        if self.action_type == ActionType.RAISE:
            if self.raise_to is None:
                raise ValueError(
                    "Raise action must include "
                    "raise_to."
                )

            if self.raise_to < 0:
                raise ValueError(
                    "Raise amount cannot "
                    "be negative."
                )

        elif self.raise_to is not None:
            raise ValueError(
                "Only raise actions may "
                "include raise_to."
            )


SolverAction: TypeAlias = (
    BettingAction
    | DiscardAction
)


def legal_actions(
    game: SingleDrawGame,
    *,
    max_draw: int = 3,
    raise_sizes: tuple[float, ...] | None = (),
    bet_sizing_policy: BetSizingPolicy | None = None,
    draw_action_mode: DrawActionMode = "full",
) -> tuple[SolverAction, ...]:
    """
    Return legal solver actions.

    Betting sizing semantics:

    raise_sizes is None:
        Use BetSizingPolicy.

    raise_sizes == ():
        Do not generate raise actions.

    raise_sizes contains values:
        Treat them as explicit absolute
        raise-to amounts.
    """
    if game.phase == GamePhase.COMPLETE:
        return ()

    if game.phase == GamePhase.DRAW:
        return _legal_draw_actions(
            game,
            max_draw=max_draw,
            draw_action_mode=(
                draw_action_mode
            ),
        )

    return _legal_betting_actions(
        game,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
    )


def _legal_draw_actions(
    game: SingleDrawGame,
    *,
    max_draw: int,
    draw_action_mode: DrawActionMode,
) -> tuple[DiscardAction, ...]:
    acting_seat = game.draw_acting_seat

    if acting_seat is None:
        return ()

    hand = game.hands[
        acting_seat
    ]

    if hand is None:
        raise RuntimeError(
            f"Seat {acting_seat} does not "
            "have a hand."
        )

    if draw_action_mode == "full":
        return generate_discard_actions(
            hand_size=len(
                hand.cards
            ),
            max_draw=max_draw,
        )

    if draw_action_mode == "candidate":
        return candidate_discard_actions(
            hand,
            max_draw=max_draw,
        )

    raise ValueError(
        "Unknown draw action mode: "
        f"{draw_action_mode}"
    )


def _legal_betting_actions(
    game: SingleDrawGame,
    *,
    raise_sizes: tuple[float, ...] | None,
    bet_sizing_policy: BetSizingPolicy | None,
) -> tuple[BettingAction, ...]:
    state = game.betting_state
    acting_seat = state.acting_seat

    if acting_seat is None:
        return ()

    player = state.players[
        acting_seat
    ]

    if (
        player.has_folded
        or player.is_all_in
    ):
        return ()

    actions: list[
        BettingAction
    ] = []

    amount_to_call = (
        state.amount_to_call(
            acting_seat
        )
    )

    if amount_to_call > 0:
        actions.append(
            BettingAction(
                ActionType.FOLD
            )
        )

        actions.append(
            BettingAction(
                ActionType.CALL
            )
        )

    else:
        actions.append(
            BettingAction(
                ActionType.CHECK
            )
        )

    candidate_raise_sizes = (
        _candidate_raise_sizes(
            game,
            raise_sizes=raise_sizes,
            bet_sizing_policy=(
                bet_sizing_policy
            ),
        )
    )

    for raise_to in candidate_raise_sizes:
        if not _raise_is_legal(
            game,
            raise_to=raise_to,
        ):
            continue

        actions.append(
            BettingAction(
                ActionType.RAISE,
                raise_to=raise_to,
            )
        )

    return tuple(
        actions
    )


def _candidate_raise_sizes(
    game: SingleDrawGame,
    *,
    raise_sizes: tuple[float, ...] | None,
    bet_sizing_policy: BetSizingPolicy | None,
) -> tuple[float, ...]:
    """
    Generate discrete absolute raise-to sizes.

    None:
        use pot-based BetSizingPolicy

    ():
        explicitly disable raises

    non-empty tuple:
        explicit raise-to override
    """

    # Explicit legacy/debug override.
    if raise_sizes is not None:
        return tuple(
            sorted(
                set(
                    raise_sizes
                )
            )
        )

    policy = (
        bet_sizing_policy
        if bet_sizing_policy is not None
        else BetSizingPolicy()
    )

    state = game.betting_state
    acting_seat = state.acting_seat

    if acting_seat is None:
        return ()

    player = state.players[
        acting_seat
    ]

    if (
        player.has_folded
        or player.is_all_in
    ):
        return ()

    amount_to_call = (
        state.amount_to_call(
            acting_seat
        )
    )

    minimum_raise_to = (
        state.minimum_raise_to()
    )

    maximum_raise_to = (
        state.maximum_raise_to(
            acting_seat
        )
    )

    candidates = (
        policy.raise_to_candidates(
            pot=game.pot,
            committed_this_round=(
                player.committed_this_round
            ),
            stack=player.stack,
            amount_to_call=(
                amount_to_call
            ),
            minimum_raise_to=(
                minimum_raise_to
            ),
            maximum_raise_to=(
                maximum_raise_to
            ),
        )
    )

    # BetSizingPolicy generates the abstraction.
    # The engine remains the final authority
    # on whether each raise is legal.
    return tuple(
        raise_to
        for raise_to in candidates
        if _raise_is_legal(
            game,
            raise_to=raise_to,
        )
    )


def _raise_is_legal(
    game: SingleDrawGame,
    *,
    raise_to: float,
) -> bool:
    state = game.betting_state
    acting_seat = state.acting_seat

    if acting_seat is None:
        return False

    player = state.players[
        acting_seat
    ]

    if (
        player.has_folded
        or player.is_all_in
    ):
        return False

    if raise_to <= state.current_bet:
        return False

    maximum_raise_to = (
        state.maximum_raise_to(
            acting_seat
        )
    )

    if raise_to > maximum_raise_to:
        return False

    minimum_raise_to = (
        state.minimum_raise_to()
    )

    if raise_to >= minimum_raise_to:
        return True

    # A player may still move all-in for
    # less than a normal minimum raise.
    return (
        raise_to
        == maximum_raise_to
    )