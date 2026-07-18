import pytest

from solver.game_state import (
    ActionType,
    GameConfig,
    GameState,
)


def test_game_requires_between_two_and_six_players() -> None:
    with pytest.raises(ValueError):
        GameConfig(player_count=1)

    with pytest.raises(ValueError):
        GameConfig(player_count=7)


def test_six_player_forced_bet_positions() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    assert state.small_blind_seat == 1
    assert state.big_blind_seat == 2
    assert state.acting_seat == 3


def test_heads_up_button_posts_small_blind() -> None:
    state = GameState(
        config=GameConfig(player_count=2),
        button_seat=0,
    )

    assert state.small_blind_seat == 0
    assert state.big_blind_seat == 1
    assert state.acting_seat == 0


def test_default_starting_pot_is_three_big_blinds() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    assert state.pot == 3.0


def test_big_blind_ante_does_not_increase_current_bet() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    assert state.current_bet == 1.0


def test_small_blind_commitment() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    small_blind = state.players[state.small_blind_seat]

    assert small_blind.stack == 99.5
    assert small_blind.committed_this_round == 0.5
    assert small_blind.committed_total == 0.5


def test_big_blind_commitment_includes_ante() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    big_blind = state.players[state.big_blind_seat]

    assert big_blind.stack == 97.5
    assert big_blind.committed_this_round == 1.0
    assert big_blind.committed_total == 2.5


def test_big_blind_ante_can_be_disabled() -> None:
    state = GameState(
        config=GameConfig(
            player_count=6,
            big_blind_ante=0.0,
        ),
        button_seat=0,
    )

    assert state.pot == 1.5
    assert state.current_bet == 1.0


def test_button_position_wraps_around_table() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=5,
    )

    assert state.small_blind_seat == 0
    assert state.big_blind_seat == 1
    assert state.acting_seat == 2


def test_first_player_can_fold_call_or_raise() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    assert state.legal_actions() == {
        ActionType.FOLD,
        ActionType.CALL,
        ActionType.RAISE,
    }


def test_amount_to_call_is_one_big_blind() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    assert state.amount_to_call(state.acting_seat) == 1.0


def test_call_moves_chips_into_pot() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    acting_seat = state.acting_seat
    assert acting_seat is not None

    player = state.players[acting_seat]

    state.apply_action(ActionType.CALL)

    assert player.stack == 99.0
    assert player.committed_this_round == 1.0
    assert player.committed_total == 1.0
    assert state.pot == 4.0


def test_call_moves_action_to_next_player() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    assert state.acting_seat == 3

    state.apply_action(ActionType.CALL)

    assert state.acting_seat == 4


def test_fold_marks_player_as_folded() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    folding_seat = state.acting_seat
    assert folding_seat is not None

    state.apply_action(ActionType.FOLD)

    assert state.players[folding_seat].has_folded
    assert state.acting_seat == 4


def test_small_blind_calls_only_remaining_half_blind() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(ActionType.CALL)

    assert state.acting_seat == state.small_blind_seat
    assert state.amount_to_call(state.acting_seat) == 0.5

    state.apply_action(ActionType.CALL)

    small_blind = state.players[state.small_blind_seat]

    assert small_blind.committed_this_round == 1.0
    assert small_blind.committed_total == 1.0


def test_minimum_initial_raise_is_to_two_big_blinds() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    assert state.minimum_raise_to() == 2.0


def test_player_can_raise_to_two_big_blinds() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    raising_seat = state.acting_seat
    assert raising_seat is not None

    state.apply_action(
        ActionType.RAISE,
        raise_to=2.0,
    )

    raising_player = state.players[raising_seat]

    assert raising_player.committed_this_round == 2.0
    assert raising_player.stack == 98.0
    assert state.current_bet == 2.0
    assert state.pot == 5.0
    assert state.minimum_raise_size == 1.0


def test_larger_raise_updates_minimum_raise_size() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    state.apply_action(
        ActionType.RAISE,
        raise_to=4.0,
    )

    assert state.current_bet == 4.0
    assert state.minimum_raise_size == 3.0
    assert state.minimum_raise_to() == 7.0


def test_raise_smaller_than_minimum_is_rejected() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    with pytest.raises(ValueError):
        state.apply_action(
            ActionType.RAISE,
            raise_to=1.5,
        )


def test_raise_requires_raise_to_amount() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    with pytest.raises(ValueError):
        state.apply_action(ActionType.RAISE)


def test_cannot_raise_more_than_stack() -> None:
    state = GameState(
        config=GameConfig(
            player_count=6,
            starting_stack=10.0,
        ),
        button_seat=0,
    )

    with pytest.raises(ValueError):
        state.apply_action(
            ActionType.RAISE,
            raise_to=11.0,
        )


