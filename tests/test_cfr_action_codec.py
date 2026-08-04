from solver.actions import (
    DiscardAction,
)
from solver.cfr_action_codec import (
    canonical_solver_actions_for_game,
    executable_solver_action_for_game,
)
from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.hand import (
    Hand,
)
from solver.legal_actions import (
    legal_actions,
)
from solver.single_draw_game import (
    SingleDrawGame,
)


def make_draw_game() -> SingleDrawGame:
    game = SingleDrawGame(
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

    game.apply_betting_action(
        ActionType.CALL
    )

    game.apply_betting_action(
        ActionType.CHECK
    )

    acting_seat = game.acting_seat

    assert acting_seat is not None

    game.hands[
        acting_seat
    ] = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    return game


def test_actual_action_maps_to_canonical_action() -> None:
    game = make_draw_game()

    actual_action = DiscardAction(
        (4,)
    )

    result = (
        canonical_solver_actions_for_game(
            game=game,
            actions=(
                actual_action,
            ),
        )
    )

    assert result == (
        DiscardAction(
            (3,)
        ),
    )


def test_canonical_action_maps_back_to_actual_action() -> None:
    game = make_draw_game()

    canonical_action = DiscardAction(
        (3,)
    )

    result = (
        executable_solver_action_for_game(
            game=game,
            action=canonical_action,
        )
    )

    assert result == (
        DiscardAction(
            (4,)
        )
    )


def test_action_mapping_round_trip() -> None:
    game = make_draw_game()

    original_action = DiscardAction(
        (
            0,
            4,
        )
    )

    canonical_action = (
        canonical_solver_actions_for_game(
            game=game,
            actions=(
                original_action,
            ),
        )[0]
    )

    restored_action = (
        executable_solver_action_for_game(
            game=game,
            action=canonical_action,
        )
    )

    assert restored_action == (
        original_action
    )


def test_full_legal_action_set_remains_unique() -> None:
    game = make_draw_game()

    actual_actions = legal_actions(
        game,
        max_draw=2,
        raise_sizes=(),
        draw_action_mode="full",
    )

    canonical_actions = (
        canonical_solver_actions_for_game(
            game=game,
            actions=actual_actions,
        )
    )

    assert len(
        canonical_actions
    ) == len(
        set(canonical_actions)
    )

    assert len(
        canonical_actions
    ) == len(
        actual_actions
    )


def test_stand_pat_is_preserved() -> None:
    game = make_draw_game()

    stand_pat = DiscardAction(
        ()
    )

    canonical_actions = (
        canonical_solver_actions_for_game(
            game=game,
            actions=(
                stand_pat,
            ),
        )
    )

    assert canonical_actions == (
        stand_pat,
    )

    executable_action = (
        executable_solver_action_for_game(
            game=game,
            action=stand_pat,
        )
    )

    assert executable_action == (
        stand_pat
    )