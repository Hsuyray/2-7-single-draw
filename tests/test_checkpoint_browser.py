from pathlib import Path

import pytest

from solver.checkpoint_browser import (
    CheckpointBrowserSession,
    browser_from_checkpoint,
)
from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.information_state import (
    InformationState,
)
from solver.legal_actions import (
    BettingAction,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_checkpoint import (
    build_checkpoint_metadata,
    save_strategy_checkpoint,
)
from solver.strategy_index import (
    StrategyIndex,
)


def make_game(
    *,
    seed: int = 42,
) -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=100.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=seed,
    )


def save_test_checkpoint(
    path: Path,
    *,
    game: SingleDrawGame,
) -> InformationState:
    acting_seat = game.acting_seat

    assert acting_seat is not None

    state = InformationState.from_game(
        game,
        observer_seat=acting_seat,
        abstraction="exact",
    )

    index = StrategyIndex.from_strategies(
        {
            state: {
                BettingAction(
                    ActionType.FOLD
                ): 0.25,
                BettingAction(
                    ActionType.CALL
                ): 0.75,
            },
        }
    )

    metadata = build_checkpoint_metadata(
        abstraction="exact",
        max_draw=2,
        draw_action_mode="full",
        completed_iterations=100,
        raise_sizes=(),
    )

    save_strategy_checkpoint(
        path,
        strategy_index=index,
        metadata=metadata,
    )

    return state


def test_browser_loads_from_checkpoint(
    tmp_path: Path,
) -> None:
    game = make_game()

    path = (
        tmp_path
        / "strategy.chk.gz"
    )

    state = save_test_checkpoint(
        path,
        game=game,
    )

    session = browser_from_checkpoint(
        path,
        game=game,
    )

    assert isinstance(
        session,
        CheckpointBrowserSession,
    )

    strategy = (
        session.browser
        .current_hand_strategy(
            state.own_hand_key
        )
    )

    assert strategy == {
        BettingAction(
            ActionType.FOLD
        ): 0.25,
        BettingAction(
            ActionType.CALL
        ): 0.75,
    }


def test_browser_restores_checkpoint_configuration(
    tmp_path: Path,
) -> None:
    game = make_game()

    path = (
        tmp_path
        / "config.chk.gz"
    )

    save_test_checkpoint(
        path,
        game=game,
    )

    session = browser_from_checkpoint(
        path,
        game=game,
    )

    browser = session.browser

    assert browser.abstraction == "exact"
    assert browser.max_draw == 2
    assert browser.draw_action_mode == "full"
    assert browser.raise_sizes == ()


def test_session_exposes_metadata(
    tmp_path: Path,
) -> None:
    game = make_game()

    path = (
        tmp_path
        / "metadata.chk.gz"
    )

    save_test_checkpoint(
        path,
        game=game,
    )

    session = browser_from_checkpoint(
        path,
        game=game,
    )

    assert (
        session.completed_iterations
        == 100
    )

    assert session.strategy_count == 1


def test_browser_returns_none_for_unknown_hand(
    tmp_path: Path,
) -> None:
    checkpoint_game = make_game(
        seed=42
    )

    different_game = make_game(
        seed=99
    )

    path = (
        tmp_path
        / "unknown.chk.gz"
    )

    save_test_checkpoint(
        path,
        game=checkpoint_game,
    )

    session = browser_from_checkpoint(
        path,
        game=different_game,
    )

    acting_seat = (
        different_game.acting_seat
    )

    assert acting_seat is not None

    state = InformationState.from_game(
        different_game,
        observer_seat=acting_seat,
        abstraction="exact",
    )

    assert (
        session.browser
        .current_hand_strategy(
            state.own_hand_key
        )
        is None
    )


def test_missing_checkpoint_is_rejected(
    tmp_path: Path,
) -> None:
    game = make_game()

    with pytest.raises(
        FileNotFoundError
    ):
        browser_from_checkpoint(
            tmp_path
            / "missing.chk.gz",
            game=game,
        )