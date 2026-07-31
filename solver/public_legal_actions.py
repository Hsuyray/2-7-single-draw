from dataclasses import dataclass

from solver.legal_actions import (
    SolverAction,
    legal_actions,
)
from solver.single_draw_game import (
    SingleDrawGame,
)


@dataclass(frozen=True)
class PublicLegalActionSnapshot:
    """
    Public-facing legal actions available
    at the current decision node.

    The UI/query layer should consume this
    instead of reimplementing poker rules.
    """

    acting_seat: int
    actions: tuple[
        SolverAction,
        ...,
    ]

    @property
    def action_count(self) -> int:
        return len(
            self.actions
        )


def public_legal_actions(
    game: SingleDrawGame,
) -> PublicLegalActionSnapshot | None:
    acting_seat = game.acting_seat

    if acting_seat is None:
        return None

    actions = tuple(
        legal_actions(
            game
        )
    )

    return PublicLegalActionSnapshot(
        acting_seat=acting_seat,
        actions=actions,
    )