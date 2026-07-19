from dataclasses import dataclass
from typing import TypeAlias

from solver.actions import DiscardAction
from solver.discard_actions import generate_discard_actions
from solver.game_state import ActionType
from solver.single_draw_game import GamePhase, SingleDrawGame


@dataclass(frozen=True)
class BettingAction:
    action_type: ActionType
    raise_to: float | None = None

    def __post_init__(self) -> None:
        if self.action_type == ActionType.RAISE:
            if self.raise_to is None:
                raise ValueError(
                    "Raise action must include raise_to."
                )

            if self.raise_to < 0:
                raise ValueError(
                    "Raise amount cannot be negative."
                )

        elif self.raise_to is not None:
            raise ValueError(
                "Only raise actions may include raise_to."
            )


SolverAction: TypeAlias = BettingAction | DiscardAction


def legal_actions(
    game: SingleDrawGame,
    *,
    max_draw: int = 3,
    raise_sizes: tuple[float, ...] = (),
) -> tuple[SolverAction, ...]:
    if game.phase == GamePhase.COMPLETE:
        return ()

    if game.phase == GamePhase.DRAW:
        return generate_discard_actions(
            hand_size=5,
            max_draw=max_draw,
        )

    return _legal_betting_actions(
        game,
        raise_sizes=raise_sizes,
    )


def _legal_betting_actions(
    game: SingleDrawGame,
    *,
    raise_sizes: tuple[float, ...],
) -> tuple[BettingAction, ...]:
    state = game.betting_state
    acting_seat = state.acting_seat

    if acting_seat is None:
        return ()

    player = state.players[acting_seat]

    if player.has_folded or player.is_all_in:
        return ()

    actions: list[BettingAction] = []

    amount_to_call = (
        state.current_bet
        - player.committed_total
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

    for raise_to in raise_sizes:
        if _raise_is_legal(
            game,
            raise_to=raise_to,
        ):
            actions.append(
                BettingAction(
                    ActionType.RAISE,
                    raise_to=raise_to,
                )
            )

    return tuple(actions)


def _raise_is_legal(
    game: SingleDrawGame,
    *,
    raise_to: float,
) -> bool:
    state = game.betting_state
    acting_seat = state.acting_seat

    if acting_seat is None:
        return False

    player = state.players[acting_seat]

    if player.has_folded or player.is_all_in:
        return False

    if raise_to <= state.current_bet:
        return False

    maximum_raise_to = (
        player.committed_total
        + player.stack
    )

    if raise_to > maximum_raise_to:
        return False

    minimum_raise_to = state.minimum_raise_to()

    if raise_to >= minimum_raise_to:
        return True

    # Allow an all-in raise below the normal minimum raise.
    return raise_to == maximum_raise_to