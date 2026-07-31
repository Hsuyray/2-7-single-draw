from dataclasses import dataclass
from typing import Generic, TypeVar

from solver.information_state import (
    PrivateHandKey,
)


HandKeyT = TypeVar(
    "HandKeyT",
    bound=PrivateHandKey,
)


@dataclass(frozen=True)
class StartingRange(
    Generic[HandKeyT]
):
    """
    Starting distribution over canonical
    private-hand keys.

    The weight of a key is the number of
    raw five-card combinations represented
    by that key.

    Example:

        key A -> 24 combinations
        key B -> 12 combinations
    """

    weights: dict[
        HandKeyT,
        float,
    ]

    def __post_init__(self) -> None:
        for (
            hand_key,
            weight,
        ) in self.weights.items():
            if weight < 0:
                raise ValueError(
                    "Starting range weights "
                    "cannot be negative."
                )

            if not isinstance(
                weight,
                int | float,
            ):
                raise TypeError(
                    "Starting range weights "
                    "must be numeric."
                )

    @classmethod
    def from_counts(
        cls,
        counts: dict[
            HandKeyT,
            int,
        ],
    ) -> "StartingRange[HandKeyT]":
        return cls(
            weights={
                hand_key: float(count)
                for hand_key, count
                in counts.items()
            }
        )

    @property
    def total_weight(self) -> float:
        return sum(
            self.weights.values()
        )

    @property
    def hand_count(self) -> int:
        return len(
            self.weights
        )

    def weight_for_hand(
        self,
        hand_key: HandKeyT,
    ) -> float:
        return self.weights.get(
            hand_key,
            0.0,
        )

    def normalized(
        self,
    ) -> dict[
        HandKeyT,
        float,
    ]:
        total = self.total_weight

        if total <= 0:
            return {
                hand_key: 0.0
                for hand_key
                in self.weights
            }

        return {
            hand_key: (
                weight / total
            )
            for hand_key, weight
            in self.weights.items()
        }

    def copy_weights(
        self,
    ) -> dict[
        HandKeyT,
        float,
    ]:
        return dict(
            self.weights
        )