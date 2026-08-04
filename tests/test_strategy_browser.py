from copy import deepcopy

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
from solver.public_legal_actions import (
    PublicBettingAction,
)
from solver.public_node_navigator import (
    PublicNodeNavigator,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_browser import (
    HandStrategySnapshot,
    RangeActionView,
    RangeStrategySnapshot,
    StrategyActionView,
    StrategyBrowser,
)
from solver.strategy_index import (
    StrategyIndex,
)
from solver.range_tracker import (
    RangeTracker,
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

    after_call_game = deepcopy(
        game
    )

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
        raise_sizes=(),
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


def test_browser_exposes_current_game() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    assert (
        browser.game
        is browser.navigator.game
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
    ) == pytest.approx(
        1.0
    )


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

    alias = (
        browser.strategy_for_action(
            initial_state.own_hand_key
        )
    )

    assert direct == alias


def test_browser_accepts_exact_hand_input() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    hand = (
        browser.game.hands[
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


def test_browser_returns_public_legal_actions() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    assert (
        snapshot.acting_seat
        == browser.acting_seat
    )

    assert snapshot.actions


def test_browser_legal_actions_are_public_betting_actions() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    assert snapshot.betting_actions

    assert all(
        isinstance(
            action,
            PublicBettingAction,
        )
        for action
        in snapshot.betting_actions
    )


def test_browser_empty_raise_sizes_disable_raises() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = ()

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    assert all(
        action.action_type
        != ActionType.RAISE
        for action
        in snapshot.betting_actions
    )


def test_browser_policy_generates_raise_actions() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = None

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    raises = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    assert raises


def test_browser_policy_raise_actions_have_labels() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = None

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    raises = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    assert raises

    assert all(
        action.label
        for action in raises
    )


def test_browser_policy_raise_actions_have_execution_values() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = None

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    raises = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    assert raises

    assert all(
        action.raise_to is not None
        for action in raises
    )


def test_browser_policy_includes_all_in() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = None

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    all_in_actions = [
        action
        for action
        in snapshot.betting_actions
        if action.is_all_in
    ]

    assert len(
        all_in_actions
    ) == 1

    assert (
        all_in_actions[0].label
        == "All-in"
    )


def test_browser_explicit_raise_size_is_preserved() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = (
        6.0,
    )

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    raises = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    assert raises == [
        PublicBettingAction(
            action_type=(
                ActionType.RAISE
            ),
            label="Raise to 6",
            raise_to=6.0,
            pot_fraction=None,
            is_all_in=False,
        )
    ]


def test_browser_combines_actions_and_probabilities() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    snapshot = (
        browser.current_hand_action_snapshot(
            initial_state.own_hand_key
        )
    )

    assert snapshot is not None

    assert isinstance(
        snapshot,
        HandStrategySnapshot,
    )

    assert (
        snapshot.acting_seat
        == browser.acting_seat
    )

    assert len(
        snapshot.actions
    ) == 2


def test_browser_action_view_contains_labels() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    snapshot = (
        browser.current_hand_action_snapshot(
            initial_state.own_hand_key
        )
    )

    assert snapshot is not None

    labels = {
        action.label
        for action
        in snapshot.actions
    }

    assert labels == {
        "Fold",
        "Call",
    }


def test_browser_action_view_contains_probabilities() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    snapshot = (
        browser.current_hand_action_snapshot(
            initial_state.own_hand_key
        )
    )

    assert snapshot is not None

    probabilities = {
        action.label: (
            action.probability
        )
        for action
        in snapshot.actions
    }

    assert probabilities == {
        "Fold": 0.25,
        "Call": 0.75,
    }


def test_browser_action_snapshot_sums_to_one() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    snapshot = (
        browser.current_hand_action_snapshot(
            initial_state.own_hand_key
        )
    )

    assert snapshot is not None

    assert (
        snapshot.total_probability
        == pytest.approx(1.0)
    )


def test_strategy_action_view_exposes_percentage() -> None:
    action = PublicBettingAction(
        action_type=ActionType.CALL,
        label="Call",
    )

    view = StrategyActionView(
        action=action,
        probability=0.375,
    )

    assert (
        view.label
        == "Call"
    )

    assert (
        view.percentage
        == pytest.approx(37.5)
    )


def test_strategy_action_view_rejects_negative_probability() -> None:
    action = PublicBettingAction(
        action_type=ActionType.CALL,
        label="Call",
    )

    with pytest.raises(
        ValueError
    ):
        StrategyActionView(
            action=action,
            probability=-0.1,
        )


def test_strategy_action_view_rejects_probability_above_one() -> None:
    action = PublicBettingAction(
        action_type=ActionType.CALL,
        label="Call",
    )

    with pytest.raises(
        ValueError
    ):
        StrategyActionView(
            action=action,
            probability=1.1,
        )


def test_unknown_hand_has_no_action_snapshot() -> None:
    (
        browser,
        _,
        after_call_state,
    ) = make_browser()

    snapshot = (
        browser.current_hand_action_snapshot(
            after_call_state.own_hand_key
        )
    )

    assert snapshot is None


def test_exact_hand_action_snapshot() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    hand = browser.game.hands[
        initial_state.observer_seat
    ]

    assert hand is not None

    snapshot = (
        browser.current_action_snapshot_for_hand(
            hand
        )
    )

    assert snapshot is not None

    probabilities = {
        action.label: (
            action.probability
        )
        for action
        in snapshot.actions
    }

    assert probabilities == {
        "Fold": 0.25,
        "Call": 0.75,
    }


def test_browser_detects_action_profile_mismatch() -> None:
    (
        browser,
        initial_state,
        _,
    ) = make_browser()

    browser.raise_sizes = None

    with pytest.raises(
        RuntimeError,
        match=(
            "Current legal actions do not "
            "match"
        ),
    ):
        browser.current_hand_action_snapshot(
            initial_state.own_hand_key
        )


def test_browser_detects_strategy_with_extra_action() -> None:
    game = make_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
        abstraction="exact",
    )

    fold = BettingAction(
        ActionType.FOLD
    )

    call = BettingAction(
        ActionType.CALL
    )

    illegal_extra_raise = BettingAction(
        ActionType.RAISE,
        raise_to=6.0,
    )

    index = (
        StrategyIndex.from_strategies(
            {
                state: {
                    fold: 0.25,
                    call: 0.50,
                    illegal_extra_raise: 0.25,
                }
            }
        )
    )

    browser = StrategyBrowser(
        navigator=(
            PublicNodeNavigator.from_game(
                game
            )
        ),
        strategy_index=index,
        raise_sizes=(),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Solved strategy contains "
            "actions that are not legal"
        ),
    ):
        browser.current_hand_action_snapshot(
            state.own_hand_key
        )


def test_browser_applies_public_call_action() -> None:
    (
        browser,
        initial_state,
        after_call_state,
    ) = make_browser()

    snapshot = (
        browser.current_hand_action_snapshot(
            initial_state.own_hand_key
        )
    )

    assert snapshot is not None

    call_view = next(
        view
        for view in snapshot.actions
        if view.label == "Call"
    )

    browser.apply_public_action(
        call_view.action
    )

    assert (
        browser.public_node
        == after_call_state.public_node
    )


def test_browser_applies_public_betting_action() -> None:
    (
        browser,
        _,
        after_call_state,
    ) = make_browser()

    action = PublicBettingAction(
        action_type=ActionType.CALL,
        label="Call",
    )

    browser.apply_public_action(
        action
    )

    assert (
        browser.public_node
        == after_call_state.public_node
    )


def test_browser_applies_public_raise_action() -> None:
    game = make_game()

    initial_state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    fold_action = BettingAction(
        action_type=ActionType.FOLD,
    )

    call_action = BettingAction(
        action_type=ActionType.CALL,
    )

    raise_action = BettingAction(
        action_type=ActionType.RAISE,
        raise_to=6.0,
    )

    index = (
        StrategyIndex.from_strategies(
            {
                initial_state: {
                    fold_action: 0.0,
                    call_action: 0.0,
                    raise_action: 1.0,
                }
            }
        )
    )

    browser = StrategyBrowser(
        navigator=(
            PublicNodeNavigator.from_game(
                game
            )
        ),
        strategy_index=index,
        raise_sizes=(
            6.0,
        ),
    )

    snapshot = (
        browser.current_hand_action_snapshot(
            initial_state.own_hand_key
        )
    )

    assert snapshot is not None

    public_raise = next(
        view.action
        for view in snapshot.actions
        if view.label == "Raise to 6"
    )

    assert isinstance(
        public_raise,
        PublicBettingAction,
    )

    assert (
        public_raise.raise_to
        == 6.0
    )

    browser.apply_public_action(
        public_raise
    )

    assert (
        browser.game.betting_state.current_bet
        == 6.0
    )


def test_apply_public_raise_uses_execution_value() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = (
        6.0,
    )

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    public_raise = next(
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
            and action.raise_to
            == 6.0
        )
    )

    browser.apply_public_action(
        public_raise
    )

    assert (
        browser.game.betting_state.current_bet
        == 6.0
    )


def test_apply_public_action_rejects_illegal_check() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    illegal_check = PublicBettingAction(
        action_type=ActionType.CHECK,
        label="Check",
    )

    with pytest.raises(
        ValueError,
        match=(
            "selected action is not legal"
        ),
    ):
        browser.apply_public_action(
            illegal_check
        )


def test_apply_public_action_rejects_forged_raise() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.raise_sizes = (
        6.0,
    )

    forged_raise = PublicBettingAction(
        action_type=ActionType.RAISE,
        label="Raise to 999",
        raise_to=999.0,
        pot_fraction=None,
        is_all_in=False,
    )

    with pytest.raises(
        ValueError,
        match=(
            "selected action is not legal"
        ),
    ):
        browser.apply_public_action(
            forged_raise
        )


def test_apply_public_action_rejects_stale_action() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    call_action = next(
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.CALL
        )
    )

    browser.apply_public_action(
        call_action
    )

    with pytest.raises(
        ValueError,
        match=(
            "selected action is not legal"
        ),
    ):
        browser.apply_public_action(
            call_action
        )


