from dataclasses import dataclass

from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.game_state import ActionType
from solver.hand import Hand
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
    One UI-facing action and its solved
    strategy probability for one hand.
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
        return _public_action_label(
            self.action
        )


@dataclass(frozen=True)
class HandStrategySnapshot:
    """
    Complete UI-facing strategy result for
    one private hand at one public node.
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
    One UI-facing action and its aggregate
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
        return _public_action_label(
            self.action
        )


@dataclass(frozen=True)
class RangeStrategySnapshot:
    """
    UI-facing aggregate strategy for the
    currently acting player's entire range.
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
            self.navigator.game,
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
        Combine one hand's solved strategy
        with current UI-facing legal actions.
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

        views: list[
            StrategyActionView
        ] = []

        legal_solver_actions: set[
            SolverAction
        ] = set()

        for public_action in (
            legal_snapshot.actions
        ):
            solver_action = (
                _public_to_solver_action(
                    public_action
                )
            )

            legal_solver_actions.add(
                solver_action
            )

            if solver_action not in strategy:
                raise RuntimeError(
                    "Current legal actions do "
                    "not match the actions in "
                    "the solved strategy. "
                    "Check the browser betting "
                    "and draw configuration."
                )

            views.append(
                StrategyActionView(
                    action=public_action,
                    probability=(
                        strategy[
                            solver_action
                        ]
                    ),
                )
            )

        if (
            set(strategy)
            != legal_solver_actions
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
        Return aggregate UI-facing action
        frequencies across the entire current
        range.

        Example:

            Fold       18%
            Call       42%
            33% Pot    17%
            66% Pot    14%
            All-in      9%
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

        range_solver_actions = {
            frequency.action
            for frequency
            in range_summary.actions
        }

        legal_solver_actions: set[
            SolverAction
        ] = set()

        views: list[
            RangeActionView
        ] = []

        for public_action in (
            legal_snapshot.actions
        ):
            solver_action = (
                _public_to_solver_action(
                    public_action
                )
            )

            legal_solver_actions.add(
                solver_action
            )

            if (
                solver_action
                not in range_solver_actions
            ):
                raise RuntimeError(
                    "Current legal actions do "
                    "not match the actions in "
                    "the solved range strategy. "
                    "Check the browser betting "
                    "and draw configuration."
                )

            probability = (
                range_summary
                .frequency_for_action(
                    solver_action
                )
            )

            views.append(
                RangeActionView(
                    action=public_action,
                    probability=probability,
                )
            )

        if (
            range_solver_actions
            != legal_solver_actions
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
    ) -> PublicNodeKey:
        """
        Apply one currently legal UI-facing
        action.

        Betting actions also condition the
        acting player's tracked range.

        Draw actions currently advance the
        game only. Exact draw-range transition
        requires separate card-removal and
        replacement-card modeling.
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

        solver_action = (
            _public_to_solver_action(
                action
            )
        )

        updated_range: (
            dict[PrivateHandKey, float]
            | None
        ) = None

        if (
            isinstance(
                action,
                PublicBettingAction,
            )
            and self.range_tracker
            is not None
            and self.range_tracker.has_player(
                acting_seat
            )
        ):
            updated_range = (
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

        if isinstance(
            action,
            PublicBettingAction,
        ):
            next_node = self.apply_betting(
                action.action_type,
                raise_to=action.raise_to,
            )
        else:
            next_node = self.apply_draw(
                discard_indices=(
                    action.discard_indices
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


def _public_to_solver_action(
    action: PublicSolverAction,
) -> SolverAction:
    if not isinstance(
        action,
        PublicBettingAction,
    ):
        return action

    return BettingAction(
        action_type=action.action_type,
        raise_to=action.raise_to,
    )


def _public_action_label(
    action: PublicSolverAction,
) -> str:
    if isinstance(
        action,
        PublicBettingAction,
    ):
        return action.label

    draw_count = len(
        action.discard_indices
    )

    if draw_count == 0:
        return "Stand Pat"

    if draw_count == 1:
        return "Draw 1"

    return f"Draw {draw_count}"