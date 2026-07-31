from dataclasses import dataclass, field

from solver.information_state import (
    PrivateHandKey,
)
from solver.legal_actions import (
    SolverAction,
)
from solver.strategy_index import (
    StrategyIndex,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.starting_range import (
    StartingRange,
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

    def apply_action(
        self,
        *,
        public_node: PublicNodeKey,
        acting_seat: int,
        action: SolverAction,
        strategy_index: StrategyIndex,
    ) -> None:
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
            strategy = (
                strategies.get(
                    hand_key
                )
            )

            if strategy is None:
                continue

            action_probability = (
                strategy.get(
                    action,
                    0.0,
                )
            )

            updated_range[
                hand_key
            ] = (
                current_weight
                * action_probability
            )

        self.weights[
            acting_seat
        ] = updated_range

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

        total_weight = sum(
            current_range.values()
        )

        if total_weight <= 0:
            return

        self.weights[seat] = {
            hand_key: (
                weight / total_weight
            )
            for hand_key, weight
            in current_range.items()
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