def test_apply_public_action_accepts_current_legal_action() -> None:
    (
        browser,
        _,
        after_call_state,
    ) = make_browser()

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    call_action = next(
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.CALL
        )
    )

    result = browser.apply_public_action(
        call_action
    )

    assert (
        result
        == after_call_state.public_node
    )

    assert (
        browser.public_node
        == after_call_state.public_node
    )


def make_range_browser() -> tuple[
    StrategyBrowser,
    InformationState,
    InformationState,
]:
    first_game = make_game()

    second_game = SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=100.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=99,
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

    fold = BettingAction(
        ActionType.FOLD
    )

    call = BettingAction(
        ActionType.CALL
    )

    index = (
        StrategyIndex.from_strategies(
            {
                first_state: {
                    fold: 0.0,
                    call: 1.0,
                },
                second_state: {
                    fold: 0.75,
                    call: 0.25,
                },
            }
        )
    )

    tracker = RangeTracker()

    tracker.weights[0] = {
        first_state.own_hand_key: 2.0,
        second_state.own_hand_key: 1.0,
    }

    browser = StrategyBrowser(
        navigator=(
            PublicNodeNavigator.from_game(
                first_game
            )
        ),
        strategy_index=index,
        range_tracker=tracker,
        raise_sizes=(),
    )

    return (
        browser,
        first_state,
        second_state,
    )


