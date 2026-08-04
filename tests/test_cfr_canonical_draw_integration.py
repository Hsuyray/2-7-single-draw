from copy import deepcopy

import pytest

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

    # These tests inspect action encoding.
    # They do not perform a real deck draw,
    # except through a monkeypatched executor.
    game.hands[
        acting_seat
    ] = hand

    return game


def make_trainer() -> CFRTrainer:
    return CFRTrainer(
        max_draw=2,
        raise_sizes=(),
        abstraction="exact",
        traversal_mode="full",
        draw_action_mode="full",
        random_seed=1,
    )


def test_trainer_legal_actions_use_canonical_indices() -> None:
    game = make_draw_game(
        hand=Hand.from_strings(
            "2s",
            "4s",
            "6s",
            "7d",
            "7s",
        )
    )

    trainer = make_trainer()

    actions = trainer._legal_actions(
        game
    )

    assert (
        DiscardAction(
            (3,)
        )
        in actions
    )

    assert (
        DiscardAction(
            (4,)
        )
        in actions
    )


def test_trainer_maps_canonical_action_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = make_draw_game(
        hand=Hand.from_strings(
            "2s",
            "4s",
            "6s",
            "7d",
            "7s",
        )
    )

    trainer = make_trainer()

    captured_actions: list[
        DiscardAction
    ] = []

    def fake_apply_solver_action(
        current_game: SingleDrawGame,
        action,
    ) -> SingleDrawGame:
        assert isinstance(
            action,
            DiscardAction,
        )

        captured_actions.append(
            action
        )

        return deepcopy(
            current_game
        )

    monkeypatch.setattr(
        "solver.cfr_trainer.apply_solver_action",
        fake_apply_solver_action,
    )

    trainer._apply_node_action(
        game=game,
        action=DiscardAction(
            (3,)
        ),
    )

    # Canonical index 3 corresponds to the
    # actual Hand.cards index 4, which is 7s.
    assert captured_actions == [
        DiscardAction(
            (4,)
        )
    ]


def test_trainer_maps_multiple_indices_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = make_draw_game(
        hand=Hand.from_strings(
            "2s",
            "4s",
            "6s",
            "7d",
            "7s",
        )
    )

    trainer = make_trainer()

    captured_actions: list[
        DiscardAction
    ] = []

    def fake_apply_solver_action(
        current_game: SingleDrawGame,
        action,
    ) -> SingleDrawGame:
        assert isinstance(
            action,
            DiscardAction,
        )

        captured_actions.append(
            action
        )

        return deepcopy(
            current_game
        )

    monkeypatch.setattr(
        "solver.cfr_trainer.apply_solver_action",
        fake_apply_solver_action,
    )

    trainer._apply_node_action(
        game=game,
        action=DiscardAction(
            (
                0,
                3,
            )
        ),
    )

    assert captured_actions == [
        DiscardAction(
            (
                0,
                4,
            )
        )
    ]


def test_suit_isomorphic_hands_have_same_node_actions() -> None:
    first_game = make_draw_game(
        hand=Hand.from_strings(
            "2s",
            "4s",
            "6s",
            "7d",
            "7s",
        )
    )

    second_game = make_draw_game(
        hand=Hand.from_strings(
            "2c",
            "4c",
            "6c",
            "7c",
            "7h",
        )
    )

    trainer = make_trainer()

    first_actions = trainer._legal_actions(
        first_game
    )

    second_actions = trainer._legal_actions(
        second_game
    )

    assert first_actions == (
        second_actions
    )


def test_canonical_actions_are_unique() -> None:
    game = make_draw_game(
        hand=Hand.from_strings(
            "2s",
            "4s",
            "6s",
            "7d",
            "7s",
        )
    )

    trainer = make_trainer()

    actions = trainer._legal_actions(
        game
    )

    assert len(actions) == len(
        set(actions)
    )


def test_stand_pat_remains_stand_pat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = make_draw_game(
        hand=Hand.from_strings(
            "2s",
            "4s",
            "6s",
            "7d",
            "7s",
        )
    )

    trainer = make_trainer()

    captured_actions: list[
        DiscardAction
    ] = []

    def fake_apply_solver_action(
        current_game: SingleDrawGame,
        action,
    ) -> SingleDrawGame:
        assert isinstance(
            action,
            DiscardAction,
        )

        captured_actions.append(
            action
        )

        return deepcopy(
            current_game
        )

    monkeypatch.setattr(
        "solver.cfr_trainer.apply_solver_action",
        fake_apply_solver_action,
    )

    trainer._apply_node_action(
        game=game,
        action=DiscardAction(
            ()
        ),
    )

    assert captured_actions == [
        DiscardAction(
            ()
        )
    ]


def test_betting_action_is_not_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    trainer = make_trainer()

    captured_actions = []

    def fake_apply_solver_action(
        current_game: SingleDrawGame,
        action,
    ) -> SingleDrawGame:
        captured_actions.append(
            action
        )

        return deepcopy(
            current_game
        )

    monkeypatch.setattr(
        "solver.cfr_trainer.apply_solver_action",
        fake_apply_solver_action,
    )

    actions = trainer._legal_actions(
        game
    )

    call_action = next(
        action
        for action in actions
        if getattr(
            action,
            "action_type",
            None,
        ) == ActionType.CALL
    )

    trainer._apply_node_action(
        game=game,
        action=call_action,
    )

    assert captured_actions == [
        call_action
    ]