"""
Regression tests for two previously fixed bugs.

1. solver/game_state.py used exact float equality for
   betting-round termination and all-in detection. Float
   residue caused endless betting loops / RecursionError
   under full bet sizing. Both now use CHIP_EPSILON.

2. solver/hand_strategy_resolver.py used the wrong bucket
   type for postdraw lookups. Postdraw lookups must use
   PostdrawStrengthBucket, the same key training uses.

3. (day70) solver/game_state.py ended a betting round when at
   most one player was neither folded nor all-in, even if that
   player still owed chips: a player facing an all-in never got
   to call or fold. See section 3 at the bottom of this file.
"""

from types import SimpleNamespace

import pytest

from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.game_state import (
    CHIP_EPSILON,
    ActionType,
    GameConfig,
    GameState,
)
from solver.hand import Hand
from solver.hand_strategy_resolver import (
    HandStrategyResolver,
)
from solver.information_state import (
    _private_hand_key,
)
from solver.made_hand_bucket import (
    MadeHandBucket,
)
from solver.postdraw_strength_bucket import (
    PostdrawStrengthBucket,
    postdraw_strength_bucket,
)
from solver.single_draw_game import (
    GamePhase,
)


# --- 1. float near-equality in game_state ---


def make_heads_up_state(
    *,
    starting_stack: float = 100.0,
) -> GameState:
    return GameState(
        config=GameConfig(
            player_count=2,
            starting_stack=starting_stack,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=0.0,
        ),
        button_seat=0,
    )


@pytest.mark.parametrize(
    "residue",
    [
        1e-12,
        -1e-12,
    ],
)
def test_betting_round_completes_despite_float_residue(
    residue: float,
) -> None:
    assert abs(residue) < CHIP_EPSILON

    state = make_heads_up_state()

    # Button / small blind completes to 2.0.
    state.apply_action(ActionType.CALL)

    assert state.acting_seat == 1
    assert not state.betting_round_complete

    # Inject float residue into the caller's
    # commitment, as accumulated fractional bet
    # sizes can produce.
    state.players[0].committed_this_round = (
        state.current_bet + residue
    )

    # Big blind checks. With exact equality the
    # round would never close.
    state.apply_action(ActionType.CHECK)

    assert state.betting_round_complete
    assert state.acting_seat is None
    assert state.legal_actions() == set()


def test_betting_round_still_open_for_real_difference() -> None:
    state = make_heads_up_state()

    state.apply_action(ActionType.CALL)

    state.players[0].committed_this_round = (
        state.current_bet - 0.5
    )

    state.apply_action(ActionType.CHECK)

    assert not state.betting_round_complete
    assert state.acting_seat == 0


def test_all_in_raise_within_epsilon_of_stack_is_accepted() -> None:
    # Seat 0 posts 1.0 of a 3.0 stack, so its maximum
    # raise-to is 3.0: a short all-in below the 4.0
    # minimum raise-to.
    state = make_heads_up_state(
        starting_stack=3.0,
    )

    assert state.maximum_raise_to(0) == 3.0
    assert state.minimum_raise_to() == 4.0

    raise_to = 3.0 - 1e-12

    # With exact equality this was not recognised as
    # all-in and raised "smaller than the minimum
    # raise".
    state.apply_action(
        ActionType.RAISE,
        raise_to=raise_to,
    )

    assert state.current_bet == pytest.approx(3.0)
    assert state.acting_seat == 1


# --- 2. postdraw lookup bucket type ---


def make_hand() -> Hand:
    return Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )


def test_bucket_postdraw_lookup_uses_postdraw_strength_bucket() -> None:
    hand = make_hand()

    result = HandStrategyResolver(
        abstraction="bucket"
    ).resolve(
        hand=hand,
        phase=GamePhase.POSTDRAW_BETTING,
    )

    assert isinstance(
        result,
        PostdrawStrengthBucket,
    )
    assert not isinstance(
        result,
        MadeHandBucket,
    )
    assert result == postdraw_strength_bucket(
        hand
    )


