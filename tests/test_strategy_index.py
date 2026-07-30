from solver.game_state import (
    GameConfig,
)
from solver.information_state import (
    InformationState,
)
from solver.legal_actions import (
    BettingAction,
)
from solver.game_state import (
    ActionType,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_index import (
    StrategyIndex,
)


def make_game(
    *,
    seed: int,
) -> SingleDrawGame:
    return SingleDrawGame(
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


def test_strategy_for_state() -> None:
    game = make_game(
        seed=42
    )

    state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    fold = BettingAction(
        ActionType.FOLD
    )

    call = BettingAction(
        ActionType.CALL
    )

    expected = {
        fold: 0.25,
        call: 0.75,
    }

    index = (
        StrategyIndex.from_strategies(
            {
                state: expected,
            }
        )
    )

    assert (
        index.strategy_for_state(
            state
        )
        == expected
    )


def test_strategy_for_hand() -> None:
    game = make_game(
        seed=42
    )

    state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    fold = BettingAction(
        ActionType.FOLD
    )

    call = BettingAction(
        ActionType.CALL
    )

    expected = {
        fold: 0.40,
        call: 0.60,
    }

    index = (
        StrategyIndex.from_strategies(
            {
                state: expected,
            }
        )
    )

    result = (
        index.strategy_for_hand(
            public_node=(
                state.public_node
            ),
            observer_seat=0,
            hand_key=(
                state.own_hand_key
            ),
        )
    )

    assert result == expected


def test_unknown_hand_returns_none() -> None:
    first_game = make_game(
        seed=1
    )

    second_game = make_game(
        seed=2
    )

    first_state = (
        InformationState.from_game(
            first_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    second_state = (
        InformationState.from_game(
            second_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first_state: {},
            }
        )
    )

    assert (
        first_state.public_node
        == second_state.public_node
    )

    if (
        first_state.own_hand_key
        == second_state.own_hand_key
    ):
        raise RuntimeError(
            "Test seeds unexpectedly "
            "produced the same hand."
        )

    assert (
        index.strategy_for_hand(
            public_node=(
                first_state.public_node
            ),
            observer_seat=0,
            hand_key=(
                second_state.own_hand_key
            ),
        )
        is None
    )


def test_range_strategy_contains_multiple_hands() -> None:
    first_game = make_game(
        seed=1
    )

    second_game = make_game(
        seed=2
    )

    first_state = (
        InformationState.from_game(
            first_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    second_state = (
        InformationState.from_game(
            second_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    assert (
        first_state.public_node
        == second_state.public_node
    )

    assert (
        first_state.own_hand_key
        != second_state.own_hand_key
    )

    fold = BettingAction(
        ActionType.FOLD
    )

    call = BettingAction(
        ActionType.CALL
    )

    first_strategy = {
        fold: 0.80,
        call: 0.20,
    }

    second_strategy = {
        fold: 0.30,
        call: 0.70,
    }

    index = (
        StrategyIndex.from_strategies(
            {
                first_state: (
                    first_strategy
                ),
                second_state: (
                    second_strategy
                ),
            }
        )
    )

    result = index.range_strategy(
        public_node=(
            first_state.public_node
        ),
        observer_seat=0,
    )

    assert len(result) == 2

    assert (
        result[
            first_state.own_hand_key
        ]
        == first_strategy
    )

    assert (
        result[
            second_state.own_hand_key
        ]
        == second_strategy
    )


def test_hand_count_matches_range_size() -> None:
    first_game = make_game(
        seed=1
    )

    second_game = make_game(
        seed=2
    )

    first_state = (
        InformationState.from_game(
            first_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    second_state = (
        InformationState.from_game(
            second_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first_state: {},
                second_state: {},
            }
        )
    )

    assert (
        index.hand_count(
            public_node=(
                first_state.public_node
            ),
            observer_seat=0,
        )
        == 2
    )


def test_different_observers_are_separated() -> None:
    game = make_game(
        seed=42
    )

    first_state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    second_state = (
        InformationState.from_game(
            game,
            observer_seat=1,
            abstraction="exact",
        )
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first_state: {},
                second_state: {},
            }
        )
    )

    assert (
        index.hand_count(
            public_node=(
                first_state.public_node
            ),
            observer_seat=0,
        )
        == 1
    )

    assert (
        index.hand_count(
            public_node=(
                first_state.public_node
            ),
            observer_seat=1,
        )
        == 1
    )


def test_public_nodes_deduplicates_same_node() -> None:
    first_game = make_game(
        seed=1
    )

    second_game = make_game(
        seed=2
    )

    first_state = (
        InformationState.from_game(
            first_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    second_state = (
        InformationState.from_game(
            second_game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first_state: {},
                second_state: {},
            }
        )
    )

    assert len(
        index.public_nodes()
    ) == 1