from dataclasses import dataclass

from solver.game_state import ActionType
from solver.hand import Hand
from solver.hand_strategy_resolver import (
    HandStrategyResolver,
)
from solver.information_state import (
    AbstractionMode,
    PrivateHandKey,
)
from solver.public_node_navigator import (
    PublicNodeNavigator,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.single_draw_game import (
    GamePhase,
)
from solver.strategy_index import (
    Strategy,
    StrategyIndex,
)
from solver.range_tracker import (
    RangeTracker,
)
from solver.range_view import (
    RangeSnapshot,
    build_range_snapshot,
)


@dataclass
class StrategyBrowser:
    """
    Browse solved strategies through the game tree.

    The browser combines:

    - PublicNodeNavigator:
        handles game-state transitions

    - StrategyIndex:
        handles strategy lookup

    It supports:

    - Range Mode:
        return all private-hand strategies
        at the current public node.

    - Hand Mode:
        return the strategy for one
        private hand.

    Future UI flow:

        display strategy
        -> user chooses action
        -> apply action
        -> display next strategy
    """

    navigator: PublicNodeNavigator
    strategy_index: StrategyIndex
    abstraction: AbstractionMode = "exact"
    range_tracker: RangeTracker | None = None

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

    def current_range_strategy(
        self,
    ) -> dict[
        PrivateHandKey,
        Strategy,
    ]:
        """
        Return all private-hand strategies
        for the player currently acting.

        This is the backend for Range Mode.
        """
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
        """
        Return the strategy for one
        private-hand key belonging to
        the player currently acting.
        """
        acting_seat = self.acting_seat

        if acting_seat is None:
            return None

        return (
            self.strategy_index.strategy_for_hand(
                public_node=self.public_node,
                observer_seat=acting_seat,
                hand_key=hand_key,
            )
        )

    def current_strategy_for_hand(
        self,
        hand: Hand,
    ) -> Strategy | None:
        """
        Return the current strategy for
        an exact five-card hand.

        The browser automatically converts
        the exact hand into the correct
        private-hand representation based on:

        - current game phase
        - configured abstraction mode

        This is the main UI-facing method
        for Hand Mode.
        """
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

    def apply_betting(
        self,
        action_type: ActionType,
        *,
        raise_to: float | None = None,
    ) -> PublicNodeKey:
        """
        Apply a betting action and move
        the browser to the next public node.
        """
        return self.navigator.apply_betting(
            action_type,
            raise_to=raise_to,
        )

    def apply_draw(
        self,
        *,
        discard_indices: tuple[int, ...],
    ) -> PublicNodeKey:
        """
        Apply the current player's draw
        action and move to the next
        public node.
        """
        return self.navigator.apply_draw(
            discard_indices=discard_indices,
        )

    def strategy_for_action(
        self,
        hand_key: PrivateHandKey,
    ) -> Strategy | None:
        """
        Compatibility alias for
        current_hand_strategy().
        """
        return self.current_hand_strategy(
            hand_key
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
            strategy_index=self.strategy_index,
            range_tracker=self.range_tracker,
        )