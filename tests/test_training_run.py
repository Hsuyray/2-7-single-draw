"""
WS C1: resumable training (docs/C1_DESIGN.md section 5).

T1: N iterations, save state, resume to N+M (twice) gives the same
    node table and checkpoint as N+M uninterrupted.
T3: resuming with a setting that affects results is refused.
T4: an interrupted state write leaves the earlier state readable.
"""

from pathlib import Path

import pytest

import solver.training_run as training_run
from scripts import save_training_checkpoint
from scripts.fingerprint_node_store import (
    fingerprint_trainer,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)
from solver.training_run import (
    load_training_state,
    save_training_state,
)


CONFIGS = {
    "exact_sequential": [
        "--max-draw", "1",
        "--abstraction", "exact",
        "--bet-sizing", "fast",
    ],
    "exact_fixed": [
        "--max-draw", "1",
        "--abstraction", "exact",
        "--bet-sizing", "full",
        "--seed-mode", "fixed",
        "--seed", "7",
    ],
    "bucket_maxdraw5": [
        "--max-draw", "5",
        "--abstraction", "bucket",
        "--bet-sizing", "fast",
    ],
}


def train(
    tmp_path: Path,
    name: str,
    config: list[str],
    *extra: str,
) -> None:
    save_training_checkpoint.main(
        config
        + [
            "--output",
            str(tmp_path / f"{name}.chk.gz"),
            "--batch-size",
            "3",
            *extra,
        ]
    )


def fingerprint(path: Path) -> dict[str, object]:
    return fingerprint_trainer(
        load_training_state(path).trainer
    )


def strategies(path: Path) -> dict:
    return load_strategy_checkpoint(
        path
    ).strategy_index.strategies()


@pytest.mark.parametrize(
    "config_name",
    sorted(CONFIGS),
)
def test_resume_matches_uninterrupted_run(
    tmp_path: Path,
    config_name: str,
) -> None:
    config = CONFIGS[config_name]

    straight_state = tmp_path / "straight.state.gz"

    train(
        tmp_path,
        "straight",
        config,
        "--iterations", "10",
        "--state-output", str(straight_state),
    )

    resumed_state = tmp_path / "resumed.state.gz"

    train(
        tmp_path,
        "resumed",
        config,
        "--iterations", "4",
        "--state-output", str(resumed_state),
    )

    # Two resumes, with the state path defaulting to --resume.
    for target in ("7", "10"):
        train(
            tmp_path,
            "resumed",
            config,
            "--iterations", target,
            "--resume", str(resumed_state),
        )

    straight = fingerprint(straight_state)

    resumed = fingerprint(resumed_state)

    assert resumed == straight

    assert strategies(
        tmp_path / "resumed.chk.gz"
    ) == strategies(
        tmp_path / "straight.chk.gz"
    )

    segments = load_training_state(
        resumed_state
    ).run.segments

    assert [
        (
            segment["start_iteration"],
            segment["end_iteration"],
            segment["stop_reason"],
        )
        for segment in segments
    ] == [
        (0, 4, "completed"),
        (4, 7, "completed"),
        (7, 10, "completed"),
    ]


def test_rss_stop_saves_state_and_resume_matches(
    tmp_path: Path,
) -> None:
    config = CONFIGS["exact_sequential"]

    straight_state = tmp_path / "straight.state.gz"

    train(
        tmp_path,
        "straight",
        config,
        "--iterations", "6",
        "--max-rss-gb", "0",
        "--state-output", str(straight_state),
    )

    stopped_state = tmp_path / "stopped.state.gz"

    # Any real process exceeds 0.001 GB, so the guard stops after
    # the first 2-iteration chunk.
    with pytest.raises(SystemExit) as stopped:
        train(
            tmp_path,
            "stopped",
            config,
            "--iterations", "6",
            "--max-rss-gb", "0.001",
            "--rss-check-every", "2",
            "--state-output", str(stopped_state),
        )

    assert stopped.value.code == (
        save_training_checkpoint.EXIT_STOPPED_EARLY
    )

    stopped_run = load_training_state(
        stopped_state
    )

    assert stopped_run.trainer.completed_iterations == 2

    assert (
        stopped_run.run.segments[-1]["stop_reason"]
        == "RSS limit"
    )

    train(
        tmp_path,
        "stopped",
        config,
        "--iterations", "6",
        "--max-rss-gb", "0",
        "--resume", str(stopped_state),
    )

    assert fingerprint(stopped_state) == fingerprint(
        straight_state
    )


@pytest.mark.parametrize(
    "changed",
    [
        ["--stack", "30"],
        ["--seed", "43"],
        ["--bet-sizing", "full"],
        ["--seed-mode", "fixed"],
    ],
)
def test_resume_with_different_settings_is_refused(
    tmp_path: Path,
    changed: list[str],
) -> None:
    config = CONFIGS["exact_sequential"]

    state = tmp_path / "run.state.gz"

    train(
        tmp_path,
        "run",
        config,
        "--iterations", "2",
        "--state-output", str(state),
    )

    with pytest.raises(
        ValueError,
        match=changed[0].lstrip("-").replace("-", "_"),
    ):
        train(
            tmp_path,
            "run",
            config + changed,
            "--iterations", "4",
            "--resume", str(state),
        )


def test_resume_past_target_is_refused(
    tmp_path: Path,
) -> None:
    config = CONFIGS["exact_sequential"]

    state = tmp_path / "run.state.gz"

    train(
        tmp_path,
        "run",
        config,
        "--iterations", "3",
        "--state-output", str(state),
    )

    with pytest.raises(
        ValueError,
        match="target total",
    ):
        train(
            tmp_path,
            "run",
            config,
            "--iterations", "3",
            "--resume", str(state),
        )


def test_interrupted_state_write_keeps_previous_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = CONFIGS["exact_sequential"]

    state = tmp_path / "run.state.gz"

    train(
        tmp_path,
        "run",
        config,
        "--iterations", "2",
        "--state-output", str(state),
    )

    before = fingerprint(state)

    loaded = load_training_state(state)

    def failing_dump(*args, **kwargs) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        training_run.pickle,
        "dump",
        failing_dump,
    )

    with pytest.raises(KeyboardInterrupt):
        save_training_state(state, loaded)

    monkeypatch.undo()

    assert fingerprint(state) == before

    assert not state.with_suffix(
        state.suffix + ".tmp"
    ).exists()

    # A completed second write keeps the first as .prev.
    train(
        tmp_path,
        "run",
        config,
        "--iterations", "4",
        "--resume", str(state),
    )

    previous = state.with_suffix(
        state.suffix + ".prev"
    )

    assert fingerprint(previous) == before

    assert (
        load_training_state(state)
        .trainer.completed_iterations
        == 4
    )


def test_missing_state_points_to_previous(
    tmp_path: Path,
) -> None:
    state = tmp_path / "run.state.gz"

    previous = state.with_suffix(
        state.suffix + ".prev"
    )

    previous.write_bytes(b"")

    with pytest.raises(
        FileNotFoundError,
        match="earlier state",
    ):
        load_training_state(state)
