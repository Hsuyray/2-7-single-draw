from solver.actions import (
    DiscardAction,
)
from solver.cfr_trainer import (
    CFRTrainer,
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
    deck_seed: int,
) -> SingleDrawGame:
    game = SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=100.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=deck_seed,
    )

    game.apply_betting_action(
        ActionType.CALL
    )

    game.apply_betting_action(
        ActionType.CHECK
    )

    acting_seat = game.acting_seat

    assert acting_seat is not None

    # These tests inspect information-state
    # and CFR node identity only.
    #
    # They do not physically execute a draw,
    # so replacing the hand does not require
    # rebuilding the deck.
    game.hands[
        acting_seat
    ] = hand

    return game


def make_full_trainer() -> CFRTrainer:
    return CFRTrainer(
        max_draw=2,
        raise_sizes=(),
        abstraction="exact",
        traversal_mode="full",
        draw_action_mode="full",
        random_seed=1,
    )


def make_full_draw_trainer() -> CFRTrainer:
    return CFRTrainer(
        max_draw=3,
        raise_sizes=(),
        abstraction="exact",
        traversal_mode="full",
        draw_action_mode="full",
        random_seed=1,
    )


def make_suit_isomorphic_games() -> tuple[
    SingleDrawGame,
    SingleDrawGame,
]:
    first_game = make_draw_game(
        hand=Hand.from_strings(
            "2s",
            "4s",
            "6s",
            "7d",
            "7s",
        ),
        deck_seed=42,
    )

    second_game = make_draw_game(
        hand=Hand.from_strings(
            "2c",
            "4c",
            "6c",
            "7c",
            "7h",
        ),
        deck_seed=99,
    )

    return (
        first_game,
        second_game,
    )


def test_suit_isomorphic_hands_have_same_information_state() -> None:
    (
        first_game,
        second_game,
    ) = make_suit_isomorphic_games()

    first_seat = (
        first_game.acting_seat
    )

    second_seat = (
        second_game.acting_seat
    )

    assert first_seat is not None
    assert second_seat is not None
    assert first_seat == second_seat

    first_state = (
        InformationState.from_game(
            first_game,
            observer_seat=first_seat,
            abstraction="exact",
        )
    )

    second_state = (
        InformationState.from_game(
            second_game,
            observer_seat=second_seat,
            abstraction="exact",
        )
    )

    assert (
        first_state
        == second_state
    )


def test_full_mode_reuses_same_cfr_node() -> None:
    (
        first_game,
        second_game,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

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

    assert (
        first_actions
        == second_actions
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


def test_reused_node_has_one_canonical_action_set() -> None:
    (
        first_game,
        second_game,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

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

    assert (
        tuple(
            first_node.actions
        )
        == first_actions
    )

    assert (
        tuple(
            second_node.actions
        )
        == second_actions
    )

    assert (
        tuple(
            first_node.actions
        )
        == tuple(
            second_node.actions
        )
    )


def test_reused_node_strategy_uses_canonical_actions() -> None:
    (
        first_game,
        second_game,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

    acting_seat = (
        first_game.acting_seat
    )

    assert acting_seat is not None

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

    assert (
        first_actions
        == second_actions
    )

    node = trainer._get_node(
        game=first_game,
        acting_seat=acting_seat,
        actions=first_actions,
    )

    strategy = (
        node.current_strategy()
    )

    assert (
        set(
            strategy
        )
        == set(
            first_actions
        )
    )

    assert all(
        isinstance(
            action,
            DiscardAction,
        )
        for action in strategy
    )

    assert sum(
        strategy.values()
    ) == 1.0


def test_full_draw_actions_are_suit_isomorphic() -> None:
    (
        first_game,
        second_game,
    ) = make_suit_isomorphic_games()

    trainer = (
        make_full_draw_trainer()
    )

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


def test_full_draw_mode_reuses_same_node() -> None:
    (
        first_game,
        second_game,
    ) = make_suit_isomorphic_games()

    trainer = (
        make_full_draw_trainer()
    )

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

    assert (
        first_actions
        == second_actions
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


def test_full_mode_action_order_is_deterministic() -> None:
    (
        first_game,
        _,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

    first_result = (
        trainer._legal_actions(
            first_game
        )
    )

    second_result = (
        trainer._legal_actions(
            first_game
        )
    )

    assert (
        first_result
        == second_result
    )

    assert first_result == tuple(
        sorted(
            first_result,
            key=lambda action: (
                action.draw_count,
                action.discard_indices,
            ),
        )
    )


def test_full_mode_actions_are_unique() -> None:
    (
        first_game,
        _,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

    actions = (
        trainer._legal_actions(
            first_game
        )
    )

    assert len(
        actions
    ) == len(
        set(
            actions
        )
    )


def test_full_mode_contains_stand_pat() -> None:
    (
        first_game,
        _,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

    actions = (
        trainer._legal_actions(
            first_game
        )
    )

    assert (
        DiscardAction(
            ()
        )
        in actions
    )


def test_full_mode_contains_all_single_card_discards() -> None:
    (
        first_game,
        _,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

    actions = (
        trainer._legal_actions(
            first_game
        )
    )

    expected_single_discards = {
        DiscardAction(
            (
                index,
            )
        )
        for index in range(5)
    }

    assert expected_single_discards.issubset(
        set(
            actions
        )
    )


def test_full_mode_contains_all_two_card_discards() -> None:
    (
        first_game,
        _,
    ) = make_suit_isomorphic_games()

    trainer = make_full_trainer()

    actions = (
        trainer._legal_actions(
            first_game
        )
    )

    expected_two_card_discards = {
        DiscardAction(
            (
                first_index,
                second_index,
            )
        )
        for first_index in range(5)
        for second_index in range(
            first_index + 1,
            5,
        )
    }

    assert expected_two_card_discards.issubset(
        set(
            actions
        )
    )