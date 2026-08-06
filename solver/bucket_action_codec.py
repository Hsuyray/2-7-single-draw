from solver.actions import (
    DiscardAction,
)
from solver.bucket_hand_codec import (
    actual_discard_action_for_bucket_hand,
    bucket_discard_action_for_hand,
)
from solver.legal_actions import (
    SolverAction,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def bucket_solver_actions_for_game(
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
    Convert physical draw actions into stable
    bucket-canonical action indices.
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

    bucket_actions: set[
        DiscardAction
    ] = set()

    for action in actions:
        if not isinstance(
            action,
            DiscardAction,
        ):
            raise RuntimeError(
                "Draw-phase actions must be "
                "DiscardAction objects."
            )

        bucket_actions.add(
            bucket_discard_action_for_hand(
                hand=hand,
                action=action,
            )
        )

    return tuple(
        sorted(
            bucket_actions,
            key=lambda action: (
                action.draw_count,
                action.discard_indices,
            ),
        )
    )


def executable_bucket_action_for_game(
    *,
    game: SingleDrawGame,
    action: SolverAction,
) -> SolverAction:
    """
    Convert one bucket-canonical CFR action
    into physical Hand.cards indices.
    """
    if not isinstance(
        action,
        DiscardAction,
    ):
        return action

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

    return (
        actual_discard_action_for_bucket_hand(
            hand=hand,
            action=action,
        )
    )