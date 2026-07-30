from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.public_node_navigator import (
    PublicNodeNavigator,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def make_game() -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=100.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=42,
    )


def test_navigator_exposes_initial_public_node() -> None:
    game = make_game()

    navigator = (
        PublicNodeNavigator.from_game(
            game
        )
    )

    node = navigator.public_node()

    assert (
        node.phase
        == GamePhase.PREDRAW_BETTING.value
    )

    assert (
        node.acting_seat
        == game.acting_seat
    )


def test_navigator_copies_game_by_default() -> None:
    game = make_game()

    navigator = (
        PublicNodeNavigator.from_game(
            game
        )
    )

    navigator.apply_betting(
        ActionType.CALL
    )

    assert (
        game.phase
        == GamePhase.PREDRAW_BETTING
    )

    assert len(
        game.action_history
    ) == 0


def test_betting_action_moves_to_next_public_node() -> None:
    game = make_game()

    navigator = (
        PublicNodeNavigator.from_game(
            game
        )
    )

    before = navigator.public_node()

    after = navigator.apply_betting(
        ActionType.CALL
    )

    assert before != after

    assert len(
        after.action_history
    ) == 1


def test_predraw_call_and_check_reach_draw_phase() -> None:
    navigator = (
        PublicNodeNavigator.from_game(
            make_game()
        )
    )

    navigator.apply_betting(
        ActionType.CALL
    )

    node = navigator.apply_betting(
        ActionType.CHECK
    )

    assert (
        navigator.phase
        == GamePhase.DRAW
    )

    assert (
        node.phase
        == GamePhase.DRAW.value
    )


def test_draw_action_moves_to_next_player() -> None:
    navigator = (
        PublicNodeNavigator.from_game(
            make_game()
        )
    )

    navigator.apply_betting(
        ActionType.CALL
    )

    navigator.apply_betting(
        ActionType.CHECK
    )

    first_drawer = (
        navigator.acting_seat
    )

    node = navigator.apply_draw(
        discard_indices=(),
    )

    assert (
        first_drawer
        is not None
    )

    assert (
        node.acting_seat
        != first_drawer
    )


def test_two_draw_actions_reach_postdraw() -> None:
    navigator = (
        PublicNodeNavigator.from_game(
            make_game()
        )
    )

    navigator.apply_betting(
        ActionType.CALL
    )

    navigator.apply_betting(
        ActionType.CHECK
    )

    navigator.apply_draw(
        discard_indices=(),
    )

    node = navigator.apply_draw(
        discard_indices=(),
    )

    assert (
        navigator.phase
        == GamePhase.POSTDRAW_BETTING
    )

    assert (
        node.phase
        == GamePhase.POSTDRAW_BETTING.value
    )


def test_public_history_tracks_draw_counts() -> None:
    navigator = (
        PublicNodeNavigator.from_game(
            make_game()
        )
    )

    navigator.apply_betting(
        ActionType.CALL
    )

    navigator.apply_betting(
        ActionType.CHECK
    )

    node = navigator.apply_draw(
        discard_indices=(4,)
    )

    draw_actions = [
        action
        for action
        in node.action_history
        if action.phase
        == GamePhase.DRAW.value
    ]

    assert len(
        draw_actions
    ) == 1

    assert (
        draw_actions[0].draw_count
        == 1
    )


def test_clone_is_independent() -> None:
    navigator = (
        PublicNodeNavigator.from_game(
            make_game()
        )
    )

    clone = navigator.clone()

    clone.apply_betting(
        ActionType.CALL
    )

    assert (
        len(
            navigator.public_node().action_history
        )
        == 0
    )

    assert (
        len(
            clone.public_node().action_history
        )
        == 1
    )


def test_draw_action_rejected_during_betting() -> None:
    navigator = (
        PublicNodeNavigator.from_game(
            make_game()
        )
    )

    try:
        navigator.apply_draw(
            discard_indices=(),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Expected RuntimeError."
        )


def test_betting_action_rejected_during_draw() -> None:
    navigator = (
        PublicNodeNavigator.from_game(
            make_game()
        )
    )

    navigator.apply_betting(
        ActionType.CALL
    )

    navigator.apply_betting(
        ActionType.CHECK
    )

    try:
        navigator.apply_betting(
            ActionType.CHECK
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Expected RuntimeError."
        )