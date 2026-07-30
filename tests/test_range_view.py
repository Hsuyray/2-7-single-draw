from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.information_state import (
    InformationState,
)
from solver.legal_actions import (
    BettingAction,
)
from solver.range_tracker import (
    RangeTracker,
)
from solver.range_view import (
    RangeEntry,
    RangeSnapshot,
    build_range_snapshot,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_index import (
    StrategyIndex,
)


def make_state(
    *,
    seed: int,
) -> InformationState:
    game = SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=100.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=seed,
    )

    return InformationState.from_game(
        game,
        observer_seat=0,
        abstraction="exact",
    )


def test_range_entry_is_hashable_container() -> None:
    state = make_state(
        seed=1
    )

    call = BettingAction(
        ActionType.CALL
    )

    entry = RangeEntry(
        hand_key=state.own_hand_key,
        weight=1.0,
        strategy={
            call: 1.0,
        },
    )

    assert (
        entry.hand_key
        == state.own_hand_key
    )

    assert entry.weight == 1.0


def test_build_range_snapshot_contains_hands() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    assert (
        first.public_node
        == second.public_node
    )

    call = BettingAction(
        ActionType.CALL
    )

    fold = BettingAction(
        ActionType.FOLD
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {
                    call: 0.8,
                    fold: 0.2,
                },
                second: {
                    call: 0.3,
                    fold: 0.7,
                },
            }
        )
    )

    tracker = RangeTracker()

    tracker.initialize_player(
        seat=0,
        hand_keys=(
            first.own_hand_key,
            second.own_hand_key,
        ),
    )

    snapshot = build_range_snapshot(
        public_node=first.public_node,
        acting_seat=0,
        strategy_index=index,
        range_tracker=tracker,
    )

    assert isinstance(
        snapshot,
        RangeSnapshot,
    )

    assert (
        snapshot.hand_count
        == 2
    )


def test_range_snapshot_tracks_weights() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {},
                second: {},
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 0.8,
        second.own_hand_key: 0.2,
    }

    snapshot = build_range_snapshot(
        public_node=first.public_node,
        acting_seat=0,
        strategy_index=index,
        range_tracker=tracker,
    )

    first_entry = (
        snapshot.entry_for_hand(
            first.own_hand_key
        )
    )

    second_entry = (
        snapshot.entry_for_hand(
            second.own_hand_key
        )
    )

    assert first_entry is not None
    assert second_entry is not None

    assert (
        first_entry.weight
        == 0.8
    )

    assert (
        second_entry.weight
        == 0.2
    )


def test_total_weight() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {},
                second: {},
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 4.0,
        second.own_hand_key: 1.0,
    }

    snapshot = build_range_snapshot(
        public_node=first.public_node,
        acting_seat=0,
        strategy_index=index,
        range_tracker=tracker,
    )

    assert (
        snapshot.total_weight
        == 5.0
    )


def test_aggregate_action_frequency_is_weighted() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    call = BettingAction(
        ActionType.CALL
    )

    fold = BettingAction(
        ActionType.FOLD
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {
                    call: 1.0,
                    fold: 0.0,
                },
                second: {
                    call: 0.0,
                    fold: 1.0,
                },
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 0.8,
        second.own_hand_key: 0.2,
    }

    snapshot = build_range_snapshot(
        public_node=first.public_node,
        acting_seat=0,
        strategy_index=index,
        range_tracker=tracker,
    )

    result = (
        snapshot.aggregate_action_frequency(
            call
        )
    )

    assert abs(
        result - 0.8
    ) < 1e-9


def test_unknown_hand_returns_none() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {},
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 1.0,
    }

    snapshot = build_range_snapshot(
        public_node=first.public_node,
        acting_seat=0,
        strategy_index=index,
        range_tracker=tracker,
    )

    assert (
        snapshot.entry_for_hand(
            second.own_hand_key
        )
        is None
    )