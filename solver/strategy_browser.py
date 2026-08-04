from dataclasses import dataclass

from solver.actions import (
    DiscardAction,
)
from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.draw_transition_policy import (
    DrawTransitionConfig,
    transition_draw_range,
)
from solver.exact_hand_codec import (
    actual_discard_action_for_hand,
)
from solver.game_state import (
    ActionType,
)
from solver.hand import (
    Hand,
)
from solver.hand_abstraction import (
    ExactHandKey,
)
from solver.hand_strategy_resolver import (
    HandStrategyResolver,
)
from solver.information_state import (
    AbstractionMode,
    PrivateHandKey,
)
from solver.legal_actions import (
    BettingAction,
    DrawActionMode,
    SolverAction,
)
from solver.public_legal_actions import (
    PublicBettingAction,
    PublicDrawAction,
    PublicLegalActionSnapshot,
    PublicSolverAction,
    public_legal_actions,
)
from solver.public_node_navigator import (
    PublicNodeNavigator,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.range_tracker import (
    RangeTracker,
)
from solver.range_view import (
    RangeSnapshot,
    build_range_snapshot,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)
from solver.strategy_index import (
    Strategy,
    StrategyIndex,
)


@dataclass(frozen=True)
class StrategyActionView:
    """
    One public action and its solved
    probability for one private hand.
    """

    action: PublicSolverAction
    probability: float

    def __post_init__(self) -> None:
        if not (
            0.0
            <= self.probability
            <= 1.0
        ):
            raise ValueError(
                "Strategy probability must "
                "be between zero and one."
            )

    @property
    def percentage(self) -> float:
        return (
            self.probability
            * 100.0
        )

    @property
    def label(self) -> str:
        return self.action.label


@dataclass(frozen=True)
class HandStrategySnapshot:
    """
    Public-facing strategy for one private
    hand at one public node.
    """

    public_node: PublicNodeKey
    acting_seat: int
    hand_key: PrivateHandKey
    actions: tuple[
        StrategyActionView,
        ...,
    ]

    @property
    def total_probability(
        self,
    ) -> float:
        return sum(
            action.probability
            for action in self.actions
        )


@dataclass(frozen=True)
class RangeActionView:
    """
    One public action and its aggregate
    probability across the current range.
    """

    action: PublicSolverAction
    probability: float

    def __post_init__(self) -> None:
        if not (
            0.0
            <= self.probability
            <= 1.0
        ):
            raise ValueError(
                "Range action probability "
                "must be between zero and one."
            )

    @property
    def percentage(self) -> float:
        return (
            self.probability
            * 100.0
        )

    @property
    def label(self) -> str:
        return self.action.label


@dataclass(frozen=True)
class RangeStrategySnapshot:
    """
    Public-facing aggregate strategy for
    the currently acting player's range.
    """

    public_node: PublicNodeKey
    acting_seat: int
    total_weight: float
    hand_count: int
    actions: tuple[
        RangeActionView,
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
                "Range hand count cannot "
                "be negative."
            )

    @property
    def total_probability(
        self,
    ) -> float:
        return sum(
            action.probability
            for action in self.actions
        )

    @property
    def action_count(self) -> int:
        return len(
            self.actions
        )


@dataclass
class StrategyBrowser:
    """
    Browse solved strategies through the
    public game tree.

    Supports:

    - Hand Mode
    - Range Mode
    - Public legal actions
    - Safe public action application
    - Betting range conditioning
    - Exact and sampled draw transitions
    - Canonical discard-index translation
    """

    navigator: PublicNodeNavigator
    strategy_index: StrategyIndex
    abstraction: AbstractionMode = "exact"
    range_tracker: RangeTracker | None = None

    max_draw: int = 3

    # None:
    #     use BetSizingPolicy
    #
    # ():
    #     disable raises
    #
    # non-empty tuple:
    #     explicit absolute raise-to sizes
    raise_sizes: (
        tuple[float, ...]
        | None
    ) = None

    bet_sizing_policy: (
        BetSizingPolicy
        | None
    ) = None

    draw_action_mode: (
        DrawActionMode
    ) = "full"

    draw_transition_config: (
        DrawTransitionConfig
    ) = DrawTransitionConfig()

    @property
    def phase(self) -> GamePhase:
        return self.navigator.phase

    @property
    def acting_seat(
        self,
    ) -> int | None:
        return self.navigator.acting_seat

    @property
    def is_terminal(self) -> bool:
        return self.navigator.is_terminal

    @property
    def public_node(
        self,
    ) -> PublicNodeKey:
        return self.navigator.public_node()

    @property
    def game(
        self,
    ) -> SingleDrawGame:
        return self.navigator.game

    def current_legal_actions(
        self,
    ) -> PublicLegalActionSnapshot | None:
        return public_legal_actions(
            self.game,
            max_draw=self.max_draw,
            raise_sizes=self.raise_sizes,
            bet_sizing_policy=(
                self.bet_sizing_policy
            ),
            draw_action_mode=(
                self.draw_action_mode
            ),
        )

    def current_range_strategy(
        self,
    ) -> dict[
        PrivateHandKey,
        Strategy,
    ]:
        acting_seat = self.acting_seat

        if acting_seat is None:
            return {}

        return (
            self.strategy_index.range_strategy(
                public_node=self.public_node,
                observer_seat=acting_seat,
            )
        )

    def current_hand_strategy(
        self,
        hand_key: PrivateHandKey,
    ) -> Strategy | None:
        acting_seat = self.acting_seat

        if acting_seat is None:
            return None

        return (
            self.strategy_index
            .strategy_for_hand(
                public_node=self.public_node,
                observer_seat=acting_seat,
                hand_key=hand_key,
            )
        )

    def current_strategy_for_hand(
        self,
        hand: Hand,
    ) -> Strategy | None:
        resolver = HandStrategyResolver(
            abstraction=self.abstraction,
        )

        hand_key = resolver.resolve(
            hand=hand,
            phase=self.phase,
        )

        return self.current_hand_strategy(
            hand_key
        )

    def current_hand_action_snapshot(
        self,
        hand_key: PrivateHandKey,
    ) -> HandStrategySnapshot | None:
        """
        Aggregate private solver actions into
        public UI actions.

        Betting actions map one-to-one.

        Private discard patterns with the same
        draw count map to one PublicDrawAction.
        """
        acting_seat = self.acting_seat

        if acting_seat is None:
            return None

        strategy = (
            self.current_hand_strategy(
                hand_key
            )
        )

        if strategy is None:
            return None

        legal_snapshot = (
            self.current_legal_actions()
        )

        if legal_snapshot is None:
            return None

        covered_actions: set[
            SolverAction
        ] = set()

        views: list[
            StrategyActionView
        ] = []

        for public_action in (
            legal_snapshot.actions
        ):
            matching_actions = (
                _private_actions_for_public_action(
                    public_action,
                    private_actions=tuple(
                        strategy
                    ),
                )
            )

            if not matching_actions:
                raise RuntimeError(
                    "Current legal actions do "
                    "not match the actions in "
                    "the solved strategy. "
                    "Check the browser betting "
                    "and draw configuration."
                )

            covered_actions.update(
                matching_actions
            )

            probability = sum(
                strategy.get(
                    private_action,
                    0.0,
                )
                for private_action
                in matching_actions
            )

            views.append(
                StrategyActionView(
                    action=public_action,
                    probability=probability,
                )
            )

        if (
            set(strategy)
            != covered_actions
        ):
            raise RuntimeError(
                "Solved strategy contains "
                "actions that are not legal "
                "under the browser's current "
                "configuration."
            )

        return HandStrategySnapshot(
            public_node=self.public_node,
            acting_seat=acting_seat,
            hand_key=hand_key,
            actions=tuple(
                views
            ),
        )

    def current_action_snapshot_for_hand(
        self,
        hand: Hand,
    ) -> HandStrategySnapshot | None:
        resolver = HandStrategyResolver(
            abstraction=self.abstraction,
        )

        hand_key = resolver.resolve(
            hand=hand,
            phase=self.phase,
        )

        return (
            self.current_hand_action_snapshot(
                hand_key
            )
        )

    def current_range_snapshot(
        self,
    ) -> RangeSnapshot | None:
        acting_seat = self.acting_seat

        if (
            acting_seat is None
            or self.range_tracker is None
        ):
            return None

        return build_range_snapshot(
            public_node=self.public_node,
            acting_seat=acting_seat,
            strategy_index=(
                self.strategy_index
            ),
            range_tracker=(
                self.range_tracker
            ),
        )

    def current_range_action_summary(
        self,
    ) -> RangeStrategySnapshot | None:
        """
        Aggregate private solver actions into
        public frequencies across the range.

        Multiple private discard patterns with
        the same draw count are combined.
        """
        range_snapshot = (
            self.current_range_snapshot()
        )

        if range_snapshot is None:
            return None

        legal_snapshot = (
            self.current_legal_actions()
        )

        if legal_snapshot is None:
            return None

        range_summary = (
            range_snapshot.strategy_summary()
        )

        private_actions = tuple(
            frequency.action
            for frequency
            in range_summary.actions
        )

        covered_actions: set[
            SolverAction
        ] = set()

        views: list[
            RangeActionView
        ] = []

        for public_action in (
            legal_snapshot.actions
        ):
            matching_actions = (
                _private_actions_for_public_action(
                    public_action,
                    private_actions=(
                        private_actions
                    ),
                )
            )

            if not matching_actions:
                raise RuntimeError(
                    "Current legal actions do "
                    "not match the actions in "
                    "the solved range strategy. "
                    "Check the browser betting "
                    "and draw configuration."
                )

            covered_actions.update(
                matching_actions
            )

            probability = sum(
                range_summary
                .frequency_for_action(
                    private_action
                )
                for private_action
                in matching_actions
            )

            views.append(
                RangeActionView(
                    action=public_action,
                    probability=probability,
                )
            )

        if (
            set(private_actions)
            != covered_actions
        ):
            raise RuntimeError(
                "Solved range strategy "
                "contains actions that are "
                "not legal under the browser's "
                "current configuration."
            )

        return RangeStrategySnapshot(
            public_node=self.public_node,
            acting_seat=(
                range_snapshot.acting_seat
            ),
            total_weight=(
                range_snapshot.total_weight
            ),
            hand_count=(
                range_snapshot.hand_count
            ),
            actions=tuple(
                views
            ),
        )

    def apply_public_action(
        self,
        action: PublicSolverAction,
        *,
        discard_indices: (
            tuple[int, ...]
            | None
        ) = None,
    ) -> PublicNodeKey:
        """
        Apply one currently legal public
        action.

        Betting actions condition the acting
        player's existing range.

        Public draw actions receive canonical
        private discard indices. Before the
        physical game draw is executed, those
        canonical indices are translated into
        the current Hand.cards ordering.
        """
        legal_snapshot = (
            self.current_legal_actions()
        )

        if legal_snapshot is None:
            raise RuntimeError(
                "No action can be applied "
                "at a terminal node."
            )

        if (
            action
            not in legal_snapshot.actions
        ):
            raise ValueError(
                "The selected action is not "
                "legal at the current node."
            )

        acting_seat = self.acting_seat

        if acting_seat is None:
            raise RuntimeError(
                "Current node has no "
                "acting player."
            )

        if isinstance(
            action,
            PublicBettingAction,
        ):
            if discard_indices is not None:
                raise ValueError(
                    "Betting actions cannot "
                    "include discard indices."
                )

            updated_range = (
                self._conditioned_betting_range(
                    acting_seat=acting_seat,
                    action=action,
                )
            )

            next_node = self.apply_betting(
                action.action_type,
                raise_to=action.raise_to,
            )

            if (
                updated_range is not None
                and self.range_tracker
                is not None
            ):
                self.range_tracker.set_range(
                    seat=acting_seat,
                    weights=updated_range,
                )

            return next_node

        if discard_indices is None:
            raise ValueError(
                "Public draw actions require "
                "private discard_indices for "
                "execution."
            )

        canonical_action = DiscardAction(
            discard_indices
        )

        if (
            canonical_action.draw_count
            != action.draw_count
        ):
            raise ValueError(
                "Private discard count does "
                "not match the selected public "
                "draw action."
            )

        hand = self.game.hands[
            acting_seat
        ]

        if hand is None:
            raise RuntimeError(
                "Acting player does not "
                "have a hand."
            )

        actual_action = (
            actual_discard_action_for_hand(
                hand=hand,
                action=canonical_action,
            )
        )

        updated_range = (
            self._conditioned_draw_range(
                acting_seat=acting_seat,
                action=action,
            )
        )

        next_node = self.apply_draw(
            discard_indices=(
                actual_action
                .discard_indices
            ),
        )

        if (
            updated_range is not None
            and self.range_tracker
            is not None
        ):
            self.range_tracker.set_range(
                seat=acting_seat,
                weights=updated_range,
            )

        return next_node

    def _conditioned_betting_range(
        self,
        *,
        acting_seat: int,
        action: PublicBettingAction,
    ) -> (
        dict[PrivateHandKey, float]
        | None
    ):
        if (
            self.range_tracker is None
            or not self.range_tracker
            .has_player(
                acting_seat
            )
        ):
            return None

        solver_action = (
            _betting_solver_action(
                action
            )
        )

        return (
            self.range_tracker
            .conditioned_range(
                public_node=(
                    self.public_node
                ),
                acting_seat=(
                    acting_seat
                ),
                action=solver_action,
                strategy_index=(
                    self.strategy_index
                ),
                normalize=True,
            )
        )

    def _conditioned_draw_range(
        self,
        *,
        acting_seat: int,
        action: PublicDrawAction,
    ) -> (
        dict[PrivateHandKey, float]
        | None
    ):
        """
        Transition one initialized exact-hand
        range through a public draw action.

        All private discard patterns matching
        the selected draw count are included.
        """
        if (
            self.range_tracker is None
            or not self.range_tracker
            .has_player(
                acting_seat
            )
        ):
            return None

        current_range = (
            self.range_tracker
            .range_for_seat(
                acting_seat
            )
        )

        exact_weights: dict[
            ExactHandKey,
            float,
        ] = {}

        for (
            hand_key,
            weight,
        ) in current_range.items():
            if not isinstance(
                hand_key,
                ExactHandKey,
            ):
                raise NotImplementedError(
                    "Draw range transition "
                    "currently supports only "
                    "exact hand abstraction."
                )

            exact_weights[
                hand_key
            ] = weight

        strategies = (
            self.strategy_index
            .range_strategy(
                public_node=(
                    self.public_node
                ),
                observer_seat=(
                    acting_seat
                ),
            )
        )

        transition_result = (
            transition_draw_range(
                pre_draw_weights=(
                    exact_weights
                ),
                strategies=strategies,
                public_draw_count=(
                    action.draw_count
                ),
                config=(
                    self.draw_transition_config
                ),
                normalize=True,
            )
        )

        return dict(
            transition_result.weights
        )

    def apply_betting(
        self,
        action_type: ActionType,
        *,
        raise_to: float | None = None,
    ) -> PublicNodeKey:
        return self.navigator.apply_betting(
            action_type,
            raise_to=raise_to,
        )

    def apply_draw(
        self,
        *,
        discard_indices: tuple[int, ...],
    ) -> PublicNodeKey:
        return self.navigator.apply_draw(
            discard_indices=(
                discard_indices
            ),
        )

    def strategy_for_action(
        self,
        hand_key: PrivateHandKey,
    ) -> Strategy | None:
        return self.current_hand_strategy(
            hand_key
        )


def _private_actions_for_public_action(
    public_action: PublicSolverAction,
    *,
    private_actions: tuple[
        SolverAction,
        ...,
    ],
) -> tuple[
    SolverAction,
    ...,
]:
    """
    Return all private solver actions
    represented by one public action.
    """
    if isinstance(
        public_action,
        PublicBettingAction,
    ):
        target = (
            _betting_solver_action(
                public_action
            )
        )

        return tuple(
            action
            for action in private_actions
            if action == target
        )

    return tuple(
        action
        for action in private_actions
        if (
            isinstance(
                action,
                DiscardAction,
            )
            and action.draw_count
            == public_action.draw_count
        )
    )


def _betting_solver_action(
    action: PublicBettingAction,
) -> BettingAction:
    return BettingAction(
        action_type=action.action_type,
        raise_to=action.raise_to,
    )