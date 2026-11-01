"""
Resumable training state (WS C1).

A training state file holds the whole CFRTrainer (node table with
regret sums, strategy sums and counters, the trainer RNG and
completed_iterations) plus run bookkeeping. It is separate from the
v3 strategy checkpoint, which stays unchanged; the state file is
only read by training. See docs/C1_DESIGN.md.

Resuming reproduces an uninterrupted run exactly because:
- the trainer RNG state is inside the pickled trainer, and
- the game factory calls once per iteration, so the sequential game
  seed is seed + completed_iterations (make_game_factory).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import gzip
import os
from pathlib import Path
import pickle
import platform
import subprocess
from typing import Any, Callable

from solver.cfr_trainer import (
    CFRTrainer,
)
from solver.game_state import (
    GameConfig,
)
from solver.single_draw_game import (
    SingleDrawGame,
)


TRAINING_STATE_VERSION = 1

PREVIOUS_STATE_SUFFIX = ".prev"


@dataclass
class TrainingRunInfo:
    """
    Bookkeeping stored next to the trainer.

    config: every setting that changes training results. A resume
    must match it exactly.
    segments: one entry per training session (start / end
    iteration, wall seconds, peak RSS, stop reason).
    """

    config: dict[str, Any]

    segments: list[dict[str, Any]] = field(
        default_factory=list,
    )

    git_commit: str | None = None

    python_version: str = field(
        default_factory=platform.python_version,
    )


@dataclass
class TrainingState:
    trainer: CFRTrainer

    run: TrainingRunInfo


def make_game_factory(
    trainer: CFRTrainer,
    *,
    game_config: GameConfig,
    seed: int,
    seed_mode: str,
) -> Callable[[], SingleDrawGame]:
    """
    Game factory whose game seed depends only on the trainer's
    completed_iterations, so a resumed trainer continues the same
    game sequence. CFRTrainer.train calls the factory once at the
    start of each iteration, before completed_iterations is
    incremented, so call k gets seed + k as before.
    """
    if seed_mode not in {
        "fixed",
        "sequential",
    }:
        raise ValueError(
            "Seed mode must be "
            "'fixed' or 'sequential'."
        )

    def game_factory() -> SingleDrawGame:
        if seed_mode == "fixed":
            game_seed = seed
        else:
            game_seed = (
                seed
                + trainer.completed_iterations
            )

        return SingleDrawGame(
            config=game_config,
            button_seat=0,
            deck_seed=game_seed,
        )

    return game_factory


def config_differences(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[str]:
    differences = []

    for key in sorted(
        set(expected) | set(actual)
    ):
        if expected.get(key) != actual.get(key):
            differences.append(
                f"{key}: state file has "
                f"{expected.get(key)!r}, "
                f"this run has "
                f"{actual.get(key)!r}"
            )

    return differences


def save_training_state(
    path: str | Path,
    state: TrainingState,
) -> Path:
    """
    Write the state atomically: write <path>.tmp, move the existing
    file to <path>.prev, then move the new file into place. If the
    process dies at any point, either <path> or <path>.prev holds a
    complete earlier state.
    """
    output_path = Path(
        path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        output_path.with_suffix(
            output_path.suffix
            + ".tmp"
        )
    )

    previous_path = (
        output_path.with_suffix(
            output_path.suffix
            + PREVIOUS_STATE_SUFFIX
        )
    )

    payload = {
        "state_version": (
            TRAINING_STATE_VERSION
        ),
        "trainer": state.trainer,
        "run": state.run,
    }

    try:
        with gzip.open(
            temporary_path,
            "wb",
        ) as state_file:
            pickle.dump(
                payload,
                state_file,
                protocol=(
                    pickle.HIGHEST_PROTOCOL
                ),
            )

        if output_path.exists():
            os.replace(
                output_path,
                previous_path,
            )

        os.replace(
            temporary_path,
            output_path,
        )

    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return output_path


def load_training_state(
    path: str | Path,
) -> TrainingState:
    state_path = Path(
        path
    )

    if not state_path.is_file():
        previous_path = (
            state_path.with_suffix(
                state_path.suffix
                + PREVIOUS_STATE_SUFFIX
            )
        )

        hint = (
            f" An earlier state exists at "
            f"{previous_path}; resume from "
            f"it explicitly if intended."
            if previous_path.is_file()
            else ""
        )

        raise FileNotFoundError(
            f"Training state does not "
            f"exist: {state_path}.{hint}"
        )

    with gzip.open(
        state_path,
        "rb",
    ) as state_file:
        payload = pickle.load(
            state_file
        )

    if not isinstance(payload, dict):
        raise ValueError(
            "Training state file has an "
            "unexpected format."
        )

    version = payload.get(
        "state_version"
    )

    if version != TRAINING_STATE_VERSION:
        raise ValueError(
            f"Unsupported training state "
            f"version {version!r}; expected "
            f"{TRAINING_STATE_VERSION}."
        )

    trainer = payload["trainer"]

    run = payload["run"]

    if not isinstance(trainer, CFRTrainer):
        raise ValueError(
            "Training state does not "
            "contain a CFRTrainer."
        )

    if not isinstance(run, TrainingRunInfo):
        raise ValueError(
            "Training state does not "
            "contain run information."
        )

    return TrainingState(
        trainer=trainer,
        run=run,
    )


def current_git_commit() -> str | None:
    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(
                __file__
            ).resolve().parents[1],
        )

    except (
        OSError,
        subprocess.CalledProcessError,
    ):
        return None

    return result.stdout.strip() or None
