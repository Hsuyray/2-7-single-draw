import pytest

from solver.actions import DiscardAction
from solver.game_state import ActionType, GameConfig
from solver.legal_actions import (
    BettingAction,
    legal_actions,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def make_heads_up_game() -> SingleDrawGame:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    return SingleDrawGame(
        config=config,
        button_seat=0,
        shuffle_deck=False,
    )


def test_non_raise_action_cannot_include_raise_to() -> None:
    with pytest.raises(ValueError):
        BettingAction(
            ActionType.CALL,
            raise_to=4.0,
        )


def test_raise_action_requires_raise_to() -> None:
    with pytest.raises(ValueError):
        BettingAction(
            ActionType.RAISE,
        )


def test_negative_raise_is_rejected() -> None:
    with pytest.raises(ValueError):
        BettingAction(
            ActionType.RAISE,
            raise_to=-1.0,
        )


def test_facing_bet_can_fold_or_call() -> None:
    game = make_heads_up_game()

    actions = legal_actions(game)

    assert BettingAction(
        ActionType.FOLD
    ) in actions

    assert BettingAction(
        ActionType.CALL
    ) in actions

    assert BettingAction(
        ActionType.CHECK
    ) not in actions


def test_check_is_available_when_nothing_to_call() -> None:
    game = make_heads_up_game()

    game.apply_betting_action(
        ActionType.CALL
    )

    actions = legal_actions(game)

    assert BettingAction(
        ActionType.CHECK
    ) in actions

    assert BettingAction(
        ActionType.CALL
    ) not in actions

    assert BettingAction(
        ActionType.FOLD
    ) not in actions


def test_legal_raise_size_is_included() -> None:
    game = make_heads_up_game()

    actions = legal_actions(
        game,
        raise_sizes=(4.0,),
    )

    assert BettingAction(
        ActionType.RAISE,
        raise_to=4.0,
    ) in actions


def test_raise_not_above_current_bet_is_excluded() -> None:
    game = make_heads_up_game()

    actions = legal_actions(
        game,
        raise_sizes=(2.0,),
    )

    assert BettingAction(
        ActionType.RAISE,
        raise_to=2.0,
    ) not in actions


def test_raise_above_player_stack_is_excluded() -> None:
    game = make_heads_up_game()

    actions = legal_actions(
        game,
        raise_sizes=(200.0,),
    )

    assert BettingAction(
        ActionType.RAISE,
        raise_to=200.0,
    ) not in actions


def test_draw_phase_returns_discard_actions() -> None:
    game = make_heads_up_game()

    game.apply_betting_action(
        ActionType.CALL
    )
    game.apply_betting_action(
        ActionType.CHECK
    )

    assert game.phase == GamePhase.DRAW

    actions = legal_actions(game)

    assert len(actions) == 26
    assert all(
        isinstance(action, DiscardAction)
        for action in actions
    )


def test_draw_phase_can_use_full_draw_rules() -> None:
    game = make_heads_up_game()

    game.apply_betting_action(
        ActionType.CALL
    )
    game.apply_betting_action(
        ActionType.CHECK
    )

    actions = legal_actions(
        game,
        max_draw=5,
    )

    assert len(actions) == 32
    assert DiscardAction(
        (0, 1, 2, 3, 4)
    ) in actions


def test_complete_game_has_no_legal_actions() -> None:
    game = make_heads_up_game()
    game.phase = GamePhase.COMPLETE

    assert legal_actions(game) == ()


