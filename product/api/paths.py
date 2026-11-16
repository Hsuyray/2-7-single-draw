"""
Action paths for the query API (docs/API.md section 2).

A path is a "/"-joined list of public action tokens from the root:
F fold, X check, C call, R<pct> pot-percentage bet / raise (as labelled,
e.g. R50), RA all-in, D<n> draw n cards. The public tree does not
depend on the cards, so a path is walked on a game dealt from a fixed
deck; draws apply any discard of the right size.

Training uses button_seat=0 only, so the API walks button_seat=0
games: seat 0 is BTN and seat 1 is BB (docs/API.md section 0.3).
"""

import re
from dataclasses import dataclass

from solver.checkpoint_evaluation import EvaluationSetup
from solver.game_state import ActionType
from solver.legal_actions import BettingAction
from solver.public_legal_actions import (
    PublicBettingAction,
    PublicDrawAction,
    public_legal_actions,
)
from solver.public_node_navigator import PublicNodeNavigator
from solver.single_draw_game import SingleDrawGame


BUTTON_SEAT = 0

POSITIONS = {
    0: "BTN",
    1: "BB",
}

_PERCENT_LABEL = re.compile(r"^(\d+)% Pot$")

_SIMPLE_TOKENS = {
    ActionType.FOLD: "F",
    ActionType.CHECK: "X",
    ActionType.CALL: "C",
}


class IllegalPath(ValueError):
    def __init__(self, at: str, legal: list[str]) -> None:
        super().__init__(
            f"Action {at!r} is not legal here; "
            f"legal: {legal}"
        )
        self.at = at
        self.legal = legal


def action_token(action) -> str:
    if isinstance(action, PublicDrawAction):
        return f"D{action.draw_count}"

    if action.action_type in _SIMPLE_TOKENS:
        return _SIMPLE_TOKENS[action.action_type]

    if action.is_all_in:
        return "RA"

    match = _PERCENT_LABEL.match(action.label)

    if match is None:
        raise ValueError(
            f"Raise label {action.label!r} has no "
            "pot percentage; the API needs a "
            "policy (percentage) bet sizing."
        )

    return f"R{match.group(1)}"


def solver_action(action):
    """
    The SolverAction a public betting action stands for,
    as stored in a strategy (same raise_to float, no
    recomputation). Draw actions map to several solver
    actions and are handled by the caller.
    """
    if isinstance(action, PublicBettingAction):
        return BettingAction(
            action_type=action.action_type,
            raise_to=action.raise_to,
        )

    raise TypeError("Draw actions have no single solver action.")


@dataclass(frozen=True)
class Decision:
    """One decision taken on the path."""

    seat: int
    public_node: object
    phase: str
    action: object
    token: str
    # Number of legal actions at the decision (for the
    # uniform fallback when a strategy is missing).
    legal_count: int


def new_game(setup: EvaluationSetup) -> SingleDrawGame:
    return SingleDrawGame(
        config=setup.game_config,
        button_seat=BUTTON_SEAT,
        deck_seed=0,
    )


def legal_public_actions(
    game: SingleDrawGame,
    setup: EvaluationSetup,
) -> tuple:
    snapshot = public_legal_actions(
        game,
        max_draw=setup.max_draw,
        raise_sizes=setup.raise_sizes,
        bet_sizing_policy=setup.bet_sizing_policy,
        draw_action_mode=setup.draw_action_mode,
    )

    return () if snapshot is None else snapshot.actions


def split_path(path: str) -> list[str]:
    return [
        token
        for token in path.strip().strip("/").split("/")
        if token
    ]


def walk(
    setup: EvaluationSetup,
    path: str,
) -> tuple[PublicNodeNavigator, list[Decision]]:
    navigator = PublicNodeNavigator.from_game(
        new_game(setup)
    )

    decisions: list[Decision] = []

    for token in split_path(path):
        if navigator.is_terminal:
            raise IllegalPath(token, [])

        actions = legal_public_actions(
            navigator.game,
            setup,
        )

        by_token = {
            action_token(action): action
            for action in actions
        }

        action = by_token.get(token)

        if action is None:
            raise IllegalPath(token, list(by_token))

        decisions.append(
            Decision(
                seat=navigator.acting_seat,
                public_node=navigator.public_node(),
                phase=navigator.phase.value,
                action=action,
                token=token,
                legal_count=len(actions),
            )
        )

        if isinstance(action, PublicDrawAction):
            navigator.apply_draw(
                discard_indices=tuple(
                    range(action.draw_count)
                ),
            )
        else:
            navigator.apply_betting(
                action.action_type,
                raise_to=action.raise_to,
            )

    return navigator, decisions

