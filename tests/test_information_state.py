from types import SimpleNamespace

import pytest

from solver.action_history import (
    PublicAction,
)
from solver.cards import Card
from solver.draw_hand_bucket import (
    DrawHandBucket,
)
from solver.hand import Hand
from solver.hand_abstraction import (
    ExactHandKey,
)
from solver.information_state import (
    InformationState,
)
from solver.postdraw_strength_bucket import (
    PostdrawStrengthBucket,
)
from solver.public_state import (
    PublicNodeKey,
    PublicPlayerState,
)


def make_hand(
    *cards: str,
) -> Hand:
    return Hand(
        tuple(
            Card.from_string(card)
            for card in cards
        )
    )


def make_player(
    *,
    seat: int,
    stack: float,
    committed_total: float,
    committed_this_round: float,
    has_folded: bool = False,
    is_all_in: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        seat=seat,
        stack=stack,
        committed_total=committed_total,
        committed_this_round=(
            committed_this_round
        ),
        has_folded=has_folded,
        is_all_in=is_all_in,
    )


def make_draw_result(
    draw_count: int,
) -> SimpleNamespace:
    """
    Match the production DrawResult shape
    required by PublicNodeKey:

        draw_result.action.draw_count
    """
    return SimpleNamespace(
        action=SimpleNamespace(
            draw_count=draw_count,
        )
    )


def make_fake_game() -> SimpleNamespace:
    player_zero = make_player(
        seat=0,
        stack=99.0,
        committed_total=1.0,
        committed_this_round=1.0,
    )

    player_one = make_player(
        seat=1,
        stack=96.5,
        committed_total=3.5,
        committed_this_round=2.0,
    )

    return SimpleNamespace(
        config=SimpleNamespace(
            player_count=2,
        ),
        hands=[
            make_hand(
                "7s",
                "5h",
                "4d",
                "3c",
                "2s",
            ),
            make_hand(
                "Ks",
                "Qh",
                "Jd",
                "9c",
                "8s",
            ),
        ],
        betting_state=SimpleNamespace(
            players=[
                player_zero,
                player_one,
            ],
            current_bet=2.0,
            minimum_raise_size=2.0,
        ),
        draw_results={},
        action_history=[],
        phase=SimpleNamespace(
            value="predraw_betting",
        ),
        acting_seat=0,
        button_seat=0,
        pot=4.5,
    )


def test_public_player_state_is_hashable() -> None:
    player = PublicPlayerState(
        seat=0,
        stack=99.0,
        committed_total=1.0,
        committed_this_round=1.0,
        has_folded=False,
        is_all_in=False,
        draw_count=None,
    )

    assert isinstance(
        hash(player),
        int,
    )


def test_information_state_is_hashable() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert isinstance(
        hash(state),
        int,
    )


def test_information_state_contains_own_cards() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert isinstance(
        state.own_hand_key,
        ExactHandKey,
    )


def test_information_state_does_not_store_opponent_cards() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert not hasattr(
        state,
        "opponent_hand",
    )

    assert not hasattr(
        state,
        "opponent_cards",
    )

    assert not hasattr(
        state.public_node,
        "hands",
    )


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


def test_different_observers_share_public_node() -> None:
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
        state_zero.public_node
        == state_one.public_node
    )


def test_information_state_contains_public_game_data() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert isinstance(
        state.public_node,
        PublicNodeKey,
    )

    assert (
        state.phase
        == "predraw_betting"
    )

    assert (
        state.acting_seat
        == 0
    )

    assert (
        state.button_seat
        == 0
    )

    assert (
        state.pot
        == 4.5
    )

    assert (
        state.public_node.current_bet
        == 2.0
    )

    assert (
        state.public_node.minimum_raise_size
        == 2.0
    )


def test_public_player_tracks_total_commitment() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.players[0].committed_total
        == 1.0
    )

    assert (
        state.players[1].committed_total
        == 3.5
    )


def test_public_player_tracks_current_round_commitment() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.players[0].committed_this_round
        == 1.0
    )

    assert (
        state.players[1].committed_this_round
        == 2.0
    )


def test_big_blind_ante_does_not_need_to_equal_round_commitment() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    big_blind = state.players[1]

    assert (
        big_blind.committed_total
        == 3.5
    )

    assert (
        big_blind.committed_this_round
        == 2.0
    )


def test_players_without_draw_result_have_unknown_draw_count() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.players[0].draw_count
        is None
    )

    assert (
        state.players[1].draw_count
        is None
    )


