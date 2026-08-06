import pytest

from solver.cfr_trainer import (
    CFRTrainer,
)
from solver.draw_hand_bucket import (
    draw_hand_bucket,
)
from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.hand import (
    Hand,
)
from solver.information_state import (
    InformationState,
)
from solver.single_draw_game import (
    SingleDrawGame,
)


def make_draw_game(
    *,
    hand: Hand,
    seed: int,
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
        deck_seed=seed,
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


def make_bucket_trainer() -> CFRTrainer:
    return CFRTrainer(
        max_draw=2,
        raise_sizes=(),
        abstraction="bucket",
        traversal_mode=(
            "external_sampling"
        ),
        draw_action_mode="auto",
        random_seed=1,
    )


def test_bucket_auto_uses_full_draw_actions() -> None:
    trainer = make_bucket_trainer()

    assert (
        trainer.resolved_draw_action_mode
        == "full"
    )


def test_bucket_candidate_mode_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "requires full draw actions"
        ),
    ):
        CFRTrainer(
            abstraction="bucket",
            draw_action_mode="candidate",
        )


def test_similar_hands_share_draw_bucket() -> None:
    first = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Tc",
    )

    second = Hand.from_strings(
        "3d",
        "5h",
        "7s",
        "9c",
        "Jd",
    )

    assert (
        draw_hand_bucket(
            first
        )
        == draw_hand_bucket(
            second
        )
    )


def test_similar_hands_share_information_state() -> None:
    first_game = make_draw_game(
        hand=Hand.from_strings(
            "2c",
            "4d",
            "6h",
            "8s",
            "Tc",
        ),
        seed=1,
    )

    second_game = make_draw_game(
        hand=Hand.from_strings(
            "3d",
            "5h",
            "7s",
            "9c",
            "Jd",
        ),
        seed=2,
    )

    first_seat = (
        first_game.acting_seat
    )

    second_seat = (
        second_game.acting_seat
    )

    assert first_seat is not None
    assert second_seat is not None

    first_state = (
        InformationState.from_game(
            first_game,
            observer_seat=first_seat,
            abstraction="bucket",
        )
    )

    second_state = (
        InformationState.from_game(
            second_game,
            observer_seat=second_seat,
            abstraction="bucket",
        )
    )

    assert (
        first_state
        == second_state
    )


def test_bucket_hands_have_same_full_action_set() -> None:
    first_game = make_draw_game(
        hand=Hand.from_strings(
            "2c",
            "4d",
            "6h",
            "8s",
            "Tc",
        ),
        seed=1,
    )

    second_game = make_draw_game(
        hand=Hand.from_strings(
            "3d",
            "5h",
            "7s",
            "9c",
            "Jd",
        ),
        seed=2,
    )

    trainer = make_bucket_trainer()

    first_actions = (
        trainer._legal_actions(
            first_game
        )
    )

    second_actions = (
        trainer._legal_actions(
            second_game
        )
    )

    assert first_actions
    assert (
        first_actions
        == second_actions
    )


def test_bucket_hands_reuse_same_node() -> None:
    first_game = make_draw_game(
        hand=Hand.from_strings(
            "2c",
            "4d",
            "6h",
            "8s",
            "Tc",
        ),
        seed=1,
    )

    second_game = make_draw_game(
        hand=Hand.from_strings(
            "3d",
            "5h",
            "7s",
            "9c",
            "Jd",
        ),
        seed=2,
    )

    trainer = make_bucket_trainer()

    first_seat = (
        first_game.acting_seat
    )

    second_seat = (
        second_game.acting_seat
    )

    assert first_seat is not None
    assert second_seat is not None

    first_actions = (
        trainer._legal_actions(
            first_game
        )
    )

    second_actions = (
        trainer._legal_actions(
            second_game
        )
    )

    first_node = trainer._get_node(
        game=first_game,
        acting_seat=first_seat,
        actions=first_actions,
    )

    second_node = trainer._get_node(
        game=second_game,
        acting_seat=second_seat,
        actions=second_actions,
    )

    assert (
        first_node
        is second_node
    )

    assert len(
        trainer.node_store
    ) == 1