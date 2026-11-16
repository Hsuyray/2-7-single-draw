"""
WS C1 step 3: solution library (docs/C1_DESIGN.md section 8.6).
"""

import json
from pathlib import Path

import pytest

from scripts import save_training_checkpoint, solve_library
from solver.benchmark_gates import evaluate_gates
from solver.solution_library import (
    LATEST_CHECKPOINT_NAME,
    STATE_FILE_NAME,
    evaluation_summary,
    file_sha256,
    load_manifest,
    new_solution_entry,
    save_manifest,
    stopping_advice,
    training_argv,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)
from solver.training_run import read_state_summary


SOLUTION = "tiny"

ADD_ARGS = [
    "--stack", "20",
    "--max-draw", "1",
    "--abstraction", "exact",
    "--bet-sizing", "fast",
    "--seed", "42",
    "--milestones", "3,6",
]


def library(
    manifest: Path,
    *argv: str,
) -> None:
    solve_library.main(
        ["--manifest", str(manifest), *argv]
    )


def add_tiny(tmp_path: Path) -> Path:
    manifest = tmp_path / "solutions" / "manifest.json"

    library(manifest, "add", SOLUTION, *ADD_ARGS)

    return manifest


def train(manifest: Path, *extra: str) -> None:
    library(
        manifest,
        "train",
        SOLUTION,
        "--batch-size", "2",
        *extra,
    )


def strategies(path: Path) -> dict:
    return load_strategy_checkpoint(
        path
    ).strategy_index.strategies()


def straight_strategies(
    tmp_path: Path,
    iterations: int,
) -> dict:
    output = tmp_path / f"straight_{iterations}.chk.gz"

    save_training_checkpoint.main(
        [
            "--stack", "20",
            "--max-draw", "1",
            "--abstraction", "exact",
            "--bet-sizing", "fast",
            "--seed", "42",
            "--iterations", str(iterations),
            "--output", str(output),
        ]
    )

    return strategies(output)


def entry(manifest: Path) -> dict:
    return load_manifest(manifest)["solutions"][SOLUTION]


def test_train_milestones_match_uninterrupted_runs(
    tmp_path: Path,
) -> None:
    manifest = add_tiny(tmp_path)

    assert entry(manifest)["status"] == "planned"

    train(manifest, "--until", "3")

    first = entry(manifest)

    assert first["status"] == "training"
    assert [r["iterations"] for r in first["checkpoints"]] == [3]

    train(manifest)

    final = entry(manifest)

    assert final["status"] == "trained"

    records = final["checkpoints"]

    assert [r["iterations"] for r in records] == [3, 6]

    assert [r["training_segments"] for r in records] == [1, 2]

    for record in records:
        path = manifest.parent / record["path"]

        assert file_sha256(path) == record["sha256"]

        assert strategies(path) == straight_strategies(
            tmp_path,
            record["iterations"],
        )

    assert not (
        manifest.parent / SOLUTION / LATEST_CHECKPOINT_NAME
    ).exists()

    # Nothing pending: train again is a no-op.
    train(manifest)

    assert entry(manifest)["checkpoints"] == records


def test_memory_stop_then_same_command_resumes(
    tmp_path: Path,
) -> None:
    manifest = add_tiny(tmp_path)

    with pytest.raises(SystemExit) as stopped:
        train(
            manifest,
            "--until", "3",
            "--max-rss-gb", "0.001",
            "--rss-check-every", "1",
        )

    assert stopped.value.code == (
        save_training_checkpoint.EXIT_STOPPED_EARLY
    )

    assert entry(manifest)["status"] == "training"
    assert entry(manifest)["checkpoints"] == []

    train(manifest, "--until", "3", "--max-rss-gb", "0")

    record = entry(manifest)["checkpoints"][0]

    assert record["training_segments"] == 2

    assert strategies(
        manifest.parent / record["path"]
    ) == straight_strategies(tmp_path, 3)


