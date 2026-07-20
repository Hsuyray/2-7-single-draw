from types import SimpleNamespace

import pytest

from solver.actions import DiscardAction
from solver.cards import Card
from solver.draw import DrawResult
from solver.hand import Hand
from solver.information_state import (
    InformationState,
    PublicPlayerState,
)
from solver.action_history import PublicAction
from solver.hand_abstraction import exact_hand_key


def make_fake_game() -> SimpleNamespace:
    player_zero = SimpleNamespace(
        seat=0,
        stack=99.0,
        committed_total=1.0,
        has_folded=False,
        is_all_in=False,
    )

    player_one = SimpleNamespace(
        seat=1,
        stack=98.0,
        committed_total=2.0,
        has_folded=False,
        is_all_in=False,
    )

    hand_zero = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "Ks",
    )

    hand_one = Hand.from_strings(
        "8s",
        "6h",
        "4c",
        "2d",
        "Qh",
    )

    return SimpleNamespace(
        config=SimpleNamespace(
            player_count=2,
        ),
        hands=[
            hand_zero,
            hand_one,
        ],
        betting_state=SimpleNamespace(
            players=[
                player_zero,
                player_one,
            ],
        ),
        draw_results={},
        action_history=[],
        phase=SimpleNamespace(
            value="predraw_betting",
        ),
        acting_seat=0,
        button_seat=0,
        pot=3.0,
    )


def test_public_player_state_is_hashable() -> None:
    state = PublicPlayerState(
        seat=0,
        stack=100.0,
        committed_total=0.0,
        has_folded=False,
        is_all_in=False,
        draw_count=None,
    )

    assert isinstance(hash(state), int)


def test_information_state_is_hashable() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert isinstance(hash(state), int)


def test_information_state_contains_own_cards() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert state.own_hand_key == exact_hand_key(
        game.hands[0]
    )


def test_information_state_does_not_store_opponent_cards() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    opponent_cards = {
        "8s",
        "6h",
        "4c",
        "2d",
        "Qh",
    }

    state_values = repr(state)

    for card in opponent_cards:
        assert card not in state_values


def test_different_observers_see_different_private_cards() -> None:
    game = make_fake_game()

    state_zero = InformationState.from_game(
        game,
        observer_seat=0,
    )

    state_one = InformationState.from_game(
        game,
        observer_seat=1,
    )

    assert (
        state_zero.own_hand_key
        != state_one.own_hand_key
    )
    assert state_zero != state_one


def test_information_state_contains_public_game_data() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert state.phase == "predraw_betting"
    assert state.acting_seat == 0
    assert state.button_seat == 0
    assert state.pot == 3.0
    assert len(state.players) == 2


def test_players_without_draw_result_have_unknown_draw_count() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert state.players[0].draw_count is None
    assert state.players[1].draw_count is None


def test_completed_draw_count_is_public() -> None:
    game = make_fake_game()

    hand = game.hands[0]

    action = DiscardAction((4,))

    game.draw_results[0] = DrawResult(
        original_hand=hand,
        final_hand=Hand.from_strings(
            "7s",
            "5h",
            "4d",
            "3c",
            "2h",
        ),
        discarded_cards=(
            Card.from_string("Ks"),
        ),
        drawn_cards=(
            Card.from_string("2h"),
        ),
        action=action,
    )

    state = InformationState.from_game(
        game,
        observer_seat=1,
    )

    assert state.players[0].draw_count == 1
    assert state.players[1].draw_count is None


def test_stand_pat_is_recorded_as_zero_cards() -> None:
    game = make_fake_game()

    hand = game.hands[0]
    action = DiscardAction(())

    game.draw_results[0] = DrawResult(
        original_hand=hand,
        final_hand=hand,
        discarded_cards=(),
        drawn_cards=(),
        action=action,
    )

    state = InformationState.from_game(
        game,
        observer_seat=1,
    )

    assert state.players[0].draw_count == 0


def test_fold_and_all_in_status_are_public() -> None:
    game = make_fake_game()

    game.betting_state.players[0].has_folded = True
    game.betting_state.players[1].is_all_in = True

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert state.players[0].has_folded is True
    assert state.players[1].is_all_in is True


def test_invalid_observer_seat_is_rejected() -> None:
    game = make_fake_game()

    with pytest.raises(ValueError):
        InformationState.from_game(
            game,
            observer_seat=2,
        )


def test_negative_observer_seat_is_rejected() -> None:
    game = make_fake_game()

    with pytest.raises(ValueError):
        InformationState.from_game(
            game,
            observer_seat=-1,
        )


def test_missing_observer_hand_is_rejected() -> None:
    game = make_fake_game()
    game.hands[0] = None

    with pytest.raises(RuntimeError):
        InformationState.from_game(
            game,
            observer_seat=0,
        )


def test_information_state_contains_action_history() -> None:
    game = make_fake_game()

    game.action_history.append(
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="raise",
            amount=6.0,
        )
    )

    state = InformationState.from_game(
        game,
        observer_seat=1,
    )

    assert state.action_history == (
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="raise",
            amount=6.0,
        ),
    )


def test_different_action_histories_create_different_states() -> None:
    game_one = make_fake_game()
    game_two = make_fake_game()

    game_one.action_history.append(
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="call",
        )
    )

    game_two.action_history.append(
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="raise",
            amount=3.0,
        )
    )

    state_one = InformationState.from_game(
        game_one,
        observer_seat=0,
    )

    state_two = InformationState.from_game(
        game_two,
        observer_seat=0,
    )

    assert state_one != state_two