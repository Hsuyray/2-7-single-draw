from solver.actions import (
    DiscardAction,
)
from solver.exact_hand_codec import (
    actual_discard_action_for_hand,
    canonical_discard_action_for_hand,
)
from solver.legal_actions import (
    BettingAction,
    SolverAction,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def canonical_solver_actions_for_game(
    *,
    game: SingleDrawGame,
    actions: tuple[
        SolverAction,
        ...,
    ],
) -> tuple[
    SolverAction,
    ...,
]:
    """
    Convert legal draw actions from the
    current Hand.cards ordering into the
    canonical ExactHandKey ordering.

    Betting actions are returned unchanged.

    Canonical draw actions are sorted
    deterministically so suit-isomorphic
    hands produce exactly the same action
    tuple and ordering.
    """
    if game.phase != GamePhase.DRAW:
        return actions

    acting_seat = game.acting_seat

    if acting_seat is None:
        raise RuntimeError(
            "Draw phase has no acting player."
        )

    hand = game.hands[
        acting_seat
    ]

    if hand is None:
        raise RuntimeError(
            "Acting player does not have "
            "a hand."
        )

    canonical_actions: set[
        DiscardAction
    ] = set()

    for action in actions:
        if not isinstance(
            action,
            DiscardAction,
        ):
            raise RuntimeError(
                "Draw-phase legal actions "
                "must be discard actions."
            )

        canonical_action = (
            canonical_discard_action_for_hand(
                hand=hand,
                action=action,
            )
        )

        canonical_actions.add(
            canonical_action
        )

    return tuple(
        sorted(
            canonical_actions,
            key=lambda action: (
                action.draw_count,
                action.discard_indices,
            ),
        )
    )


def executable_solver_action_for_game(
    *,
    game: SingleDrawGame,
    action: SolverAction,
) -> SolverAction:
    """
    Convert one canonical CFR draw action into
    the current Hand.cards ordering before
    physical game execution.

    Betting actions are returned unchanged.
    """
    if isinstance(
        action,
        BettingAction,
    ):
        return action

    if not isinstance(
        action,
        DiscardAction,
    ):
        raise TypeError(
            "Unknown solver action type."
        )

    if game.phase != GamePhase.DRAW:
        raise RuntimeError(
            "Discard actions may only be "
            "executed during the draw phase."
        )

    acting_seat = game.acting_seat

    if acting_seat is None:
        raise RuntimeError(
            "Draw phase has no acting player."
        )

    hand = game.hands[
        acting_seat
    ]

    if hand is None:
        raise RuntimeError(
            "Acting player does not have "
            "a hand."
        )

    return actual_discard_action_for_hand(
        hand=hand,
        action=action,
    )