def test_completed_draw_count_is_public() -> None:
    game = make_fake_game()

    game.phase.value = "draw"

    game.draw_results[1] = (
        make_draw_result(
            2
        )
    )

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.players[1].draw_count
        == 2
    )


def test_stand_pat_is_recorded_as_zero_cards() -> None:
    game = make_fake_game()

    game.phase.value = "draw"

    game.draw_results[1] = (
        make_draw_result(
            0
        )
    )

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.players[1].draw_count
        == 0
    )


def test_fold_and_all_in_status_are_public() -> None:
    game = make_fake_game()

    game.betting_state.players[
        0
    ].has_folded = True

    game.betting_state.players[
        1
    ].is_all_in = True

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.players[0].has_folded
        is True
    )

    assert (
        state.players[1].is_all_in
        is True
    )


def test_information_state_contains_action_history() -> None:
    game = make_fake_game()

    action = PublicAction(
        phase="predraw_betting",
        seat=0,
        action_type="call",
        amount=None,
        draw_count=None,
    )

    game.action_history.append(
        action
    )

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.action_history
        == (action,)
    )


def test_different_action_histories_create_different_states() -> None:
    first_game = make_fake_game()

    second_game = make_fake_game()

    second_game.action_history.append(
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="call",
            amount=None,
            draw_count=None,
        )
    )

    first_state = (
        InformationState.from_game(
            first_game,
            observer_seat=0,
        )
    )

    second_state = (
        InformationState.from_game(
            second_game,
            observer_seat=0,
        )
    )

    assert (
        first_state
        != second_state
    )


def test_exact_abstraction_is_default() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert isinstance(
        state.own_hand_key,
        ExactHandKey,
    )


def test_exact_abstraction_can_be_requested_explicitly() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
        abstraction="exact",
    )

    assert isinstance(
        state.own_hand_key,
        ExactHandKey,
    )


def test_exact_and_bucket_states_are_different() -> None:
    game = make_fake_game()

    exact_state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    bucket_state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="bucket",
        )
    )

    assert (
        exact_state
        != bucket_state
    )

    assert (
        exact_state.public_node
        == bucket_state.public_node
    )


def test_bucket_abstraction_uses_draw_hand_bucket_predraw() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
        abstraction="bucket",
    )

    assert isinstance(
        state.own_hand_key,
        DrawHandBucket,
    )


def test_bucket_abstraction_uses_draw_hand_bucket_during_draw() -> None:
    game = make_fake_game()

    game.phase.value = "draw"

    state = InformationState.from_game(
        game,
        observer_seat=0,
        abstraction="bucket",
    )

    assert isinstance(
        state.own_hand_key,
        DrawHandBucket,
    )


def test_bucket_abstraction_uses_made_hand_postdraw() -> None:
    game = make_fake_game()

    game.phase.value = (
        "postdraw_betting"
    )

    state = InformationState.from_game(
        game,
        observer_seat=0,
        abstraction="bucket",
    )

    assert isinstance(
        state.own_hand_key,
        PostdrawStrengthBucket,
    )


def test_invalid_observer_seat_is_rejected() -> None:
    game = make_fake_game()

    with pytest.raises(
        ValueError
    ):
        InformationState.from_game(
            game,
            observer_seat=-1,
        )

    with pytest.raises(
        ValueError
    ):
        InformationState.from_game(
            game,
            observer_seat=2,
        )


def test_observer_without_hand_is_rejected() -> None:
    game = make_fake_game()

    game.hands[0] = None

    with pytest.raises(
        RuntimeError
    ):
        InformationState.from_game(
            game,
            observer_seat=0,
        )


def test_unknown_abstraction_is_rejected() -> None:
    game = make_fake_game()

    with pytest.raises(
        ValueError
    ):
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="unknown",  # type: ignore[arg-type]
        )


def test_information_state_compatibility_properties_use_public_node() -> None:
    game = make_fake_game()

    state = InformationState.from_game(
        game,
        observer_seat=0,
    )

    assert (
        state.phase
        == state.public_node.phase
    )

    assert (
        state.acting_seat
        == state.public_node.acting_seat
    )

    assert (
        state.button_seat
        == state.public_node.button_seat
    )

    assert (
        state.pot
        == state.public_node.pot
    )

    assert (
        state.players
        == state.public_node.players
    )

    assert (
        state.action_history
        == state.public_node.action_history
    )