import pytest

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
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.starting_range import (
    StartingRange,
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


def test_initialize_player_range() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    tracker = RangeTracker()

    tracker.initialize_player(
        seat=0,
        hand_keys=(
            first.own_hand_key,
            second.own_hand_key,
        ),
    )

    result = tracker.range_for_seat(
        0
    )

    assert len(result) == 2

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(1.0)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(1.0)
    )


def test_initialize_player_rejects_negative_weight() -> None:
    state = make_state(
        seed=1
    )

    tracker = RangeTracker()

    with pytest.raises(
        ValueError
    ):
        tracker.initialize_player(
            seat=0,
            hand_keys=(
                state.own_hand_key,
            ),
            initial_weight=-1.0,
        )


def test_has_player() -> None:
    state = make_state(
        seed=1
    )

    tracker = RangeTracker()

    assert (
        tracker.has_player(0)
        is False
    )

    tracker.initialize_player(
        seat=0,
        hand_keys=(
            state.own_hand_key,
        ),
    )

    assert (
        tracker.has_player(0)
        is True
    )


def test_range_for_unknown_seat_is_empty() -> None:
    tracker = RangeTracker()

    assert (
        tracker.range_for_seat(0)
        == {}
    )


def test_range_for_seat_returns_copy() -> None:
    state = make_state(
        seed=1
    )

    tracker = RangeTracker()

    tracker.initialize_player(
        seat=0,
        hand_keys=(
            state.own_hand_key,
        ),
    )

    copied_range = (
        tracker.range_for_seat(0)
    )

    copied_range[
        state.own_hand_key
    ] = 99.0

    assert (
        tracker.weight_for_hand(
            seat=0,
            hand_key=(
                state.own_hand_key
            ),
        )
        == pytest.approx(1.0)
    )


def test_weight_for_unknown_hand_is_zero() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    tracker = RangeTracker()

    tracker.initialize_player(
        seat=0,
        hand_keys=(
            first.own_hand_key,
        ),
    )

    assert (
        tracker.weight_for_hand(
            seat=0,
            hand_key=(
                second.own_hand_key
            ),
        )
        == 0.0
    )


def test_apply_action_filters_range_by_strategy_probability() -> None:
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

    tracker.apply_action(
        public_node=(
            first.public_node
        ),
        acting_seat=0,
        action=call,
        strategy_index=index,
    )

    result = tracker.range_for_seat(
        0
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(0.8)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(0.3)
    )


def test_apply_action_can_keep_zero_probability_hand() -> None:
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

    tracker.initialize_player(
        seat=0,
        hand_keys=(
            first.own_hand_key,
            second.own_hand_key,
        ),
    )

    tracker.apply_action(
        public_node=(
            first.public_node
        ),
        acting_seat=0,
        action=call,
        strategy_index=index,
    )

    result = tracker.range_for_seat(
        0
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(1.0)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(0.0)
    )


def test_apply_action_rejects_uninitialized_player() -> None:
    state = make_state(
        seed=1
    )

    call = BettingAction(
        ActionType.CALL
    )

    index = (
        StrategyIndex.from_strategies(
            {
                state: {
                    call: 1.0,
                },
            }
        )
    )

    tracker = RangeTracker()

    with pytest.raises(
        ValueError
    ):
        tracker.apply_action(
            public_node=(
                state.public_node
            ),
            acting_seat=0,
            action=call,
            strategy_index=index,
        )


def test_conditioned_range_does_not_mutate_tracker() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    call = BettingAction(
        ActionType.CALL
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {
                    call: 1.0,
                },
                second: {
                    call: 0.25,
                },
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 0.6,
        second.own_hand_key: 0.4,
    }

    result = tracker.conditioned_range(
        public_node=first.public_node,
        acting_seat=0,
        action=call,
        strategy_index=index,
        normalize=False,
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(0.6)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(0.1)
    )

    assert tracker.weights[0] == {
        first.own_hand_key: 0.6,
        second.own_hand_key: 0.4,
    }


def test_conditioned_range_can_normalize() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    call = BettingAction(
        ActionType.CALL
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {
                    call: 1.0,
                },
                second: {
                    call: 0.25,
                },
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 0.6,
        second.own_hand_key: 0.4,
    }

    result = tracker.conditioned_range(
        public_node=first.public_node,
        acting_seat=0,
        action=call,
        strategy_index=index,
        normalize=True,
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(6 / 7)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(1 / 7)
    )

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )


def test_conditioned_range_rejects_uninitialized_player() -> None:
    state = make_state(
        seed=1
    )

    call = BettingAction(
        ActionType.CALL
    )

    index = (
        StrategyIndex.from_strategies(
            {
                state: {
                    call: 1.0,
                },
            }
        )
    )

    tracker = RangeTracker()

    with pytest.raises(
        ValueError
    ):
        tracker.conditioned_range(
            public_node=(
                state.public_node
            ),
            acting_seat=0,
            action=call,
            strategy_index=index,
        )


def test_conditioned_range_skips_hand_without_strategy() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    call = BettingAction(
        ActionType.CALL
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {
                    call: 1.0,
                },
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 0.5,
        second.own_hand_key: 0.5,
    }

    result = tracker.conditioned_range(
        public_node=first.public_node,
        acting_seat=0,
        action=call,
        strategy_index=index,
    )

    assert result == {
        first.own_hand_key: 0.5,
    }


def test_apply_action_can_normalize() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    call = BettingAction(
        ActionType.CALL
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first: {
                    call: 1.0,
                },
                second: {
                    call: 0.25,
                },
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 0.6,
        second.own_hand_key: 0.4,
    }

    tracker.apply_action(
        public_node=first.public_node,
        acting_seat=0,
        action=call,
        strategy_index=index,
        normalize=True,
    )

    result = tracker.range_for_seat(
        0
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(6 / 7)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(1 / 7)
    )


def test_set_range_copies_weights() -> None:
    state = make_state(
        seed=1
    )

    source = {
        state.own_hand_key: 1.0,
    }

    tracker = RangeTracker()

    tracker.set_range(
        seat=0,
        weights=source,
    )

    source[
        state.own_hand_key
    ] = 99.0

    assert (
        tracker.weight_for_hand(
            seat=0,
            hand_key=(
                state.own_hand_key
            ),
        )
        == pytest.approx(1.0)
    )


def test_set_range_rejects_negative_weights() -> None:
    state = make_state(
        seed=1
    )

    tracker = RangeTracker()

    with pytest.raises(
        ValueError
    ):
        tracker.set_range(
            seat=0,
            weights={
                state.own_hand_key: -1.0,
            },
        )


def test_normalize_range() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 0.8,
        second.own_hand_key: 0.2,
    }

    tracker.normalize(
        seat=0
    )

    result = tracker.range_for_seat(
        0
    )

    assert (
        sum(result.values())
        == pytest.approx(1.0)
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(0.8)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(0.2)
    )


def test_normalize_scales_weights() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first.own_hand_key: 4.0,
        second.own_hand_key: 1.0,
    }

    tracker.normalize(
        seat=0
    )

    result = tracker.range_for_seat(
        0
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(0.8)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(0.2)
    )


def test_normalize_zero_weight_range() -> None:
    state = make_state(
        seed=1
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        state.own_hand_key: 0.0,
    }

    tracker.normalize(
        seat=0
    )

    assert (
        tracker.range_for_seat(0)
        == {
            state.own_hand_key: 0.0,
        }
    )


def test_normalize_rejects_uninitialized_player() -> None:
    tracker = RangeTracker()

    with pytest.raises(
        ValueError
    ):
        tracker.normalize(
            seat=0
        )


def test_initialize_from_starting_range() -> None:
    first = make_state(
        seed=1
    )

    second = make_state(
        seed=2
    )

    starting_range = StartingRange(
        weights={
            first.own_hand_key: 4.0,
            second.own_hand_key: 1.0,
        }
    )

    tracker = RangeTracker()

    tracker.initialize_from_starting_range(
        seat=0,
        starting_range=starting_range,
    )

    result = tracker.range_for_seat(
        0
    )

    assert (
        result[
            first.own_hand_key
        ]
        == pytest.approx(4.0)
    )

    assert (
        result[
            second.own_hand_key
        ]
        == pytest.approx(1.0)
    )


def test_starting_range_initialization_copies_weights() -> None:
    state = make_state(
        seed=1
    )

    starting_range = StartingRange(
        weights={
            state.own_hand_key: 4.0,
        }
    )

    tracker = RangeTracker()

    tracker.initialize_from_starting_range(
        seat=0,
        starting_range=starting_range,
    )

    tracker.weights[
        0
    ][
        state.own_hand_key
    ] = 99.0

    assert (
        starting_range.weight_for_hand(
            state.own_hand_key
        )
        == pytest.approx(4.0)
    )