def test_trained_but_unrecorded_milestone_is_recorded_without_training(
    tmp_path: Path,
) -> None:
    manifest = add_tiny(tmp_path)

    directory = manifest.parent / SOLUTION

    # As if a run finished training to 3 but died before recording.
    save_training_checkpoint.main(
        training_argv(entry(manifest))
        + [
            "--iterations", "3",
            "--output", str(directory / LATEST_CHECKPOINT_NAME),
            "--state-output", str(directory / STATE_FILE_NAME),
        ]
    )

    train(manifest, "--until", "3")

    record = entry(manifest)["checkpoints"][0]

    assert record["iterations"] == 3
    assert record["training_segments"] == 1

    assert read_state_summary(
        directory / STATE_FILE_NAME
    )["completed_iterations"] == 3


def test_add_rejects_bad_settings(tmp_path: Path) -> None:
    manifest = add_tiny(tmp_path)

    with pytest.raises(ValueError, match="already exists"):
        library(manifest, "add", SOLUTION, *ADD_ARGS)

    with pytest.raises(ValueError, match="Milestones"):
        library(
            manifest, "add", "other",
            *ADD_ARGS[:-1], "6,3",
        )

    unsupported = new_solution_entry(
        stack=20, max_draw=1, abstraction="exact",
        bet_sizing="fast", seed=1, milestones=[1],
    )

    unsupported["game"]["big_blind_ante"] = 0.0

    with pytest.raises(ValueError, match="big_blind_ante"):
        training_argv(unsupported)


def evaluated_entry(
    points: list[tuple[int, str, float, float]],
) -> dict:
    result = new_solution_entry(
        stack=20, max_draw=5, abstraction="bucket",
        bet_sizing="full", seed=42,
        milestones=[p[0] for p in points] or [1],
    )

    for iterations, verdict, gain, se in points:
        result["checkpoints"].append(
            {
                "iterations": iterations,
                "evaluation": {
                    "benchmark_run": True,
                    "verdict": verdict,
                    "sbr_mean_gain": gain,
                    "sbr_standard_error": se,
                },
            }
        )

    return result


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        ([], "no benchmark evaluation"),
        ([(8000, "PASS", 0.1, 0.05)], "stop: gates PASS"),
        (
            [(8000, "FAIL", 2.5, 0.1), (16000, "FAIL", 2.0, 0.1)],
            "continue: gates FAIL, too few",
        ),
        (
            [
                (8000, "FAIL", 2.5, 0.1),
                (16000, "FAIL", 2.0, 0.1),
                (32000, "FAIL", 1.4, 0.1),
            ],
            "continue: SBR gain dropped",
        ),
        (
            [
                (8000, "FAIL", 2.5, 0.1),
                (16000, "FAIL", 2.4, 0.1),
                (32000, "FAIL", 2.35, 0.1),
            ],
            "stop: SBR gain plateaued",
        ),
    ],
)
def test_stopping_advice(points, expected) -> None:
    assert stopping_advice(
        evaluated_entry(points)
    ).startswith(expected)


def test_evaluation_summary_of_v2_report() -> None:
    report = json.loads(
        Path(
            "experiments/eval/"
            "production_v2_maxdraw5__85c6f9ba__standard__s2027.json"
        ).read_text(encoding="utf-8")
    )

    summary = evaluation_summary(
        report,
        evaluate_gates(report),
        "x.json",
    )

    assert summary["verdict"] == "FAIL"
    assert summary["benchmark_run"] is True
    assert "Q6" in summary["failing_gates"]
    assert summary["sbr_lower_bound"] == pytest.approx(
        1.53,
        abs=0.01,
    )


def test_release_requires_benchmark_pass_or_allow_fail(
    tmp_path: Path,
) -> None:
    manifest = add_tiny(tmp_path)

    train(manifest, "--until", "3")

    with pytest.raises(SystemExit, match="evaluate"):
        library(manifest, "release", SOLUTION, "3")

    data = load_manifest(manifest)

    data["solutions"][SOLUTION]["checkpoints"][0]["evaluation"] = {
        "benchmark_run": True,
        "verdict": "FAIL",
        "failing_gates": ["Q6"],
    }

    save_manifest(manifest, data)

    with pytest.raises(SystemExit, match="allow-fail"):
        library(manifest, "release", SOLUTION, "3")

    library(manifest, "release", SOLUTION, "3", "--allow-fail")

    released = entry(manifest)

    assert released["status"] == "released"
    assert released["released"]["iterations"] == 3

    with pytest.raises(SystemExit, match="released"):
        train(manifest)
