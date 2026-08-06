from solver.actions import (
    DiscardAction,
)
from solver.bucket_action_codec import (
    bucket_solver_actions_for_game,
    executable_bucket_action_for_game,
)
from solver.bucket_hand_codec import (
    actual_discard_action_for_bucket_hand,
    bucket_discard_action_for_hand,
    bucket_hand_encoding,
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


def make_draw_game(
    *,
    hand: Hand,
) -> SingleDrawGame:
    game = SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=20.0,
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
    ] = hand

    return game


def test_bucket_encoding_tracks_both_directions() -> None:
    hand = Hand.from_strings(
        "Tc",
        "2c",
        "8s",
        "4d",
        "6h",
    )

    encoding = bucket_hand_encoding(
        hand
    )

    assert (
        encoding.bucket_to_original
        == (
            1,
            3,
            4,
            2,
            0,
        )
    )

    assert (
        encoding.original_to_bucket
        == (
            4,
            0,
            3,
            1,
            2,
        )
    )


def test_actual_action_maps_to_bucket_action() -> None:
    hand = Hand.from_strings(
        "Tc",
        "2c",
        "8s",
        "4d",
        "6h",
    )

    action = (
        bucket_discard_action_for_hand(
            hand=hand,
            action=DiscardAction(
                (0,)
            ),
        )
    )

    assert action == DiscardAction(
        (4,)
    )


def test_bucket_action_maps_to_actual_action() -> None:
    hand = Hand.from_strings(
        "Tc",
        "2c",
        "8s",
        "4d",
        "6h",
    )

    action = (
        actual_discard_action_for_bucket_hand(
            hand=hand,
            action=DiscardAction(
                (4,)
            ),
        )
    )

    assert action == DiscardAction(
        (0,)
    )


def test_bucket_action_round_trip() -> None:
    hand = Hand.from_strings(
        "Tc",
        "2c",
        "8s",
        "4d",
        "6h",
    )

    original = DiscardAction(
        (
            0,
            3,
        )
    )

    bucket_action = (
        bucket_discard_action_for_hand(
            hand=hand,
            action=original,
        )
    )

    restored = (
        actual_discard_action_for_bucket_hand(
            hand=hand,
            action=bucket_action,
        )
    )

    assert restored == original


def test_bucket_legal_actions_are_sorted() -> None:
    game = make_draw_game(
        hand=Hand.from_strings(
            "Tc",
            "2c",
            "8s",
            "4d",
            "6h",
        )
    )

    actions = legal_actions(
        game,
        max_draw=2,
        raise_sizes=(),
        draw_action_mode="full",
    )

    bucket_actions = (
        bucket_solver_actions_for_game(
            game=game,
            actions=actions,
        )
    )

    assert bucket_actions == tuple(
        sorted(
            bucket_actions,
            key=lambda action: (
                action.draw_count,
                action.discard_indices,
            ),
        )
    )


def test_similar_bucket_hands_have_same_actions() -> None:
    first_game = make_draw_game(
        hand=Hand.from_strings(
            "Tc",
            "2c",
            "8s",
            "4d",
            "6h",
        )
    )

    second_game = make_draw_game(
        hand=Hand.from_strings(
            "7s",
            "Jd",
            "3d",
            "9c",
            "5h",
        )
    )

    first_actual = legal_actions(
        first_game,
        max_draw=2,
        raise_sizes=(),
        draw_action_mode="full",
    )

    second_actual = legal_actions(
        second_game,
        max_draw=2,
        raise_sizes=(),
        draw_action_mode="full",
    )

    first_bucket = (
        bucket_solver_actions_for_game(
            game=first_game,
            actions=first_actual,
        )
    )

    second_bucket = (
        bucket_solver_actions_for_game(
            game=second_game,
            actions=second_actual,
        )
    )

    assert first_bucket == second_bucket


def test_executable_bucket_action_uses_actual_index() -> None:
    game = make_draw_game(
        hand=Hand.from_strings(
            "Tc",
            "2c",
            "8s",
            "4d",
            "6h",
        )
    )

    executable = (
        executable_bucket_action_for_game(
            game=game,
            action=DiscardAction(
                (4,)
            ),
        )
    )

    assert executable == DiscardAction(
        (0,)
    )


def test_stand_pat_is_preserved() -> None:
    hand = Hand.from_strings(
        "Tc",
        "2c",
        "8s",
        "4d",
        "6h",
    )

    action = (
        bucket_discard_action_for_hand(
            hand=hand,
            action=DiscardAction(
                ()
            ),
        )
    )

    assert action == DiscardAction(
        ()
    )