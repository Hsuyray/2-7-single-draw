import pytest

from solver.game_state import ActionType, GameConfig
from solver.hand import Hand
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)
from solver.terminal_utility import (
    terminal_utilities,
    terminal_utility,
)


def make_heads_up_game(
    *,
    starting_stack: float = 100.0,
) -> SingleDrawGame:
    config = GameConfig(
        player_count=2,
        starting_stack=starting_stack,
        small_blind=1.0,
        big_blind=2.0,
    )

    return SingleDrawGame(
        config=config,
        button_seat=0,
        shuffle_deck=False,
    )


def complete_predraw_by_fold(
    game: SingleDrawGame,
) -> None:
    game.apply_betting_action(
        ActionType.FOLD
    )

    assert game.phase == GamePhase.COMPLETE


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


def complete_draw_with_stand_pat(
    game: SingleDrawGame,
) -> None:
    while game.phase == GamePhase.DRAW:
        acting_seat = game.draw_acting_seat

        assert acting_seat is not None

        game.submit_draw(
            seat=acting_seat,
            discard_indices=[],
        )


def complete_postdraw_with_checks(
    game: SingleDrawGame,
) -> None:
    while game.phase == GamePhase.POSTDRAW_BETTING:
        game.apply_betting_action(
            ActionType.CHECK
        )


def test_non_terminal_game_has_no_terminal_utilities() -> None:
    game = make_heads_up_game()

    with pytest.raises(ValueError):
        terminal_utilities(game)


def test_fold_terminal_utilities() -> None:
    game = make_heads_up_game()

    complete_predraw_by_fold(game)

    utilities = terminal_utilities(game)

    assert utilities[0] == pytest.approx(-1.0)
    assert utilities[1] == pytest.approx(1.0)


def test_terminal_utility_returns_one_seat() -> None:
    game = make_heads_up_game()

    complete_predraw_by_fold(game)

    assert terminal_utility(
        game,
        seat=0,
    ) == pytest.approx(-1.0)

    assert terminal_utility(
        game,
        seat=1,
    ) == pytest.approx(1.0)


def test_terminal_utilities_sum_to_zero() -> None:
    game = make_heads_up_game()

    complete_predraw_by_fold(game)

    utilities = terminal_utilities(game)

    assert sum(utilities) == pytest.approx(0.0)


def test_showdown_winner_utility() -> None:
    game = make_heads_up_game()

    enter_draw_phase(game)

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "8s",
        "6h",
        "4c",
        "3d",
        "2h",
    )

    complete_draw_with_stand_pat(game)
    complete_postdraw_with_checks(game)

    assert game.phase == GamePhase.COMPLETE

    utilities = terminal_utilities(game)

    assert utilities[0] == pytest.approx(3.5)
    assert utilities[1] == pytest.approx(-3.5)


def test_tied_showdown_splits_pot() -> None:
    game = make_heads_up_game()

    enter_draw_phase(game)

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "7h",
        "5d",
        "4c",
        "3s",
        "2h",
    )

    complete_draw_with_stand_pat(game)
    complete_postdraw_with_checks(game)

    utilities = terminal_utilities(game)

    assert utilities[0] == pytest.approx(0.75)
    assert utilities[1] == pytest.approx(-0.75)
    assert sum(utilities) == pytest.approx(0.0)


def test_invalid_positive_seat_is_rejected() -> None:
    game = make_heads_up_game()

    complete_predraw_by_fold(game)

    with pytest.raises(ValueError):
        terminal_utility(
            game,
            seat=2,
        )


def test_negative_seat_is_rejected() -> None:
    game = make_heads_up_game()

    complete_predraw_by_fold(game)

    with pytest.raises(ValueError):
        terminal_utility(
            game,
            seat=-1,
        )


def test_different_starting_stacks_are_supported() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        starting_stacks=(
            50.0,
            100.0,
        ),
        small_blind=1.0,
        big_blind=2.0,
    )

    game = SingleDrawGame(
        config=config,
        button_seat=0,
        shuffle_deck=False,
    )

    complete_predraw_by_fold(game)

    utilities = terminal_utilities(game)

    assert utilities[0] == pytest.approx(-1.0)
    assert utilities[1] == pytest.approx(1.0)
    assert sum(utilities) == pytest.approx(0.0)