@pytest.mark.parametrize(
    "phase",
    [
        GamePhase.PREDRAW_BETTING,
        GamePhase.DRAW,
    ],
)
def test_bucket_non_postdraw_lookup_uses_draw_bucket(
    phase: GamePhase,
) -> None:
    hand = make_hand()

    result = HandStrategyResolver(
        abstraction="bucket"
    ).resolve(
        hand=hand,
        phase=phase,
    )

    assert isinstance(
        result,
        DrawHandBucket,
    )
    assert result == draw_hand_bucket(
        hand
    )


@pytest.mark.parametrize(
    "phase",
    [
        GamePhase.PREDRAW_BETTING,
        GamePhase.DRAW,
        GamePhase.POSTDRAW_BETTING,
    ],
)
def test_resolver_key_matches_training_key(
    phase: GamePhase,
) -> None:
    """
    Evaluation lookups must use the same private
    hand key that training stores in
    InformationState.own_hand_key.
    """
    hand = make_hand()

    fake_game = SimpleNamespace(
        hands=[
            hand,
            None,
        ],
        phase=phase,
    )

    training_key = _private_hand_key(
        game=fake_game,  # type: ignore[arg-type]
        observer_seat=0,
        abstraction="bucket",
    )

    lookup_key = HandStrategyResolver(
        abstraction="bucket"
    ).resolve(
        hand=hand,
        phase=phase,
    )

    assert lookup_key == training_key
    assert type(lookup_key) is type(training_key)


# ---------------------------------------------------------------------------
# 3. All-in round completion (day70, docs/proposals/ENGINE-all-in-round.md).
#    BettingState._is_betting_round_complete ended the round when at most one
#    player was neither folded nor all-in, even if that player had not matched
#    the bet: a player facing an all-in never got to call or fold.
# ---------------------------------------------------------------------------

from solver.bet_sizing import FULL_BET_SIZING
from solver.legal_actions import legal_actions as _game_legal_actions
from solver.single_draw_game import GamePhase, SingleDrawGame
from solver.terminal_utility import terminal_utilities


def _all_in_game(
    *,
    player_count: int = 2,
    starting_stacks: tuple[float, ...] | None = None,
    deck_seed: int = 1,
) -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=player_count,
            starting_stack=20.0,
            starting_stacks=starting_stacks,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=deck_seed,
    )


def _action_types(game: SingleDrawGame) -> set[ActionType]:
    return {
        action.action_type
        for action in _game_legal_actions(
            game,
            max_draw=5,
            raise_sizes=None,
            bet_sizing_policy=FULL_BET_SIZING,
        )
    }


def _play_out_draws_and_check(game: SingleDrawGame) -> None:
    while game.phase == GamePhase.DRAW:
        game.submit_draw(game.draw_acting_seat, [])

    while game.phase == GamePhase.POSTDRAW_BETTING:
        game.apply_betting_action(ActionType.CHECK)


def test_player_facing_an_all_in_must_respond() -> None:
    game = _all_in_game()

    # BTN (seat 0) shoves: raise to 20 = all of its chips.
    game.apply_betting_action(ActionType.RAISE, raise_to=20.0)

    assert game.phase == GamePhase.PREDRAW_BETTING
    assert game.acting_seat == 1
    # Nobody could call a re-raise: only fold or call.
    assert _action_types(game) == {ActionType.FOLD, ActionType.CALL}
    assert game.betting_state.legal_actions() == {
        ActionType.FOLD,
        ActionType.CALL,
    }


