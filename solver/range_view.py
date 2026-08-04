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

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError(
                "Range-entry weight cannot "
                "be negative."
            )


@dataclass(frozen=True)
class RangeActionFrequency:
    """
    Aggregate frequency for one solver
    action across the current range.
    """

    action: SolverAction
    probability: float

    def __post_init__(self) -> None:
        if not (
            0.0
            <= self.probability
            <= 1.0
        ):
            raise ValueError(
                "Action probability must be "
                "between zero and one."
            )

    @property
    def percentage(self) -> float:
        return (
            self.probability
            * 100.0
        )


@dataclass(frozen=True)
class RangeStrategySummary:
    """
    Aggregate action strategy for the whole
    currently tracked range.

    The action objects remain SolverAction
    values. StrategyBrowser will later match
    them to UI-facing labels such as:

        Fold
        Call
        33% Pot
        66% Pot
        All-in
    """

    public_node: PublicNodeKey
    acting_seat: int
    total_weight: float
    hand_count: int
    actions: tuple[
        RangeActionFrequency,
        ...,
    ]

    def __post_init__(self) -> None:
        if self.total_weight < 0:
            raise ValueError(
                "Total range weight cannot "
                "be negative."
            )

        if self.hand_count < 0:
            raise ValueError(
                "Hand count cannot be "
                "negative."
            )

    @property
    def action_count(self) -> int:
        return len(
            self.actions
        )

    @property
    def total_probability(
        self,
    ) -> float:
        return sum(
            action.probability
            for action in self.actions
        )

    def frequency_for_action(
        self,
        action: SolverAction,
    ) -> float:
        for action_frequency in self.actions:
            if (
                action_frequency.action
                == action
            ):
                return (
                    action_frequency
                    .probability
                )

        return 0.0


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

    @property
    def actions(
        self,
    ) -> tuple[
        SolverAction,
        ...,
    ]:
        """
        Return every action appearing in at
        least one private-hand strategy.

        Encounter order is preserved.
        """
        actions: list[
            SolverAction
        ] = []

        seen: set[
            SolverAction
        ] = set()

        for entry in self.entries:
            for action in entry.strategy:
                if action in seen:
                    continue

                seen.add(
                    action
                )

                actions.append(
                    action
                )

        return tuple(
            actions
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
        """
        Return the range-weighted frequency
        of one action.

        Example:

            Hand A:
                weight 2
                Call 100%

            Hand B:
                weight 1
                Call 25%

            Aggregate Call:
                (2 * 1.00 + 1 * 0.25) / 3
                = 0.75
        """
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

    def strategy_summary(
        self,
    ) -> RangeStrategySummary:
        return build_range_strategy_summary(
            self
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


def build_range_strategy_summary(
    snapshot: RangeSnapshot,
) -> RangeStrategySummary:
    """
    Aggregate every action across the
    private-hand entries in one range
    snapshot.
    """
    action_frequencies = tuple(
        RangeActionFrequency(
            action=action,
            probability=(
                snapshot
                .aggregate_action_frequency(
                    action
                )
            ),
        )
        for action in snapshot.actions
    )

    return RangeStrategySummary(
        public_node=(
            snapshot.public_node
        ),
        acting_seat=(
            snapshot.acting_seat
        ),
        total_weight=(
            snapshot.total_weight
        ),
        hand_count=(
            snapshot.hand_count
        ),
        actions=action_frequencies,
    )