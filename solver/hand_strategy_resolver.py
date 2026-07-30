from dataclasses import dataclass

from solver.draw_hand_bucket import (
    draw_hand_bucket,
)
from solver.hand import Hand
from solver.hand_abstraction import (
    exact_hand_key,
)
from solver.information_state import (
    AbstractionMode,
    PrivateHandKey,
)
from solver.made_hand_bucket import (
    made_hand_bucket,
)
from solver.single_draw_game import (
    GamePhase,
)


@dataclass(frozen=True)
class HandStrategyResolver:
    abstraction: AbstractionMode

    def resolve(
        self,
        *,
        hand: Hand,
        phase: GamePhase,
    ) -> PrivateHandKey:
        if self.abstraction == "exact":
            return exact_hand_key(
                hand
            )

        if self.abstraction == "bucket":
            if (
                phase
                == GamePhase.POSTDRAW_BETTING
            ):
                return made_hand_bucket(
                    hand
                )

            return draw_hand_bucket(
                hand
            )

        raise ValueError(
            "Unknown abstraction mode."
        )