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
    while (
        game.phase
        == GamePhase.PREDRAW_BETTING
    ):
        state = game.betting_state
        acting_seat = (
            state.acting_seat
        )

        if acting_seat is None:
            raise RuntimeError(
                "Expected a pre-draw actor."
            )

        amount_to_call = (
            state.amount_to_call(
                acting_seat
            )
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
        acting_seat = (
            game.draw_acting_seat
        )

        if acting_seat is None:
            raise RuntimeError(
                "Expected a draw actor."
            )

        game.submit_draw(
            acting_seat,
            [],
        )

    if (
        game.phase
        != GamePhase.POSTDRAW_BETTING
    ):
        raise RuntimeError(
            "Expected post-draw "
            "betting phase."
        )


def _make_postdraw_game(
    *,
    starting_stack: float = 100.0,
) -> SingleDrawGame:
    config = GameConfig(
        player_count=2,
        starting_stack=starting_stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    _advance_to_postdraw(
        game
    )

    return game


def _raise_actions(
    game: SingleDrawGame,
    *,
    raise_sizes: (
        tuple[float, ...]
        | None
    ),
) -> list[BettingAction]:
    actions = legal_actions(
        game,
        raise_sizes=raise_sizes,
    )

    return [
        action
        for action in actions
        if (
            isinstance(
                action,
                BettingAction,
            )
            and action.action_type
            == ActionType.RAISE
        )
    ]


def test_postdraw_call_uses_current_round_commitment() -> None:
    game = _make_postdraw_game()

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
    game = _make_postdraw_game()

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
    game = _make_postdraw_game(
        starting_stack=10.0,
    )

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

    assert (
        maximum_raise_to
        == player.stack
    )


def test_postdraw_raise_action_respects_available_stack() -> None:
    game = _make_postdraw_game(
        starting_stack=10.0,
    )

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

    legal_raise_to = (
        player.stack
    )

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
        raise_to=(
            legal_raise_to + 1.0
        ),
    ) not in actions


def test_empty_raise_sizes_produces_no_raise_actions() -> None:
    game = _make_postdraw_game()

    raises = _raise_actions(
        game,
        raise_sizes=(),
    )

    assert raises == []


def test_none_raise_sizes_use_bet_sizing_policy() -> None:
    game = _make_postdraw_game()

    raises = _raise_actions(
        game,
        raise_sizes=None,
    )

    assert raises


def test_default_policy_generates_multiple_raise_sizes() -> None:
    game = _make_postdraw_game()

    raises = _raise_actions(
        game,
        raise_sizes=None,
    )

    assert len(raises) > 1


def test_default_policy_raise_sizes_are_legal() -> None:
    game = _make_postdraw_game()

    raises = _raise_actions(
        game,
        raise_sizes=None,
    )

    state = game.betting_state

    acting_seat = (
        state.acting_seat
    )

    if acting_seat is None:
        raise RuntimeError(
            "Expected post-draw actor."
        )

    minimum_raise_to = (
        state.minimum_raise_to()
    )

    maximum_raise_to = (
        state.maximum_raise_to(
            acting_seat
        )
    )

    for action in raises:
        assert action.raise_to is not None

        assert (
            action.raise_to
            <= maximum_raise_to
        )

        assert (
            action.raise_to
            >= minimum_raise_to
            or action.raise_to
            == maximum_raise_to
        )


def test_explicit_raise_sizes_override_policy() -> None:
    game = _make_postdraw_game()

    raises = _raise_actions(
        game,
        raise_sizes=(
            6.0,
        ),
    )

    assert raises == [
        BettingAction(
            ActionType.RAISE,
            raise_to=6.0,
        )
    ]


def test_explicit_empty_tuple_does_not_use_policy() -> None:
    game = _make_postdraw_game()

    policy_raises = _raise_actions(
        game,
        raise_sizes=None,
    )

    disabled_raises = _raise_actions(
        game,
        raise_sizes=(),
    )

    assert policy_raises

    assert (
        disabled_raises
        == []
    )