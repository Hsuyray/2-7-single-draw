from solver.game_state import (
    GameConfig,
)
from solver.information_state import (
    InformationState,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.single_draw_game import (
    SingleDrawGame,
)


def test_information_state_contains_public_node() -> None:
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

    state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    assert isinstance(
        state.public_node,
        PublicNodeKey,
    )


def test_two_observers_share_same_public_node() -> None:
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

    first = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    second = (
        InformationState.from_game(
            game,
            observer_seat=1,
            abstraction="exact",
        )
    )

    assert (
        first.public_node
        == second.public_node
    )

    assert (
        first.own_hand_key
        != second.own_hand_key
    )


def test_compatibility_properties_match_public_node() -> None:
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

    state = (
        InformationState.from_game(
            game,
            observer_seat=0,
            abstraction="exact",
        )
    )

    assert (
        state.phase
        == state.public_node.phase
    )

    assert (
        state.acting_seat
        == state.public_node.acting_seat
    )

    assert (
        state.button_seat
        == state.public_node.button_seat
    )

    assert (
        state.pot
        == state.public_node.pot
    )

    assert (
        state.players
        == state.public_node.players
    )

    assert (
        state.action_history
        == state.public_node.action_history
    )