import pytest

from solver.action_executor import (
    apply_solver_action,
    clone_game,
)
from solver.actions import DiscardAction
from solver.game_state import ActionType, GameConfig
from solver.legal_actions import BettingAction
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


def enter_draw_phase(
    game: SingleDrawGame,
) -> None:
    game.apply_betting_action(
        ActionType.CALL
    )
    game.apply_betting_action(
        ActionType.CHECK
    )

    assert game.phase == GamePhase.DRAW


def test_clone_game_returns_different_object() -> None:
    game = make_heads_up_game()

    cloned = clone_game(game)

    assert cloned is not game
    assert cloned.betting_state is not game.betting_state
    assert cloned.deck is not game.deck
    assert cloned.hands is not game.hands


def test_clone_preserves_game_values() -> None:
    game = make_heads_up_game()

    cloned = clone_game(game)

    assert cloned.phase == game.phase
    assert cloned.pot == game.pot
    assert cloned.acting_seat == game.acting_seat
    assert cloned.hands == game.hands
    assert cloned.action_history == game.action_history


def test_betting_action_does_not_modify_original_game() -> None:
    game = make_heads_up_game()
    original_pot = game.pot
    original_acting_seat = game.acting_seat

    next_game = apply_solver_action(
        game,
        BettingAction(
            ActionType.CALL
        ),
    )

    assert game.pot == original_pot
    assert game.acting_seat == original_acting_seat
    assert game.action_history == []

    assert next_game.pot != original_pot
    assert next_game.acting_seat != original_acting_seat
    assert len(next_game.action_history) == 1


def test_call_action_is_applied_to_copy() -> None:
    game = make_heads_up_game()

    next_game = apply_solver_action(
        game,
        BettingAction(
            ActionType.CALL
        ),
    )

    assert next_game.action_history[-1].action_type == (
        ActionType.CALL.value
    )


def test_raise_action_is_applied_to_copy() -> None:
    game = make_heads_up_game()

    next_game = apply_solver_action(
        game,
        BettingAction(
            ActionType.RAISE,
            raise_to=4.0,
        ),
    )

    assert next_game.betting_state.current_bet == 4.0
    assert next_game.action_history[-1].action_type == (
        ActionType.RAISE.value
    )
    assert next_game.action_history[-1].amount == 4.0


def test_fold_action_can_complete_hand() -> None:
    game = make_heads_up_game()

    next_game = apply_solver_action(
        game,
        BettingAction(
            ActionType.FOLD
        ),
    )

    assert next_game.phase == GamePhase.COMPLETE
    assert next_game.pot_awarded is True
    assert next_game.winner_seats == (1,)

    assert game.phase == GamePhase.PREDRAW_BETTING
    assert game.pot_awarded is False


def test_discard_action_is_applied_to_copy() -> None:
    game = make_heads_up_game()
    enter_draw_phase(game)

    acting_seat = game.draw_acting_seat

    assert acting_seat is not None

    original_hand = game.hands[acting_seat]

    assert original_hand is not None

    next_game = apply_solver_action(
        game,
        DiscardAction((4,)),
    )

    next_hand = next_game.hands[acting_seat]

    assert next_hand is not None
    assert next_hand != original_hand

    assert game.hands[acting_seat] == original_hand
    assert acting_seat not in game.draw_results

    assert acting_seat in next_game.draw_results
    assert (
        next_game.draw_results[
            acting_seat
        ].action
        == DiscardAction((4,))
    )


def test_stand_pat_is_applied_to_copy() -> None:
    game = make_heads_up_game()
    enter_draw_phase(game)

    acting_seat = game.draw_acting_seat

    assert acting_seat is not None

    original_hand = game.hands[acting_seat]

    next_game = apply_solver_action(
        game,
        DiscardAction(()),
    )

    assert next_game.hands[acting_seat] == original_hand
    assert (
        next_game.draw_results[
            acting_seat
        ].action.is_stand_pat
        is True
    )


def test_betting_action_during_draw_phase_is_rejected() -> None:
    game = make_heads_up_game()
    enter_draw_phase(game)

    with pytest.raises(ValueError):
        apply_solver_action(
            game,
            BettingAction(
                ActionType.CHECK
            ),
        )


def test_discard_action_during_betting_is_rejected() -> None:
    game = make_heads_up_game()

    with pytest.raises(ValueError):
        apply_solver_action(
            game,
            DiscardAction(()),
        )


def test_invalid_discard_index_is_rejected() -> None:
    game = make_heads_up_game()
    enter_draw_phase(game)

    with pytest.raises(ValueError):
        apply_solver_action(
            game,
            DiscardAction((5,)),
        )


def test_original_deck_is_not_modified_by_draw_branch() -> None:
    game = make_heads_up_game()
    enter_draw_phase(game)

    original_stock = tuple(game.deck.stock)
    original_muck = tuple(game.deck.muck)

    next_game = apply_solver_action(
        game,
        DiscardAction((4,)),
    )

    assert tuple(game.deck.stock) == original_stock
    assert tuple(game.deck.muck) == original_muck

    assert (
        tuple(next_game.deck.stock)
        != original_stock
    )
    assert next_game.deck.muck_size == 1