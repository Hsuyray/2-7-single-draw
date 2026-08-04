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
    Query layer over information-state action
    weights.

    Most solved CFR strategies are normalized
    probability distributions.

    Some range-conditioning and view tests use
    partial action weights or empty strategies.
    StrategyIndex therefore validates only
    structural correctness and non-negative
    numeric weights.

    Strict normalized-probability validation
    belongs at checkpoint boundaries.
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
        self._validate_strategies()
        self._rebuild_index()

    def __len__(self) -> int:
        return len(
            self._strategies
        )

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
            copied_strategies[
                state
            ] = dict(
                strategy
            )

        return cls(
            _strategies=(
                copied_strategies
            )
        )

    def strategies(
        self,
    ) -> dict[
        InformationState,
        Strategy,
    ]:
        """
        Return a defensive copy of all stored
        information-state action weights.
        """
        return {
            state: dict(
                strategy
            )
            for state, strategy
            in self._strategies.items()
        }

    def strategy_for_state(
        self,
        state: InformationState,
    ) -> Strategy | None:
        strategy = self._strategies.get(
            state
        )

        if strategy is None:
            return None

        return dict(
            strategy
        )

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

        return dict(
            strategy
        )

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
            hand_key: dict(
                strategy
            )
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
        ...,
    ]:
        nodes = {
            public_node
            for (
                public_node,
                _observer_seat,
            )
            in self._by_public_node
        }

        return tuple(
            nodes
        )

    def _validate_strategies(
        self,
    ) -> None:
        """
        Validate storage structure.

        Empty strategies and partial action
        weights are allowed.

        Every stored value must still be a
        finite, non-negative number.
        """
        for (
            information_state,
            strategy,
        ) in self._strategies.items():
            if not isinstance(
                information_state,
                InformationState,
            ):
                raise TypeError(
                    "Strategy keys must be "
                    "InformationState objects."
                )

            if not isinstance(
                strategy,
                dict,
            ):
                raise TypeError(
                    "Stored strategies must "
                    "be dictionaries."
                )

            for (
                _action,
                weight,
            ) in strategy.items():
                if not isinstance(
                    weight,
                    (
                        int,
                        float,
                    ),
                ):
                    raise TypeError(
                        "Strategy weights must "
                        "be numeric."
                    )

                if weight < 0:
                    raise ValueError(
                        "Strategy weights cannot "
                        "be negative."
                    )

                if weight != weight:
                    raise ValueError(
                        "Strategy weights cannot "
                        "be NaN."
                    )

                if weight in {
                    float("inf"),
                    float("-inf"),
                }:
                    raise ValueError(
                        "Strategy weights must "
                        "be finite."
                    )

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
            ] = dict(
                strategy
            )