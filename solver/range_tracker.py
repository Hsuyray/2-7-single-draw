from dataclasses import dataclass, field

from solver.information_state import (
    PrivateHandKey,
)
from solver.legal_actions import (
    SolverAction,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.starting_range import (
    StartingRange,
)
from solver.strategy_index import (
    StrategyIndex,
)


@dataclass
class RangeTracker:
    """
    Tracks private-hand weights through
    public action history.

    A hand weight represents how much of
    that private hand remains in a player's
    range at the current public node.
    """

    weights: dict[
        int,
        dict[
            PrivateHandKey,
            float,
        ],
    ] = field(
        default_factory=dict
    )

    def initialize_player(
        self,
        *,
        seat: int,
        hand_keys: tuple[
            PrivateHandKey,
            ...
        ],
        initial_weight: float = 1.0,
    ) -> None:
        if initial_weight < 0:
            raise ValueError(
                "Initial weight cannot "
                "be negative."
            )

        self.weights[seat] = {
            hand_key: initial_weight
            for hand_key
            in hand_keys
        }

    def initialize_from_starting_range(
        self,
        *,
        seat: int,
        starting_range: StartingRange,
    ) -> None:
        self.weights[seat] = (
            starting_range.copy_weights()
        )

    def has_player(
        self,
        seat: int,
    ) -> bool:
        return seat in self.weights

    def range_for_seat(
        self,
        seat: int,
    ) -> dict[
        PrivateHandKey,
        float,
    ]:
        return dict(
            self.weights.get(
                seat,
                {},
            )
        )

    def weight_for_hand(
        self,
        *,
        seat: int,
        hand_key: PrivateHandKey,
    ) -> float:
        return (
            self.weights.get(
                seat,
                {},
            ).get(
                hand_key,
                0.0,
            )
        )

    def set_range(
        self,
        *,
        seat: int,
        weights: dict[
            PrivateHandKey,
            float,
        ],
    ) -> None:
        if any(
            weight < 0
            for weight in weights.values()
        ):
            raise ValueError(
                "Range weights cannot "
                "be negative."
            )

        self.weights[seat] = dict(
            weights
        )

    def conditioned_range(
        self,
        *,
        public_node: PublicNodeKey,
        acting_seat: int,
        action: SolverAction,
        strategy_index: StrategyIndex,
        normalize: bool = False,
    ) -> dict[
        PrivateHandKey,
        float,
    ]:
        """
        Calculate the acting player's range
        after observing one public action.

        This method does not mutate the
        tracker.

        For every private hand:

            new weight
            =
            current weight
            * action probability
        """
        current_range = (
            self.weights.get(
                acting_seat
            )
        )

        if current_range is None:
            raise ValueError(
                "Acting player's range "
                "has not been initialized."
            )

        strategies = (
            strategy_index.range_strategy(
                public_node=public_node,
                observer_seat=acting_seat,
            )
        )

        updated_range: dict[
            PrivateHandKey,
            float,
        ] = {}

        for (
            hand_key,
            current_weight,
        ) in current_range.items():
            strategy = strategies.get(
                hand_key
            )

            if strategy is None:
                continue

            action_probability = (
                strategy.get(
                    action,
                    0.0,
                )
            )

            updated_range[hand_key] = (
                current_weight
                * action_probability
            )

        if normalize:
            return self._normalized_weights(
                updated_range
            )

        return updated_range

    def apply_action(
        self,
        *,
        public_node: PublicNodeKey,
        acting_seat: int,
        action: SolverAction,
        strategy_index: StrategyIndex,
        normalize: bool = False,
    ) -> None:
        updated_range = (
            self.conditioned_range(
                public_node=public_node,
                acting_seat=acting_seat,
                action=action,
                strategy_index=(
                    strategy_index
                ),
                normalize=normalize,
            )
        )

        self.set_range(
            seat=acting_seat,
            weights=updated_range,
        )

    def normalize(
        self,
        *,
        seat: int,
    ) -> None:
        current_range = (
            self.weights.get(
                seat
            )
        )

        if current_range is None:
            raise ValueError(
                "Player range has not "
                "been initialized."
            )

        self.weights[seat] = (
            self._normalized_weights(
                current_range
            )
        )

    @staticmethod
    def _normalized_weights(
        weights: dict[
            PrivateHandKey,
            float,
        ],
    ) -> dict[
        PrivateHandKey,
        float,
    ]:
        total_weight = sum(
            weights.values()
        )

        if total_weight <= 0:
            return dict(
                weights
            )

        return {
            hand_key: (
                weight / total_weight
            )
            for hand_key, weight
            in weights.items()
        }