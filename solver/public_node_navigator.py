from copy import deepcopy
from dataclasses import dataclass

from solver.game_state import ActionType
from solver.public_state import PublicNodeKey
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


@dataclass
class PublicNodeNavigator:
    """
    Stateful navigator over a SingleDrawGame.

    This layer is intended for future UI / API use:

    current public node
        -> user selects action
        -> game state transition
        -> next public node

    It does not compute strategies.
    """

    game: SingleDrawGame

    @classmethod
    def from_game(
        cls,
        game: SingleDrawGame,
        *,
        copy_game: bool = True,
    ) -> "PublicNodeNavigator":
        if copy_game:
            game = deepcopy(game)

        return cls(game=game)

    @property
    def phase(self) -> GamePhase:
        return self.game.phase

    @property
    def acting_seat(self) -> int | None:
        return self.game.acting_seat

    @property
    def is_terminal(self) -> bool:
        return (
            self.game.phase
            == GamePhase.COMPLETE
        )

    def public_node(
        self,
    ) -> PublicNodeKey:
        return PublicNodeKey.from_game(
            self.game
        )

    def apply_betting(
        self,
        action_type: ActionType,
        *,
        raise_to: float | None = None,
    ) -> PublicNodeKey:
        if self.game.phase not in {
            GamePhase.PREDRAW_BETTING,
            GamePhase.POSTDRAW_BETTING,
        }:
            raise RuntimeError(
                "Betting action cannot be "
                "applied in the current phase."
            )

        self.game.apply_betting_action(
            action_type,
            raise_to=raise_to,
        )

        return self.public_node()

    def apply_draw(
        self,
        *,
        discard_indices: tuple[int, ...],
    ) -> PublicNodeKey:
        if (
            self.game.phase
            != GamePhase.DRAW
        ):
            raise RuntimeError(
                "Draw action cannot be "
                "applied outside the draw phase."
            )

        acting_seat = (
            self.game.draw_acting_seat
        )

        if acting_seat is None:
            raise RuntimeError(
                "No player is currently "
                "allowed to draw."
            )

        self.game.submit_draw(
            acting_seat,
            list(discard_indices),
        )

        return self.public_node()

    def clone(
        self,
    ) -> "PublicNodeNavigator":
        return PublicNodeNavigator(
            game=deepcopy(self.game)
        )