"""
Known engine bugs, recorded as strict expected failures.

Each test asserts the CORRECT behaviour and is marked xfail(strict=True):
it fails today as expected; once the bug is fixed it passes, strict
mode turns that into a failure, and the marker must be removed (the
test then guards against a regression).

See docs/proposals/ENGINE-all-in-round.md.
"""

import pytest

from solver.bet_sizing import FULL_BET_SIZING
from solver.game_state import ActionType, GameConfig
from solver.legal_actions import legal_actions
from solver.single_draw_game import GamePhase, SingleDrawGame


def heads_up_game() -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=20.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=1,
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BettingState._is_betting_round_complete ends the round "
        "when at most one player is neither folded nor all-in, "
        "even if that player has not matched the bet (day69)."
    ),
)
def test_player_facing_an_all_in_must_respond() -> None:
    game = heads_up_game()

    # BTN (seat 0) shoves: raise to 20 = all of its chips.
    game.apply_betting_action(ActionType.RAISE, raise_to=20.0)

    # BB has committed 2 of 20 and still has 16.5 behind:
    # it must be asked to call (all-in for less) or fold.
    assert game.phase == GamePhase.PREDRAW_BETTING
    assert game.acting_seat == 1

    actions = {
        action.action_type
        for action in legal_actions(
            game,
            max_draw=5,
            raise_sizes=None,
            bet_sizing_policy=FULL_BET_SIZING,
        )
    }

    assert ActionType.FOLD in actions
    assert ActionType.CALL in actions
