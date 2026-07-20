from copy import deepcopy

from solver.actions import DiscardAction
from solver.legal_actions import (
    BettingAction,
    SolverAction,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def clone_game(
    game: SingleDrawGame,
) -> SingleDrawGame:
    return deepcopy(game)


def apply_solver_action(
    game: SingleDrawGame,
    action: SolverAction,
) -> SingleDrawGame:
    next_game = clone_game(game)

    if isinstance(action, BettingAction):
        _apply_betting_action(
            next_game,
            action,
        )
        return next_game

    if isinstance(action, DiscardAction):
        _apply_discard_action(
            next_game,
            action,
        )
        return next_game

    raise TypeError(
        "Unsupported solver action type."
    )


def _apply_betting_action(
    game: SingleDrawGame,
    action: BettingAction,
) -> None:
    if game.phase not in {
        GamePhase.PREDRAW_BETTING,
        GamePhase.POSTDRAW_BETTING,
    }:
        raise ValueError(
            "Betting actions can only be applied "
            "during a betting phase."
        )

    game.apply_betting_action(
        action.action_type,
        raise_to=action.raise_to,
    )


def _apply_discard_action(
    game: SingleDrawGame,
    action: DiscardAction,
) -> None:
    if game.phase != GamePhase.DRAW:
        raise ValueError(
            "Discard actions can only be applied "
            "during the draw phase."
        )

    acting_seat = game.draw_acting_seat

    if acting_seat is None:
        raise RuntimeError(
            "No player is currently waiting to draw."
        )

    game.submit_draw(
        seat=acting_seat,
        discard_indices=list(
            action.discard_indices
        ),
    )