def test_calling_an_all_in_plays_for_full_stacks() -> None:
    for deck_seed in (1, 2, 3):
        game = _all_in_game(deck_seed=deck_seed)
        game.apply_betting_action(ActionType.RAISE, raise_to=20.0)
        game.apply_betting_action(ActionType.CALL)

        # Both all-in: both draw, then straight to showdown.
        assert game.phase == GamePhase.DRAW
        assert game.draw_order == [1, 0]
        game.submit_draw(1, [])
        game.submit_draw(0, [])
        assert game.phase == GamePhase.COMPLETE

        utilities = terminal_utilities(game)
        assert abs(sum(utilities)) <= CHIP_EPSILON
        # The whole effective stack is at stake, not just the blinds.
        # BB's 20 = 1.5 ante (dead money) + 18.5 live; BTN's extra
        # 1.5 is uncalled and returned. BTN wins 20 or loses 18.5.
        assert any(
            abs(utilities[0] - expected) <= CHIP_EPSILON
            for expected in (20.0, -18.5, 0.75)
        ), utilities


def test_folding_to_an_all_in_gives_btn_the_pot() -> None:
    game = _all_in_game()
    game.apply_betting_action(ActionType.RAISE, raise_to=20.0)
    game.apply_betting_action(ActionType.FOLD)

    assert game.phase == GamePhase.COMPLETE
    utilities = terminal_utilities(game)
    # BTN wins the BB's blind + ante; its uncalled shove is returned.
    assert abs(utilities[0] - 3.5) <= CHIP_EPSILON
    assert abs(utilities[1] + 3.5) <= CHIP_EPSILON


def test_bigger_stack_facing_short_all_in_can_only_call_or_fold() -> None:
    # BTN has 10, BB has 30: BTN's shove cannot be re-raised.
    game = _all_in_game(starting_stacks=(10.0, 30.0))
    game.apply_betting_action(ActionType.RAISE, raise_to=10.0)

    assert game.acting_seat == 1
    assert _action_types(game) == {ActionType.FOLD, ActionType.CALL}

    game.apply_betting_action(ActionType.CALL)
    assert game.phase == GamePhase.DRAW
    _play_out_draws_and_check(game)
    utilities = terminal_utilities(game)
    assert abs(sum(utilities)) <= CHIP_EPSILON
    # The covered BTN can win or lose at most its own stack plus
    # the BB's matching contribution.
    assert abs(utilities[0]) <= 10.0 + 1.5 + CHIP_EPSILON


def test_short_stack_calling_all_in_for_less_gets_excess_back() -> None:
    # BTN 30 shoves; BB (20) calls all-in for less.
    game = _all_in_game(starting_stacks=(30.0, 20.0))
    game.apply_betting_action(ActionType.RAISE, raise_to=30.0)
    assert _action_types(game) == {ActionType.FOLD, ActionType.CALL}
    game.apply_betting_action(ActionType.CALL)

    _play_out_draws_and_check(game)
    utilities = terminal_utilities(game)
    assert abs(sum(utilities)) <= CHIP_EPSILON
    # BB can lose at most its own 20.
    assert abs(utilities[1]) <= 20.0 + CHIP_EPSILON


def test_three_handed_last_player_owing_chips_is_asked() -> None:
    # Seats: 0 = BTN, 1 = SB, 2 = BB. BTN shoves, SB calls all-in;
    # BB is the only player left who can act and still owes chips.
    game = _all_in_game(player_count=3)
    game.apply_betting_action(ActionType.RAISE, raise_to=20.0)
    game.apply_betting_action(ActionType.CALL)

    assert game.phase == GamePhase.PREDRAW_BETTING
    assert game.acting_seat == 2
    assert _action_types(game) == {ActionType.FOLD, ActionType.CALL}

    game.apply_betting_action(ActionType.FOLD)
    assert game.phase == GamePhase.DRAW
    _play_out_draws_and_check(game)
    assert abs(sum(terminal_utilities(game))) <= CHIP_EPSILON


def test_normal_raise_still_allows_reraise() -> None:
    game = _all_in_game()
    game.apply_betting_action(ActionType.RAISE, raise_to=6.0)

    assert game.acting_seat == 1
    assert ActionType.RAISE in _action_types(game)
