from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.legal_actions import (
    BettingAction,
    legal_actions,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def _advance_to_postdraw(
    game: SingleDrawGame,
) -> None:
    while game.phase == GamePhase.PREDRAW_BETTING:
        state = game.betting_state
        acting_seat = state.acting_seat

        if acting_seat is None:
            raise RuntimeError(
                "Expected a pre-draw actor."
            )

        amount_to_call = state.amount_to_call(
            acting_seat
        )

        if amount_to_call > 0:
            game.apply_betting_action(
                ActionType.CALL
            )
        else:
            game.apply_betting_action(
                ActionType.CHECK
            )

    if game.phase != GamePhase.DRAW:
        raise RuntimeError(
            "Expected draw phase."
        )

    while game.phase == GamePhase.DRAW:
        acting_seat = game.draw_acting_seat

        if acting_seat is None:
            raise RuntimeError(
                "Expected a draw actor."
            )

        game.submit_draw(
            acting_seat,
            [],
        )

    if game.phase != GamePhase.POSTDRAW_BETTING:
        raise RuntimeError(
            "Expected post-draw betting phase."
        )


def test_postdraw_call_uses_current_round_commitment() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    _advance_to_postdraw(game)

    first_seat = game.acting_seat

    if first_seat is None:
        raise RuntimeError(
            "Expected first post-draw actor."
        )

    game.apply_betting_action(
        ActionType.RAISE,
        raise_to=2.0,
    )

    second_seat = game.acting_seat

    if second_seat is None:
        raise RuntimeError(
            "Expected second post-draw actor."
        )

    second_player = (
        game.betting_state.players[
            second_seat
        ]
    )

    assert (
        second_player.committed_total
        > 0
    )

    assert (
        second_player.committed_this_round
        == 0.0
    )

    actions = legal_actions(
        game,
        raise_sizes=(),
    )

    assert BettingAction(
        ActionType.FOLD
    ) in actions

    assert BettingAction(
        ActionType.CALL
    ) in actions

    assert BettingAction(
        ActionType.CHECK
    ) not in actions


def test_postdraw_amount_to_call_is_round_specific() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    _advance_to_postdraw(game)

    first_seat = game.acting_seat

    if first_seat is None:
        raise RuntimeError(
            "Expected first post-draw actor."
        )

    game.apply_betting_action(
        ActionType.RAISE,
        raise_to=2.0,
    )

    second_seat = game.acting_seat

    if second_seat is None:
        raise RuntimeError(
            "Expected second post-draw actor."
        )

    amount_to_call = (
        game.betting_state.amount_to_call(
            second_seat
        )
    )

    assert amount_to_call == 2.0


def test_postdraw_maximum_raise_to_uses_round_commitment() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=10.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    _advance_to_postdraw(game)

    acting_seat = game.acting_seat

    if acting_seat is None:
        raise RuntimeError(
            "Expected post-draw actor."
        )

    player = (
        game.betting_state.players[
            acting_seat
        ]
    )

    maximum_raise_to = (
        game.betting_state.maximum_raise_to(
            acting_seat
        )
    )

    assert maximum_raise_to == player.stack


def test_postdraw_raise_action_respects_available_stack() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=10.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    _advance_to_postdraw(game)

    acting_seat = game.acting_seat

    if acting_seat is None:
        raise RuntimeError(
            "Expected post-draw actor."
        )

    player = (
        game.betting_state.players[
            acting_seat
        ]
    )

    legal_raise_to = player.stack

    actions = legal_actions(
        game,
        raise_sizes=(
            legal_raise_to,
            legal_raise_to + 1.0,
        ),
    )

    assert BettingAction(
        ActionType.RAISE,
        raise_to=legal_raise_to,
    ) in actions

    assert BettingAction(
        ActionType.RAISE,
        raise_to=legal_raise_to + 1.0,
    ) not in actions


def test_empty_raise_sizes_produces_no_raise_actions() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    _advance_to_postdraw(game)

    actions = legal_actions(
        game,
        raise_sizes=(),
    )

    assert all(
        not (
            isinstance(
                action,
                BettingAction,
            )
            and action.action_type
            == ActionType.RAISE
        )
        for action in actions
    )