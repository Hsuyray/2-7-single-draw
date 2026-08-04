from pathlib import Path

import pytest

from solver.cfr_trainer import (
    CFRTrainer,
)
from solver.game_state import (
    GameConfig,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)


def make_game() -> SingleDrawGame:
    return SingleDrawGame(
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


def make_trainer() -> CFRTrainer:
    return CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        abstraction="exact",
        traversal_mode=(
            "external_sampling"
        ),
        draw_action_mode="candidate",
        random_seed=1,
    )


def test_trainer_builds_checkpoint_metadata() -> None:
    trainer = make_trainer()

    metadata = (
        trainer.checkpoint_metadata()
    )

    assert metadata.abstraction == "exact"
    assert metadata.max_draw == 1

    assert (
        metadata.draw_action_mode
        == "candidate"
    )

    assert (
        metadata.completed_iterations
        == 0
    )

    assert metadata.raise_sizes == ()


def test_untrained_trainer_cannot_save(
    tmp_path: Path,
) -> None:
    trainer = make_trainer()

    with pytest.raises(
        RuntimeError,
        match=(
            "before any CFR nodes "
            "have been trained"
        ),
    ):
        trainer.save_checkpoint(
            tmp_path
            / "untrained.chk.gz"
        )


def test_trainer_saves_checkpoint(
    tmp_path: Path,
) -> None:
    trainer = make_trainer()

    trainer.train(
        make_game,
        iterations=1,
    )

    path = (
        tmp_path
        / "trained.chk.gz"
    )

    result = (
        trainer.save_checkpoint(
            path
        )
    )

    assert result == path
    assert path.exists()

    loaded = (
        load_strategy_checkpoint(
            path
        )
    )

    assert (
        loaded.metadata
        .completed_iterations
        == 1
    )

    assert (
        loaded.metadata.max_draw
        == trainer.max_draw
    )

    assert (
        loaded.metadata
        .draw_action_mode
        == trainer
        .resolved_draw_action_mode
    )

    assert (
        loaded.strategy_count
        == len(
            trainer.average_strategies()
        )
    )


def test_loaded_strategy_matches_trainer(
    tmp_path: Path,
) -> None:
    trainer = make_trainer()

    trainer.train(
        make_game,
        iterations=1,
    )

    path = (
        tmp_path
        / "strategy.chk.gz"
    )

    trainer.save_checkpoint(
        path
    )

    loaded = (
        load_strategy_checkpoint(
            path
        )
    )

    assert (
        loaded.strategy_index
        .strategies()
        == trainer.strategy_index()
        .strategies()
    )