def test_browser_returns_range_action_summary() -> None:
    (
        browser,
        _,
        _,
    ) = make_range_browser()

    summary = (
        browser.current_range_action_summary()
    )

    assert summary is not None

    assert isinstance(
        summary,
        RangeStrategySnapshot,
    )

    assert (
        summary.public_node
        == browser.public_node
    )

    assert (
        summary.acting_seat
        == browser.acting_seat
    )


def test_range_action_summary_uses_range_weights() -> None:
    (
        browser,
        _,
        _,
    ) = make_range_browser()

    summary = (
        browser.current_range_action_summary()
    )

    assert summary is not None

    probabilities = {
        action.label: (
            action.probability
        )
        for action in summary.actions
    }

    # First hand:
    # weight 2, Call 100%
    #
    # Second hand:
    # weight 1, Call 25%, Fold 75%
    #
    # Call:
    # (2 * 1.00 + 1 * 0.25) / 3
    # = 0.75
    #
    # Fold:
    # (2 * 0.00 + 1 * 0.75) / 3
    # = 0.25
    assert probabilities == {
        "Fold": pytest.approx(
            0.25
        ),
        "Call": pytest.approx(
            0.75
        ),
    }


def test_range_action_summary_exposes_percentages() -> None:
    (
        browser,
        _,
        _,
    ) = make_range_browser()

    summary = (
        browser.current_range_action_summary()
    )

    assert summary is not None

    percentages = {
        action.label: (
            action.percentage
        )
        for action in summary.actions
    }

    assert percentages == {
        "Fold": pytest.approx(
            25.0
        ),
        "Call": pytest.approx(
            75.0
        ),
    }


