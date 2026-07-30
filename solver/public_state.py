from dataclasses import dataclass
from typing import TYPE_CHECKING

from solver.action_history import PublicAction

if TYPE_CHECKING:
    from solver.single_draw_game import SingleDrawGame


@dataclass(frozen=True)
class PublicPlayerState:
    seat: int
    stack: float
    committed_total: float
    has_folded: bool
    is_all_in: bool
    draw_count: int | None


@dataclass(frozen=True)
class PublicNodeKey:
    phase: str
    acting_seat: int | None
    button_seat: int
    pot: float
    players: tuple[
        PublicPlayerState,
        ...
    ]
    action_history: tuple[
        PublicAction,
        ...
    ]

    @classmethod
    def from_game(
        cls,
        game: "SingleDrawGame",
    ) -> "PublicNodeKey":
        public_players: list[
            PublicPlayerState
        ] = []

        for player in (
            game.betting_state.players
        ):
            draw_result = (
                game.draw_results.get(
                    player.seat
                )
            )

            draw_count = None

            if draw_result is not None:
                draw_count = (
                    draw_result.action.draw_count
                )

            public_players.append(
                PublicPlayerState(
                    seat=player.seat,
                    stack=player.stack,
                    committed_total=(
                        player.committed_total
                    ),
                    has_folded=(
                        player.has_folded
                    ),
                    is_all_in=(
                        player.is_all_in
                    ),
                    draw_count=draw_count,
                )
            )

        return cls(
            phase=game.phase.value,
            acting_seat=game.acting_seat,
            button_seat=game.button_seat,
            pot=game.pot,
            players=tuple(
                public_players
            ),
            action_history=tuple(
                game.action_history
            ),
        )