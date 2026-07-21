from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias

from solver.action_history import PublicAction
from solver.hand_abstraction import ExactHandKey, exact_hand_key
from solver.hand_bucket import HandBucket, hand_bucket
from solver.made_hand_bucket import (
    MadeHandBucket,
    made_hand_bucket,
)

if TYPE_CHECKING:
    from solver.single_draw_game import SingleDrawGame


AbstractionMode = Literal[
    "exact",
    "bucket",
]

PrivateHandKey: TypeAlias = (
    ExactHandKey
    | HandBucket
    | MadeHandBucket
)


@dataclass(frozen=True)
class PublicPlayerState:
    seat: int
    stack: float
    committed_total: float
    has_folded: bool
    is_all_in: bool
    draw_count: int | None


@dataclass(frozen=True)
class InformationState:
    observer_seat: int
    phase: str
    acting_seat: int | None
    button_seat: int
    pot: float
    own_hand_key: PrivateHandKey
    players: tuple[PublicPlayerState, ...]
    action_history: tuple[PublicAction, ...]

    @classmethod
    def from_game(
        cls,
        game: "SingleDrawGame",
        *,
        observer_seat: int,
        abstraction: AbstractionMode = "exact",
    ) -> "InformationState":
        if not (
            0
            <= observer_seat
            < game.config.player_count
        ):
            raise ValueError(
                "Observer seat is outside the game."
            )

        own_hand = game.hands[observer_seat]

        if own_hand is None:
            raise RuntimeError(
                "Observer does not have a hand."
            )

        if abstraction == "exact":
            own_hand_key: PrivateHandKey = (
                exact_hand_key(own_hand)
            )
        elif abstraction == "bucket":
            if game.phase.value == "postdraw_betting":
                own_hand_key = made_hand_bucket(
                    own_hand
                )
            else:
                own_hand_key = hand_bucket(
                    own_hand
                )
        else:
            raise ValueError(
                "Unknown information-state abstraction."
            )

        public_players: list[
            PublicPlayerState
        ] = []

        for player in game.betting_state.players:
            draw_result = game.draw_results.get(
                player.seat
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
                    has_folded=player.has_folded,
                    is_all_in=player.is_all_in,
                    draw_count=draw_count,
                )
            )

        return cls(
            observer_seat=observer_seat,
            phase=game.phase.value,
            acting_seat=game.acting_seat,
            button_seat=game.button_seat,
            pot=game.pot,
            own_hand_key=own_hand_key,
            players=tuple(public_players),
            action_history=tuple(
                game.action_history
            ),
        )