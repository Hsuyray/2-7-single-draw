from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def test_public_node_is_hashable() -> None:
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

    node = PublicNodeKey.from_game(
        game
    )

    assert isinstance(
        hash(node),
        int,
    )


def test_public_node_contains_no_private_hands() -> None:
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

    node = PublicNodeKey.from_game(
        game
    )

    assert not hasattr(
        node,
        "hands",
    )

    assert not hasattr(
        node,
        "own_hand_key",
    )


def test_public_node_tracks_phase() -> None:
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

    node = PublicNodeKey.from_game(
        game
    )

    assert (
        node.phase
        == GamePhase.PREDRAW_BETTING.value
    )


def test_public_node_tracks_action_history() -> None:
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

    node = PublicNodeKey.from_game(
        game
    )

    assert len(
        node.action_history
    ) == 1


def test_same_public_state_with_different_hands_has_same_node() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    first_game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=1,
    )

    second_game = SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=2,
    )

    first_node = (
        PublicNodeKey.from_game(
            first_game
        )
    )

    second_node = (
        PublicNodeKey.from_game(
            second_game
        )
    )

    assert (
        first_node
        == second_node
    )