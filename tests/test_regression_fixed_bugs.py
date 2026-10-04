"""
Regression tests for two previously fixed bugs.

1. solver/game_state.py used exact float equality for
   betting-round termination and all-in detection. Float
   residue caused endless betting loops / RecursionError
   under full bet sizing. Both now use CHIP_EPSILON.

2. solver/hand_strategy_resolver.py used the wrong bucket
   type for postdraw lookups. Postdraw lookups must use
   PostdrawStrengthBucket, the same key training uses.
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
