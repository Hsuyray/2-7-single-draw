from dataclasses import dataclass

from solver.information_state import (
    PrivateHandKey,
)
from solver.legal_actions import (
    SolverAction,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.range_tracker import (
    RangeTracker,
)
from solver.strategy_index import (
    Strategy,
    StrategyIndex,
)


@dataclass(frozen=True)
class RangeEntry:
    hand_key: PrivateHandKey
    weight: float
    strategy: Strategy


@dataclass(frozen=True)
class RangeSnapshot:
    public_node: PublicNodeKey
    acting_seat: int
    entries: tuple[
        RangeEntry,
        ...
    ]

    @property
    def total_weight(self) -> float:
        return sum(
            entry.weight
            for entry in self.entries
        )

    @property
    def hand_count(self) -> int:
        return len(
            self.entries
        )

    def entry_for_hand(
        self,
        hand_key: PrivateHandKey,
    ) -> RangeEntry | None:
        for entry in self.entries:
            if (
                entry.hand_key
                == hand_key
            ):
                return entry

        return None

    def aggregate_action_frequency(
        self,
        action: SolverAction,
    ) -> float:
        total_weight = (
            self.total_weight
        )

        if total_weight <= 0:
            return 0.0

        weighted_action = sum(
            entry.weight
            * entry.strategy.get(
                action,
                0.0,
            )
            for entry in self.entries
        )

        return (
            weighted_action
            / total_weight
        )


def build_range_snapshot(
    *,
    public_node: PublicNodeKey,
    acting_seat: int,
    strategy_index: StrategyIndex,
    range_tracker: RangeTracker,
) -> RangeSnapshot:
    strategies = (
        strategy_index.range_strategy(
            public_node=public_node,
            observer_seat=acting_seat,
        )
    )

    weights = (
        range_tracker.range_for_seat(
            acting_seat
        )
    )

    entries: list[
        RangeEntry
    ] = []

    for (
        hand_key,
        strategy,
    ) in strategies.items():
        weight = weights.get(
            hand_key,
            0.0,
        )

        entries.append(
            RangeEntry(
                hand_key=hand_key,
                weight=weight,
                strategy=dict(
                    strategy
                ),
            )
        )

    return RangeSnapshot(
        public_node=public_node,
        acting_seat=acting_seat,
        entries=tuple(
            entries
        ),
    )