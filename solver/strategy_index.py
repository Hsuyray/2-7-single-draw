from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

from solver.information_state import (
    InformationState,
    PrivateHandKey,
)
from solver.legal_actions import (
    SolverAction,
)
from solver.public_state import (
    PublicNodeKey,
)


Strategy: TypeAlias = dict[
    SolverAction,
    float,
]


@dataclass
class StrategyIndex:
    """
    Query layer over solved information-state strategies.

    It supports two main product use cases:

    Hand mode:
        public node + private hand -> strategy

    Range mode:
        public node -> all private-hand strategies
        for the acting player.
    """

    _strategies: dict[
        InformationState,
        Strategy,
    ] = field(
        default_factory=dict,
        repr=False,
    )

    _by_public_node: dict[
        tuple[
            PublicNodeKey,
            int,
        ],
        dict[
            PrivateHandKey,
            Strategy,
        ],
    ] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._rebuild_index()

    @classmethod
    def from_strategies(
        cls,
        strategies: Mapping[
            InformationState,
            Mapping[
                SolverAction,
                float,
            ],
        ],
    ) -> "StrategyIndex":
        copied_strategies: dict[
            InformationState,
            Strategy,
        ] = {}

        for state, strategy in (
            strategies.items()
        ):
            copied_strategies[state] = dict(
                strategy
            )

        return cls(
            _strategies=(
                copied_strategies
            )
        )

    def strategy_for_state(
        self,
        state: InformationState,
    ) -> Strategy | None:
        strategy = self._strategies.get(
            state
        )

        if strategy is None:
            return None

        return dict(strategy)

    def strategy_for_hand(
        self,
        *,
        public_node: PublicNodeKey,
        observer_seat: int,
        hand_key: PrivateHandKey,
    ) -> Strategy | None:
        range_strategy = (
            self._by_public_node.get(
                (
                    public_node,
                    observer_seat,
                )
            )
        )

        if range_strategy is None:
            return None

        strategy = range_strategy.get(
            hand_key
        )

        if strategy is None:
            return None

        return dict(strategy)

    def range_strategy(
        self,
        *,
        public_node: PublicNodeKey,
        observer_seat: int,
    ) -> dict[
        PrivateHandKey,
        Strategy,
    ]:
        strategies = (
            self._by_public_node.get(
                (
                    public_node,
                    observer_seat,
                ),
                {},
            )
        )

        return {
            hand_key: dict(strategy)
            for hand_key, strategy
            in strategies.items()
        }

    def hand_count(
        self,
        *,
        public_node: PublicNodeKey,
        observer_seat: int,
    ) -> int:
        return len(
            self._by_public_node.get(
                (
                    public_node,
                    observer_seat,
                ),
                {},
            )
        )

    def public_nodes(
        self,
    ) -> tuple[
        PublicNodeKey,
        ...
    ]:
        nodes = {
            public_node
            for (
                public_node,
                _observer_seat,
            )
            in self._by_public_node
        }

        return tuple(nodes)

    def _rebuild_index(self) -> None:
        self._by_public_node = {}

        for state, strategy in (
            self._strategies.items()
        ):
            key = (
                state.public_node,
                state.observer_seat,
            )

            range_strategy = (
                self._by_public_node.setdefault(
                    key,
                    {},
                )
            )

            existing = (
                range_strategy.get(
                    state.own_hand_key
                )
            )

            if (
                existing is not None
                and existing != strategy
            ):
                raise ValueError(
                    "Conflicting strategies "
                    "exist for the same "
                    "public node, observer, "
                    "and private hand."
                )

            range_strategy[
                state.own_hand_key
            ] = dict(strategy)