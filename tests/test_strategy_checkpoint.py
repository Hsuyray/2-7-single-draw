import gzip
from pathlib import Path
import pickle

import pytest

from solver.actions import (
    DiscardAction,
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
    CHECKPOINT_FORMAT_VERSION,
    CHECKPOINT_GAME,
    LoadedStrategyCheckpoint,
    StrategyCheckpointMetadata,
    build_checkpoint_metadata,
    load_strategy_checkpoint,
    save_strategy_checkpoint,
)
from solver.strategy_index import (
    StrategyIndex,
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


def make_betting_index() -> tuple[
    StrategyIndex,
    InformationState,
]:
    game = make_game()

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

    return (
        index,
        state,
    )


def make_draw_index() -> tuple[
    StrategyIndex,
    InformationState,
]:
    game = make_game()

    game.apply_betting_action(
        ActionType.CALL
    )

    game.apply_betting_action(
        ActionType.CHECK
    )

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
                DiscardAction(
                    ()
                ): 0.20,
                DiscardAction(
                    (4,)
                ): 0.80,
            },
        }
    )

    return (
        index,
        state,
    )


def make_metadata() -> (
    StrategyCheckpointMetadata
):
    return build_checkpoint_metadata(
        abstraction="exact",
        max_draw=3,
        draw_action_mode="full",
        completed_iterations=100,
        raise_sizes=(),
    )


def test_metadata_builder_uses_current_format() -> None:
    metadata = make_metadata()

    assert (
        metadata.format_version
        == CHECKPOINT_FORMAT_VERSION
    )

    assert (
        metadata.game
        == CHECKPOINT_GAME
    )

    assert (
        metadata.completed_iterations
        == 100
    )


def test_checkpoint_round_trip(
    tmp_path: Path,
) -> None:
    (
        index,
        state,
    ) = make_betting_index()

    path = (
        tmp_path
        / "strategy.chk.gz"
    )

    metadata = make_metadata()

    result_path = (
        save_strategy_checkpoint(
            path,
            strategy_index=index,
            metadata=metadata,
        )
    )

    assert result_path == path
    assert path.exists()

    loaded = (
        load_strategy_checkpoint(
            path
        )
    )

    assert isinstance(
        loaded,
        LoadedStrategyCheckpoint,
    )

    assert loaded.metadata == metadata

    assert (
        loaded.metadata.completed_iterations
        == 100
    )

    assert (
        loaded.strategy_index
        .strategy_for_state(
            state
        )
        == index.strategy_for_state(
            state
        )
    )


def test_draw_actions_round_trip(
    tmp_path: Path,
) -> None:
    (
        index,
        state,
    ) = make_draw_index()

    path = (
        tmp_path
        / "draw.chk.gz"
    )

    metadata = make_metadata()

    save_strategy_checkpoint(
        path,
        strategy_index=index,
        metadata=metadata,
    )

    loaded = (
        load_strategy_checkpoint(
            path
        )
    )

    assert (
        loaded.strategy_index
        .strategy_for_state(
            state
        )
        == {
            DiscardAction(
                ()
            ): 0.20,
            DiscardAction(
                (4,)
            ): 0.80,
        }
    )


def test_checkpoint_preserves_metadata(
    tmp_path: Path,
) -> None:
    (
        index,
        _,
    ) = make_betting_index()

    metadata = make_metadata()

    path = (
        tmp_path
        / "metadata.chk.gz"
    )

    save_strategy_checkpoint(
        path,
        strategy_index=index,
        metadata=metadata,
    )

    loaded = (
        load_strategy_checkpoint(
            path
        )
    )

    assert loaded.metadata == metadata


def test_checkpoint_exposes_strategy_count(
    tmp_path: Path,
) -> None:
    (
        index,
        _,
    ) = make_betting_index()

    path = (
        tmp_path
        / "count.chk.gz"
    )

    save_strategy_checkpoint(
        path,
        strategy_index=index,
        metadata=make_metadata(),
    )

    loaded = (
        load_strategy_checkpoint(
            path
        )
    )

    assert loaded.strategy_count == 1


def test_save_creates_parent_directory(
    tmp_path: Path,
) -> None:
    (
        index,
        _,
    ) = make_betting_index()

    path = (
        tmp_path
        / "nested"
        / "checkpoints"
        / "strategy.chk.gz"
    )

    save_strategy_checkpoint(
        path,
        strategy_index=index,
        metadata=make_metadata(),
    )

    assert path.exists()


def test_missing_checkpoint_raises(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "missing.chk.gz"
    )

    with pytest.raises(
        FileNotFoundError
    ):
        load_strategy_checkpoint(
            path
        )


def test_corrupted_checkpoint_is_rejected(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "corrupted.chk.gz"
    )

    path.write_bytes(
        b"not a checkpoint"
    )

    with pytest.raises(
        ValueError,
        match=(
            "invalid or corrupted"
        ),
    ):
        load_strategy_checkpoint(
            path
        )


def test_wrong_format_version_is_rejected(
    tmp_path: Path,
) -> None:
    (
        index,
        _,
    ) = make_betting_index()

    path = (
        tmp_path
        / "wrong-version.chk.gz"
    )

    payload = {
        "format_version": 999,
        "metadata": make_metadata(),
        "strategies": (
            index.strategies()
        ),
    }

    with gzip.open(
        path,
        "wb",
    ) as checkpoint_file:
        pickle.dump(
            payload,
            checkpoint_file,
        )

    with pytest.raises(
        ValueError,
        match=(
            "Unsupported checkpoint "
            "format version"
        ),
    ):
        load_strategy_checkpoint(
            path
        )


def test_metadata_rejects_negative_iterations() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Completed iterations cannot "
            "be negative"
        ),
    ):
        StrategyCheckpointMetadata(
            format_version=(
                CHECKPOINT_FORMAT_VERSION
            ),
            game=CHECKPOINT_GAME,
            created_at_utc=(
                "2026-08-04T00:00:00+00:00"
            ),
            abstraction="exact",
            max_draw=3,
            draw_action_mode="full",
            completed_iterations=-1,
            raise_sizes=(),
        )


def test_strategy_index_returns_defensive_copy() -> None:
    (
        index,
        state,
    ) = make_betting_index()

    strategies = (
        index.strategies()
    )

    strategies[state][
        BettingAction(
            ActionType.CALL
        )
    ] = 0.0

    original = (
        index.strategy_for_state(
            state
        )
    )

    assert original is not None

    assert original[
        BettingAction(
            ActionType.CALL
        )
    ] == pytest.approx(
        0.75
    )