def test_short_all_in_raise_is_allowed() -> None:
    state = GameState(
        config=GameConfig(
            player_count=3,
            starting_stack=1.5,
            big_blind_ante=0.0,
        ),
        button_seat=0,
    )

    state.apply_action(
        ActionType.RAISE,
        raise_to=1.5,
    )

    player = state.players[0]

    assert player.is_all_in
    assert player.stack == 0.0
    assert player.committed_this_round == 1.5
    assert state.current_bet == 1.5


def test_all_in_call_pays_only_remaining_stack() -> None:
    state = GameState(
        config=GameConfig(
            player_count=3,
            starting_stack=1.5,
            big_blind_ante=0.0,
        ),
        button_seat=0,
    )

    state.apply_action(
        ActionType.RAISE,
        raise_to=1.5,
    )

    state.apply_action(ActionType.CALL)

    small_blind = state.players[state.small_blind_seat]

    assert small_blind.stack == 0.0
    assert small_blind.is_all_in
    assert small_blind.committed_this_round == 1.5


def test_betting_round_ends_after_everyone_calls() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(ActionType.CALL)
    state.apply_action(ActionType.CALL)
    state.apply_action(ActionType.CHECK)

    assert state.betting_round_complete
    assert state.acting_seat is None
    assert state.legal_actions() == set()


def test_betting_round_ends_after_raise_and_calls() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(
        ActionType.RAISE,
        raise_to=3.0,
    )
    state.apply_action(ActionType.CALL)
    state.apply_action(ActionType.CALL)

    assert state.betting_round_complete
    assert state.acting_seat is None
    assert state.current_bet == 3.0


def test_hand_ends_when_everyone_except_one_player_folds() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(ActionType.FOLD)
    state.apply_action(ActionType.FOLD)

    assert state.hand_complete
    assert state.betting_round_complete
    assert state.winner_seat == state.big_blind_seat
    assert state.acting_seat is None


def test_action_history_records_raise_amount_paid() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(
        ActionType.RAISE,
        raise_to=3.0,
    )

    assert state.action_history == [
        (0, ActionType.RAISE, 3.0)
    ]


def test_illegal_check_facing_bet_raises_error() -> None:
    state = GameState(
        config=GameConfig(player_count=6),
        button_seat=0,
    )

    with pytest.raises(ValueError):
        state.apply_action(ActionType.CHECK)

def test_start_new_betting_round_resets_commitments() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(ActionType.CALL)
    state.apply_action(ActionType.CALL)
    state.apply_action(ActionType.CHECK)

    assert state.betting_round_complete

    state.start_new_betting_round(
        first_acting_seat=state.small_blind_seat,
    )

    assert not state.betting_round_complete
    assert state.current_bet == 0.0
    assert state.minimum_raise_size == 1.0
    assert state.acting_seat == state.small_blind_seat

    assert all(
        player.committed_this_round == 0.0
        for player in state.players
    )

    assert all(
        not player.has_acted_since_last_raise
        for player in state.players
    )


def test_new_betting_round_starts_with_check_available() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(ActionType.CALL)
    state.apply_action(ActionType.CALL)
    state.apply_action(ActionType.CHECK)

    state.start_new_betting_round(
        first_acting_seat=state.small_blind_seat,
    )

    assert state.legal_actions() == {
        ActionType.CHECK,
        ActionType.RAISE,
    }


def test_cannot_start_new_round_with_folded_player() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    folded_seat = state.acting_seat
    assert folded_seat is not None

    state.apply_action(ActionType.FOLD)

    with pytest.raises(ValueError):
        state.start_new_betting_round(
            first_acting_seat=folded_seat,
        )


def test_cannot_start_new_round_after_hand_is_complete() -> None:
    state = GameState(
        config=GameConfig(player_count=3),
        button_seat=0,
    )

    state.apply_action(ActionType.FOLD)
    state.apply_action(ActionType.FOLD)

    assert state.hand_complete

    with pytest.raises(RuntimeError):
        state.start_new_betting_round(
            first_acting_seat=state.big_blind_seat,
        )

def test_players_can_have_different_starting_stacks() -> None:
    state = GameState(
        config=GameConfig(
            player_count=3,
            starting_stacks=(20.0, 50.0, 100.0),
            big_blind_ante=0.0,
        ),
        button_seat=0,
    )

    assert state.players[0].stack == 20.0
    assert state.players[1].stack == 49.5
    assert state.players[2].stack == 99.0


def test_starting_stacks_must_match_player_count() -> None:
    with pytest.raises(ValueError):
        GameConfig(
            player_count=3,
            starting_stacks=(20.0, 50.0),
        )


def test_all_starting_stacks_must_be_positive() -> None:
    with pytest.raises(ValueError):
        GameConfig(
            player_count=3,
            starting_stacks=(20.0, 0.0, 100.0),
        )


def test_default_stack_is_used_without_custom_stacks() -> None:
    state = GameState(
        config=GameConfig(
            player_count=3,
            starting_stack=75.0,
            big_blind_ante=0.0,
        ),
        button_seat=0,
    )

    assert state.players[0].stack == 75.0
    assert state.players[1].stack == 74.5
    assert state.players[2].stack == 74.0