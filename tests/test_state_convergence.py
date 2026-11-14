"""
C1 step 5: scripts/inspect_state_convergence.py reads a training state
and must see exactly the checkpoint's strategies and decisions.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import save_training_checkpoint
from scripts.inspect_state_convergence import (
    NodeStoreStrategies,
    l1,
    total_variation_from_uniform,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)
from solver.training_run import (
    load_training_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    directory = tmp_path_factory.mktemp("convergence")

    checkpoint = directory / "strategy.chk.gz"
    state = directory / "training.state.gz"

    save_training_checkpoint.main(
        [
            "--max-draw", "1",
            "--abstraction", "bucket",
            "--bet-sizing", "fast",
            "--iterations", "30",
            "--batch-size", "10",
            "--output", str(checkpoint),
            "--state-output", str(state),
        ]
    )

    return directory, checkpoint, state


def test_node_store_view_equals_checkpoint(trained) -> None:
    _, checkpoint, state = trained

    stored = load_strategy_checkpoint(
        checkpoint
    ).strategy_index.strategies()

    view = NodeStoreStrategies(
        load_training_state(state).trainer.node_store.nodes
    )

    assert len(view) == len(stored)

    for information_state, strategy in stored.items():
        assert view.strategy_for_state(
            information_state
        ) == strategy

        assert view.strategy_for_hand(
            public_node=information_state.public_node,
            observer_seat=information_state.observer_seat,
            hand_key=information_state.own_hand_key,
        ) == strategy


def test_metric_helpers() -> None:
    uniform = {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
    pure = {"a": 1.0, "b": 0.0, "c": 0.0, "d": 0.0}

    assert total_variation_from_uniform(uniform) == 0.0
    assert total_variation_from_uniform(pure) == pytest.approx(0.75)
    assert l1(uniform, pure) == pytest.approx(1.5)


def run(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def report(trained) -> Path:
    directory, checkpoint, _ = trained

    evaluation = run(
        "scripts.evaluate_checkpoint",
        str(checkpoint),
        "--preset", "quick",
        "--sections", "coverage",
        "--deals", "80",
        "--out-dir", str(directory / "eval"),
    )

    assert evaluation.returncode == 0, evaluation.stderr

    (path,) = (directory / "eval").glob("strategy__*.json")

    return path


def test_decisions_match_evaluate_checkpoint_report(
    trained,
    report,
) -> None:
    directory, _, state = trained

    convergence = run(
        "scripts.inspect_state_convergence",
        str(state),
        "--deals", "80",
        "--report", str(report),
        "--out-dir", str(directory / "out"),
    )

    assert convergence.returncode == 0, (
        convergence.stdout + convergence.stderr
    )
    assert "REPORT CHECK OK" in convergence.stdout

    (result_path,) = (directory / "out").glob(
        "convergence__000030__s2027.json"
    )

    result = json.loads(
        result_path.read_text(encoding="utf-8")
    )

    coverage = json.loads(
        report.read_text(encoding="utf-8")
    )["coverage"]

    assert sum(result["matched"].values()) == (
        coverage["overall"]["matched"]
    )
    assert result["report_check"]["problems"] == []

    overall = result["overall"]

    assert 0.0 <= overall["current_vs_average_mean"] <= 2.0
    assert 0.0 <= overall["average_vs_uniform_mean"] < 1.0
    assert overall["strategy_updates_median"] >= 0


def test_mismatched_report_fails(
    trained,
    report,
    tmp_path,
) -> None:
    _, _, state = trained

    convergence = run(
        "scripts.inspect_state_convergence",
        str(state),
        "--deals", "81",
        "--report", str(report),
        "--out-dir", str(tmp_path),
    )

    assert convergence.returncode == 1
    assert "REPORT CHECK FAILED" in convergence.stdout
