"""
Solution library manifest (WS C1, docs/C1_DESIGN.md section 3).

solutions/manifest.json (tracked in git) lists every solution: its
game and abstraction settings, seed, iteration milestones, and for
each finished milestone the strategy checkpoint (path, sha256, node
count, cumulative training time, peak RSS) and its A2 evaluation.
Checkpoint and training-state files live in solutions/<id>/ and are
not tracked; the sha256 ties them to the manifest.

Pure data functions only; scripts/solve_library.py runs training and
evaluation.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any


MANIFEST_VERSION = 1

# save_training_checkpoint.py trains with these blinds only.
SUPPORTED_BLINDS = {
    "small_blind": 1.0,
    "big_blind": 2.0,
    "big_blind_ante": 1.5,
}

STATUSES = (
    "planned",
    "training",
    "trained",
    "released",
)

SOLUTION_ID_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_]*$"
)

STATE_FILE_NAME = "training.state.gz"

LATEST_CHECKPOINT_NAME = "strategy_latest.chk.gz"

EVAL_DIR_NAME = "eval"

# Stopping rule (C1_DESIGN 3.3): stop when the gates pass, or when
# the SBR mean gain did not drop by more than this many combined
# standard errors over each of the last two doublings.
PLATEAU_STANDARD_ERRORS = 2.0

PLATEAU_DOUBLINGS = 2


def empty_manifest() -> dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "solutions": {},
    }


def load_manifest(
    path: str | Path,
) -> dict[str, Any]:
    manifest_path = Path(path)

    if not manifest_path.exists():
        return empty_manifest()

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    version = manifest.get(
        "manifest_version"
    )

    if version != MANIFEST_VERSION:
        raise ValueError(
            f"Unsupported manifest version "
            f"{version!r}; expected "
            f"{MANIFEST_VERSION}."
        )

    return manifest


def save_manifest(
    path: str | Path,
    manifest: dict[str, Any],
) -> Path:
    manifest_path = Path(path)

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = manifest_path.with_suffix(
        manifest_path.suffix + ".tmp"
    )

    try:
        temporary_path.write_text(
            json.dumps(
                manifest,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        os.replace(
            temporary_path,
            manifest_path,
        )

    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return manifest_path


def new_solution_entry(
    *,
    stack: float,
    max_draw: int,
    abstraction: str,
    bet_sizing: str,
    seed: int,
    milestones: list[int],
    seed_mode: str = "sequential",
    traversal_mode: str = "external_sampling",
    draw_action_mode: str = "auto",
    note: str = "",
) -> dict[str, Any]:
    if stack <= 0:
        raise ValueError(
            "Stack must be positive."
        )

    if not 0 <= max_draw <= 5:
        raise ValueError(
            "Max draw must be between "
            "zero and five."
        )

    if (
        not milestones
        or any(m <= 0 for m in milestones)
        or sorted(set(milestones))
        != list(milestones)
    ):
        raise ValueError(
            "Milestones must be positive, "
            "distinct and increasing."
        )

    return {
        "status": "planned",
        "game": {
            "player_count": 2,
            "stack": float(stack),
            **SUPPORTED_BLINDS,
            "max_draw": max_draw,
        },
        "abstraction": {
            "abstraction": abstraction,
            "bet_sizing": bet_sizing,
            "traversal_mode": traversal_mode,
            "draw_action_mode": draw_action_mode,
        },
        "seed": seed,
        "seed_mode": seed_mode,
        "milestones": list(milestones),
        "checkpoints": [],
        "released": None,
        "note": note,
    }


def add_solution(
    manifest: dict[str, Any],
    solution_id: str,
    entry: dict[str, Any],
) -> None:
    if not SOLUTION_ID_PATTERN.match(
        solution_id
    ):
        raise ValueError(
            "Solution id must be lowercase "
            "letters, digits and underscores."
        )

    if solution_id in manifest["solutions"]:
        raise ValueError(
            f"Solution {solution_id!r} "
            f"already exists."
        )

    manifest["solutions"][solution_id] = (
        copy.deepcopy(entry)
    )


def get_solution(
    manifest: dict[str, Any],
    solution_id: str,
) -> dict[str, Any]:
    try:
        return manifest["solutions"][
            solution_id
        ]

    except KeyError:
        raise KeyError(
            f"No solution {solution_id!r} "
            f"in the manifest."
        ) from None


def training_argv(
    entry: dict[str, Any],
) -> list[str]:
    """
    save_training_checkpoint.py arguments for the settings that
    affect results. Refuses blinds the script cannot train.
    """
    game = entry["game"]

    for key, value in SUPPORTED_BLINDS.items():
        if not math.isclose(
            float(game[key]),
            value,
        ):
            raise ValueError(
                f"{key}={game[key]} is not "
                f"supported; training uses "
                f"{SUPPORTED_BLINDS}."
            )

    if game["player_count"] != 2:
        raise ValueError(
            "The trainer supports heads-up "
            "games only."
        )

    abstraction = entry["abstraction"]

    return [
        "--stack", repr(float(game["stack"])),
        "--max-draw", str(game["max_draw"]),
        "--abstraction",
        abstraction["abstraction"],
        "--bet-sizing",
        abstraction["bet_sizing"],
        "--traversal-mode",
        abstraction["traversal_mode"],
        "--draw-action-mode",
        abstraction["draw_action_mode"],
        "--seed", str(entry["seed"]),
        "--seed-mode", entry["seed_mode"],
    ]


def checkpoint_name(
    iterations: int,
) -> str:
    return f"strategy_{iterations:06d}.chk.gz"


def find_checkpoint(
    entry: dict[str, Any],
    iterations: int,
) -> dict[str, Any] | None:
    for record in entry["checkpoints"]:
        if record["iterations"] == iterations:
            return record

    return None


def pending_milestones(
    entry: dict[str, Any],
) -> list[int]:
    done = {
        record["iterations"]
        for record in entry["checkpoints"]
    }

    return [
        milestone
        for milestone in entry["milestones"]
        if milestone not in done
    ]


def file_sha256(
    path: str | Path,
) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as stream:
        for chunk in iter(
            lambda: stream.read(1 << 20),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="seconds"
    )


def checkpoint_record(
    *,
    iterations: int,
    path: str,
    sha256: str,
    size_bytes: int,
    cfr_nodes: int,
    segments: list[dict[str, Any]],
    git_commit: str | None,
) -> dict[str, Any]:
    """
    segments are the training-state segments up to this milestone.
    peak_rss_gb_max is read before each state write (C1_DESIGN
    8.5), so it can miss the state save's own peak.
    """
    peaks = [
        segment["peak_rss_gb"]
        for segment in segments
        if segment.get("peak_rss_gb")
        is not None
    ]

    return {
        "iterations": iterations,
        "path": path,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "cfr_nodes": cfr_nodes,
        "wall_seconds_total": sum(
            segment["wall_seconds"]
            for segment in segments
        ),
        "training_segments": len(segments),
        "peak_rss_gb_max": (
            max(peaks) if peaks else None
        ),
        "git_commit": git_commit,
        "created_at_utc": utc_now(),
        "evaluation": None,
    }


def evaluation_summary(
    report: dict[str, Any],
    gates: dict[str, Any],
    report_path: str,
) -> dict[str, Any]:
    """
    Manifest summary of an A2 report. gates is
    solver.benchmark_gates.evaluate_gates(report), recomputed so
    the manifest uses the current gates version.
    """
    sbr_gate = next(
        (
            gate
            for gate in gates["gates"]
            if gate["id"] == "Q6"
        ),
        None,
    )

    sbr_value = (
        sbr_gate.get("value")
        if sbr_gate is not None
        else None
    )

    return {
        "report_path": report_path,
        "checkpoint_sha256": (
            report["checkpoint"]["sha256"]
        ),
        "preset": (
            report["parameters"]["preset"]
        ),
        "seed": report["parameters"]["seed"],
        "benchmark_run": gates["benchmark_run"],
        "gates_version": gates["gates_version"],
        "verdict": gates["verdict"],
        "failing_gates": [
            gate["id"]
            for gate in gates["gates"]
            if gate["status"] == "fail"
        ],
        "sbr_mean_gain": (
            sbr_value["mean_gain"]
            if isinstance(sbr_value, dict)
            else None
        ),
        "sbr_standard_error": (
            sbr_value["standard_error"]
            if isinstance(sbr_value, dict)
            else None
        ),
        "sbr_lower_bound": (
            sbr_value["lower_bound"]
            if isinstance(sbr_value, dict)
            else None
        ),
    }


def stopping_advice(
    entry: dict[str, Any],
) -> str:
    """
    C1_DESIGN 3.3 stopping rule over evaluated benchmark
    checkpoints, in iteration order. Advisory only.
    """
    evaluated = [
        record
        for record in sorted(
            entry["checkpoints"],
            key=lambda r: r["iterations"],
        )
        if record["evaluation"] is not None
        and record["evaluation"]["benchmark_run"]
    ]

    if not evaluated:
        return "no benchmark evaluation yet"

    latest = evaluated[-1]

    if latest["evaluation"]["verdict"] == "PASS":
        return (
            f"stop: gates PASS at "
            f"{latest['iterations']:,}"
        )

    if len(evaluated) < PLATEAU_DOUBLINGS + 1:
        return (
            "continue: gates "
            f"{latest['evaluation']['verdict']}, "
            "too few evaluated milestones for "
            "the plateau rule"
        )

    window = evaluated[
        -(PLATEAU_DOUBLINGS + 1):
    ]

    for earlier, later in zip(
        window,
        window[1:],
    ):
        a = earlier["evaluation"]
        b = later["evaluation"]

        if (
            a["sbr_mean_gain"] is None
            or b["sbr_mean_gain"] is None
        ):
            return (
                "continue: SBR missing in a "
                "recent evaluation"
            )

        combined_se = math.sqrt(
            a["sbr_standard_error"] ** 2
            + b["sbr_standard_error"] ** 2
        )

        if (
            a["sbr_mean_gain"]
            - b["sbr_mean_gain"]
            > PLATEAU_STANDARD_ERRORS
            * combined_se
        ):
            return (
                "continue: SBR gain dropped "
                "significantly from "
                f"{earlier['iterations']:,} to "
                f"{later['iterations']:,}"
            )

    return (
        "stop: SBR gain plateaued over the "
        f"last {PLATEAU_DOUBLINGS} milestones; "
        "look for abstraction problems "
        "instead of training longer"
    )
