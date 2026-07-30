from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Literal,
    TypeAlias,
)

from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand_abstraction import (
    ExactHandKey,
    exact_hand_key,
)
from solver.made_hand_bucket import (
    MadeHandBucket,
    made_hand_bucket,
)
from solver.public_state import (
    PublicNodeKey,
)

if TYPE_CHECKING:
    from solver.single_draw_game import (
        SingleDrawGame,
    )


AbstractionMode = Literal[
    "exact",
    "bucket",
]


PrivateHandKey: TypeAlias = (
    ExactHandKey
    | DrawHandBucket
    | MadeHandBucket
)


@dataclass(frozen=True)
class InformationState:
    observer_seat: int
    public_node: PublicNodeKey
    own_hand_key: PrivateHandKey

    @property
    def phase(self) -> str:
        return self.public_node.phase

    @property
    def acting_seat(
        self,
    ) -> int | None:
        return self.public_node.acting_seat

    @property
    def button_seat(self) -> int:
        return self.public_node.button_seat

    @property
    def pot(self) -> float:
        return self.public_node.pot

    @property
    def players(self):
        return self.public_node.players

    @property
    def action_history(self):
        return self.public_node.action_history

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
                "Observer seat is outside "
                "the game."
            )

        own_hand = game.hands[
            observer_seat
        ]

        if own_hand is None:
            raise RuntimeError(
                "Observer does not have "
                "a hand."
            )

        own_hand_key = (
            _private_hand_key(
                game=game,
                observer_seat=(
                    observer_seat
                ),
                abstraction=abstraction,
            )
        )

        public_node = (
            PublicNodeKey.from_game(
                game
            )
        )

        return cls(
            observer_seat=observer_seat,
            public_node=public_node,
            own_hand_key=own_hand_key,
        )


def _private_hand_key(
    *,
    game: "SingleDrawGame",
    observer_seat: int,
    abstraction: AbstractionMode,
) -> PrivateHandKey:
    own_hand = game.hands[
        observer_seat
    ]

    if own_hand is None:
        raise RuntimeError(
            "Observer does not have "
            "a hand."
        )

    if abstraction == "exact":
        return exact_hand_key(
            own_hand
        )

    if abstraction == "bucket":
        if (
            game.phase.value
            == "postdraw_betting"
        ):
            return made_hand_bucket(
                own_hand
            )

        return draw_hand_bucket(
            own_hand
        )

    raise ValueError(
        "Unknown information-state "
        "abstraction."
    )