def test_range_action_summary_preserves_range_metadata() -> None:
    (
        browser,
        _,
        _,
    ) = make_range_browser()

    summary = (
        browser.current_range_action_summary()
    )

    assert summary is not None

    assert (
        summary.total_weight
        == pytest.approx(3.0)
    )

    assert summary.hand_count == 2

    assert summary.action_count == 2


def test_range_action_summary_probabilities_sum_to_one() -> None:
    (
        browser,
        _,
        _,
    ) = make_range_browser()

    summary = (
        browser.current_range_action_summary()
    )

    assert summary is not None

    assert (
        summary.total_probability
        == pytest.approx(1.0)
    )


def test_range_action_summary_uses_public_actions() -> None:
    (
        browser,
        _,
        _,
    ) = make_range_browser()

    summary = (
        browser.current_range_action_summary()
    )

    assert summary is not None

    assert all(
        isinstance(
            action.action,
            PublicBettingAction,
        )
        for action in summary.actions
    )


def test_range_action_summary_returns_none_without_tracker() -> None:
    (
        browser,
        _,
        _,
    ) = make_browser()

    browser.range_tracker = None

    assert (
        browser.current_range_action_summary()
        is None
    )


def test_range_action_view_exposes_label() -> None:
    public_action = PublicBettingAction(
        action_type=ActionType.CALL,
        label="Call",
    )

    view = RangeActionView(
        action=public_action,
        probability=0.625,
    )

    assert view.label == "Call"

    assert (
        view.percentage
        == pytest.approx(62.5)
    )


def test_range_action_view_rejects_negative_probability() -> None:
    public_action = PublicBettingAction(
        action_type=ActionType.CALL,
        label="Call",
    )

    with pytest.raises(
        ValueError
    ):
        RangeActionView(
            action=public_action,
            probability=-0.1,
        )


def test_range_action_view_rejects_probability_above_one() -> None:
    public_action = PublicBettingAction(
        action_type=ActionType.CALL,
        label="Call",
    )

    with pytest.raises(
        ValueError
    ):
        RangeActionView(
            action=public_action,
            probability=1.1,
        )


def test_range_summary_detects_action_profile_mismatch() -> None:
    (
        browser,
        _,
        _,
    ) = make_range_browser()

    # Stored range strategies only contain
    # Fold and Call. Enabling policy raises
    # creates additional legal actions.
    browser.raise_sizes = None

    with pytest.raises(
        RuntimeError,
        match=(
            "Current legal actions do not "
            "match the actions in the solved "
            "range strategy"
        ),
    ):
        browser.current_range_action_summary()


def test_apply_public_action_updates_acting_range() -> None:
    (
        browser,
        first_state,
        second_state,
    ) = make_range_browser()

    snapshot = (
        browser.current_legal_actions()
    )

    assert snapshot is not None

    call_action = next(
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.CALL
        )
    )

    browser.apply_public_action(
        call_action
    )

    assert (
        browser.range_tracker
        is not None
    )

    updated_range = (
        browser.range_tracker
        .range_for_seat(0)
    )

    assert (
        updated_range[
            first_state.own_hand_key
        ]
        == pytest.approx(8 / 9)
    )

    assert (
        updated_range[
            second_state.own_hand_key
        ]
        == pytest.approx(1 / 9)
    )

    assert (
        sum(updated_range.values())
        == pytest.approx(1.0)
    )