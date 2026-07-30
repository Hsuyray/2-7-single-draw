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
        == 1.0
    )

    assert (
        result[
            second.own_hand_key
        ]
        == 1.0
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
        == 0.8
    )

    assert (
        result[
            second.own_hand_key
        ]
        == 0.3
    )


def test_apply_action_can_remove_zero_probability_hand() -> None:
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
        == 1.0
    )

    assert (
        result[
            second.own_hand_key
        ]
        == 0.0
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

    assert abs(
        sum(result.values())
        - 1.0
    ) < 1e-9

    assert (
        result[
            first.own_hand_key
        ]
        == 0.8
    )

    assert (
        result[
            second.own_hand_key
        ]
        == 0.2
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

    assert abs(
        result[
            first.own_hand_key
        ]
        - 0.8
    ) < 1e-9

    assert abs(
        result[
            second.own_hand_key
        ]
        - 0.2
    ) < 1e-9