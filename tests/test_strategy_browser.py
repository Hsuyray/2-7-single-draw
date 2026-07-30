from copy import deepcopy

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
from solver.public_node_navigator import (
    PublicNodeNavigator,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_browser import (
    StrategyBrowser,
)
from solver.strategy_index import (
    StrategyIndex,
)


def make_game() -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=100.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=42,
    )


def make_browser() -> tuple[
    StrategyBrowser,
    InformationState,
    InformationState,
]:
    game = make_game()

    initial_state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    after_call_game = deepcopy(game)

    after_call_game.apply_betting_action(
        ActionType.CALL
    )

    after_call_state = (
        InformationState.from_game(
            after_call_game,
            observer_seat=1,
            abstraction="exact",
        )
    )

    fold = BettingAction(
        ActionType.FOLD
    )

    call = BettingAction(
        ActionType.CALL
    )

    check = BettingAction(
        ActionType.CHECK
    )

    index = (
        StrategyIndex.from_strategies(
            {
                initial_state: {
                    fold: 0.25,
                    call: 0.75,
                },
                after_call_state: {
                    check: 1.0,
                },
            }
        )
    )

    navigator = (
        PublicNodeNavigator.from_game(
            game
        )
    )

    browser = StrategyBrowser(
        navigator=navigator,
        strategy_index=index,
    )

    return (
        browser,
        initial_state,
        after_call_state,
    )


def test_browser_exposes_current_public_node() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    assert (
        browser.public_node
        == initial_state.public_node
    )


def test_browser_exposes_current_actor() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    assert (
        browser.acting_seat
        == initial_state.acting_seat
    )


def test_hand_mode_returns_current_hand_strategy() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    strategy = (
        browser.current_hand_strategy(
            initial_state.own_hand_key
        )
    )

    assert strategy is not None

    assert sum(
        strategy.values()
    ) == 1.0


def test_range_mode_contains_current_hand() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    range_strategy = (
        browser.current_range_strategy()
    )

    assert (
        initial_state.own_hand_key
        in range_strategy
    )


def test_betting_action_moves_browser_to_next_node() -> None:
    (
        browser,
        _,
        after_call_state,
    ) = make_browser()

    browser.apply_betting(
        ActionType.CALL
    )

    assert (
        browser.public_node
        == after_call_state.public_node
    )


def test_next_node_uses_next_players_strategy() -> None:
    (
        browser,
        _,
        after_call_state,
    ) = make_browser()

    browser.apply_betting(
        ActionType.CALL
    )

    strategy = (
        browser.current_hand_strategy(
            after_call_state.own_hand_key
        )
    )

    assert strategy is not None

    check = BettingAction(
        ActionType.CHECK
    )

    assert strategy == {
        check: 1.0,
    }


def test_range_mode_changes_with_current_node() -> None:
    (
        browser,
        initial_state,
        after_call_state,
    ) = make_browser()

    initial_range = (
        browser.current_range_strategy()
    )

    assert (
        initial_state.own_hand_key
        in initial_range
    )

    browser.apply_betting(
        ActionType.CALL
    )

    next_range = (
        browser.current_range_strategy()
    )

    assert (
        after_call_state.own_hand_key
        in next_range
    )


def test_unknown_hand_returns_none() -> None:
    (
        browser,
        _,
        after_call_state,
    ) = make_browser()

    result = (
        browser.current_hand_strategy(
            after_call_state.own_hand_key
        )
    )

    assert result is None


def test_strategy_for_action_matches_hand_mode() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    direct = (
        browser.current_hand_strategy(
            initial_state.own_hand_key
        )
    )

    alias = browser.strategy_for_action(
        initial_state.own_hand_key
    )

    assert direct == alias


def test_browser_accepts_exact_hand_input() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    hand = (
        browser.navigator.game.hands[
            initial_state.observer_seat
        ]
    )

    assert hand is not None

    result = (
        browser.current_strategy_for_hand(
            hand
        )
    )

    expected = (
        browser.current_hand_strategy(
            initial_state.own_hand_key
        )
    )

    assert result == expected