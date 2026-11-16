"""
Solution library entry point (WS C1, docs/C1_DESIGN.md sections 3-4).

    python -m scripts.solve_library add <id> --stack 20 --max-draw 5 \
        --abstraction bucket --bet-sizing full --seed 42 \
        --milestones 8000,16000,32000
    python -m scripts.solve_library train <id> [--until N]
    python -m scripts.solve_library status [<id>]
    python -m scripts.solve_library evaluate <id> <iterations>
    python -m scripts.solve_library release <id> <iterations>

train runs scripts.save_training_checkpoint once per pending milestone
with --resume, so an interrupted run continues with the same command.
evaluate runs scripts.evaluate_checkpoint (A2) and records the gates.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from scripts import save_training_checkpoint  # noqa: E402
from solver.benchmark_gates import (  # noqa: E402
    evaluate_gates,
)
from solver.memory_guard import (  # noqa: E402
    DEFAULT_RSS_CHECK_EVERY,
)
from solver.solution_library import (  # noqa: E402
    EVAL_DIR_NAME,
    LATEST_CHECKPOINT_NAME,
    STATE_FILE_NAME,
    add_solution,
    checkpoint_name,
    checkpoint_record,
    evaluation_summary,
    file_sha256,
    find_checkpoint,
    get_solution,
    load_manifest,
    new_solution_entry,
    pending_milestones,
    save_manifest,
    stopping_advice,
    training_argv,
    utc_now,
)
from solver.training_run import (  # noqa: E402
    read_state_summary,
)


DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "solutions"
    / "manifest.json"
)

# Library runs reach ~2M nodes under `full` sizing (C1_DESIGN 8.5:
# about 4-6 GB), above the training script's 3 GB default guard.
DEFAULT_LIBRARY_MAX_RSS_GB = 10.0

# The evaluate_checkpoint default seed; the report file name uses it.
EVALUATION_SEED = 2027


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train, evaluate and release "
            "solutions listed in "
            "solutions/manifest.json."
        )
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    add = commands.add_parser(
        "add",
        help="Add a planned solution.",
    )
    add.add_argument("solution_id")
    add.add_argument(
        "--stack", type=float, required=True,
    )
    add.add_argument(
        "--max-draw", type=int, required=True,
        choices=range(0, 6),
    )
    add.add_argument(
        "--abstraction", required=True,
        choices=("exact", "bucket"),
    )
    add.add_argument(
        "--bet-sizing", required=True,
        choices=("none", "fast", "full"),
    )
    add.add_argument(
        "--seed", type=int, required=True,
    )
    add.add_argument(
        "--milestones", required=True,
        help="Comma-separated iteration counts.",
    )
    add.add_argument(
        "--seed-mode", default="sequential",
        choices=("fixed", "sequential"),
    )
    add.add_argument(
        "--traversal-mode",
        default="external_sampling",
        choices=("full", "external_sampling"),
    )
    add.add_argument(
        "--draw-action-mode", default="auto",
        choices=("auto", "full", "candidate"),
    )
    add.add_argument(
        "--note", default="",
    )

    train = commands.add_parser(
        "train",
        help=(
            "Train (or resume) to the pending "
            "milestones."
        ),
    )
    train.add_argument("solution_id")
    train.add_argument(
        "--until", type=int, default=None,
        help="Stop after this milestone.",
    )
    train.add_argument(
        "--batch-size", type=int,
        default=save_training_checkpoint.DEFAULT_BATCH_SIZE,
    )
    train.add_argument(
        "--max-rss-gb", type=float,
        default=DEFAULT_LIBRARY_MAX_RSS_GB,
    )
    train.add_argument(
        "--rss-check-every", type=int,
        default=DEFAULT_RSS_CHECK_EVERY,
    )
    train.add_argument(
        "--min-free-memory-gb", type=float,
        default=save_training_checkpoint.DEFAULT_MIN_FREE_MEMORY_GB,
    )

    status = commands.add_parser(
        "status",
        help="Show progress and evaluations.",
    )
    status.add_argument(
        "solution_id", nargs="?",
    )

    evaluate = commands.add_parser(
        "evaluate",
        help=(
            "Run the A2 benchmark on a "
            "milestone checkpoint."
        ),
    )
    evaluate.add_argument("solution_id")
    evaluate.add_argument(
        "iterations", type=int,
    )
    evaluate.add_argument(
        "--preset", default="standard",
        choices=("quick", "standard"),
        help=(
            "Only 'standard' counts for the "
            "gates and the stopping rule."
        ),
    )

    release = commands.add_parser(
        "release",
        help=(
            "Mark a milestone as the "
            "solution served to users."
        ),
    )
    release.add_argument("solution_id")
    release.add_argument(
        "iterations", type=int,
    )
    release.add_argument(
        "--allow-fail", action="store_true",
        help=(
            "Release even though the gates "
            "did not pass."
        ),
    )

    return parser.parse_args(argv)


def solution_dir(
    manifest_path: Path,
    solution_id: str,
) -> Path:
    return manifest_path.parent / solution_id


def relative_path(
    manifest_path: Path,
    path: Path,
) -> str:
    return path.relative_to(
        manifest_path.parent
    ).as_posix()


def command_add(
    args: argparse.Namespace,
) -> None:
    manifest = load_manifest(args.manifest)

    entry = new_solution_entry(
        stack=args.stack,
        max_draw=args.max_draw,
        abstraction=args.abstraction,
        bet_sizing=args.bet_sizing,
        seed=args.seed,
        milestones=[
            int(value)
            for value in args.milestones.split(",")
        ],
        seed_mode=args.seed_mode,
        traversal_mode=args.traversal_mode,
        draw_action_mode=args.draw_action_mode,
        note=args.note,
    )

    # Fails early on settings the trainer cannot run.
    training_argv(entry)

    add_solution(
        manifest,
        args.solution_id,
        entry,
    )

    save_manifest(args.manifest, manifest)

    print(
        f"Added {args.solution_id} "
        f"(milestones {entry['milestones']})."
    )


def finish_milestone(
    args: argparse.Namespace,
    manifest: dict,
    entry: dict,
    milestone: int,
    directory: Path,
) -> None:
    """
    Rename the latest checkpoint to the milestone name and record
    it. The latest checkpoint and the state summary must both be
    at exactly this milestone.
    """
    state_summary = read_state_summary(
        directory / STATE_FILE_NAME
    )

    latest = directory / LATEST_CHECKPOINT_NAME

    if (
        state_summary is None
        or state_summary["completed_iterations"]
        != milestone
        or not latest.is_file()
    ):
        raise RuntimeError(
            f"Cannot record milestone "
            f"{milestone:,}: training state "
            f"or latest checkpoint is not at "
            f"that iteration."
        )

    target = directory / checkpoint_name(
        milestone
    )

    os.replace(latest, target)

    entry["checkpoints"].append(
        checkpoint_record(
            iterations=milestone,
            path=relative_path(
                args.manifest,
                target,
            ),
            sha256=file_sha256(target),
            size_bytes=target.stat().st_size,
            cfr_nodes=state_summary["cfr_nodes"],
            segments=state_summary["segments"],
            git_commit=(
                state_summary["git_commit"]
            ),
        )
    )

    entry["checkpoints"].sort(
        key=lambda record: record["iterations"]
    )

    if not pending_milestones(entry):
        entry["status"] = "trained"

    save_manifest(args.manifest, manifest)

    print(
        f"Recorded milestone {milestone:,}: "
        f"{target}"
    )


def command_train(
    args: argparse.Namespace,
) -> None:
    manifest = load_manifest(args.manifest)

    entry = get_solution(
        manifest,
        args.solution_id,
    )

    if entry["status"] == "released":
        raise SystemExit(
            "Solution is released; add a new "
            "solution instead of training it "
            "further."
        )

    directory = solution_dir(
        args.manifest,
        args.solution_id,
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    state_path = directory / STATE_FILE_NAME

    latest = directory / LATEST_CHECKPOINT_NAME

    for milestone in pending_milestones(entry):
        if (
            args.until is not None
            and milestone > args.until
        ):
            break

        state_summary = read_state_summary(
            state_path
        )

        done = (
            state_summary["completed_iterations"]
            if state_summary is not None
            else 0
        )

        if done > milestone:
            raise SystemExit(
                f"Training state is at {done:,} "
                f"iterations, past the unrecorded "
                f"milestone {milestone:,}."
            )

        # A previous run trained to this milestone but stopped
        # before recording it.
        if done == milestone and latest.is_file():
            finish_milestone(
                args, manifest, entry,
                milestone, directory,
            )
            continue

        entry["status"] = "training"

        save_manifest(args.manifest, manifest)

        argv = training_argv(entry) + [
            "--iterations", str(milestone),
            "--output", str(latest),
            "--state-output", str(state_path),
            "--checkpoint-every-batches", "0",
            "--batch-size", str(args.batch_size),
            "--max-rss-gb", str(args.max_rss_gb),
            "--rss-check-every",
            str(args.rss_check_every),
            "--min-free-memory-gb",
            str(args.min_free_memory_gb),
        ]

        if state_path.is_file():
            argv += ["--resume", str(state_path)]

        print(
            f"=== {args.solution_id}: training "
            f"to {milestone:,} iterations ==="
        )

        # Exits with EXIT_STOPPED_EARLY on a memory stop; the
        # manifest stays at "training" and the same command
        # resumes.
        save_training_checkpoint.main(argv)

        finish_milestone(
            args, manifest, entry,
            milestone, directory,
        )


def command_evaluate(
    args: argparse.Namespace,
) -> None:
    manifest = load_manifest(args.manifest)

    entry = get_solution(
        manifest,
        args.solution_id,
    )

    record = find_checkpoint(
        entry,
        args.iterations,
    )

    if record is None:
        raise SystemExit(
            f"No recorded checkpoint at "
            f"{args.iterations:,} iterations."
        )

    checkpoint = (
        args.manifest.parent / record["path"]
    )

    if file_sha256(checkpoint) != record["sha256"]:
        raise SystemExit(
            f"{checkpoint} does not match the "
            f"sha256 in the manifest."
        )

    out_dir = solution_dir(
        args.manifest,
        args.solution_id,
    ) / EVAL_DIR_NAME

    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.evaluate_checkpoint",
            str(checkpoint),
            "--preset", args.preset,
            "--out-dir", str(out_dir),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

    stem = checkpoint.name.removesuffix(
        ".gz"
    ).removesuffix(".chk")

    report_path = out_dir / (
        f"{stem}__{record['sha256'][:8]}"
        f"__{args.preset}"
        f"__s{EVALUATION_SEED}.json"
    )

    report = json.loads(
        report_path.read_text(
            encoding="utf-8"
        )
    )

    if (
        report["checkpoint"]["sha256"]
        != record["sha256"]
    ):
        raise SystemExit(
            f"{report_path} is for a different "
            f"checkpoint."
        )

    summary = evaluation_summary(
        report,
        evaluate_gates(report),
        relative_path(
            args.manifest,
            report_path,
        ),
    )

    summary["evaluated_at_utc"] = utc_now()

    record["evaluation"] = summary

    save_manifest(args.manifest, manifest)

    print(
        f"Recorded evaluation: verdict "
        f"{summary['verdict']}, SBR lower bound "
        f"{summary['sbr_lower_bound']}"
    )

    print(
        f"Stopping rule: {stopping_advice(entry)}"
    )


def command_release(
    args: argparse.Namespace,
) -> None:
    manifest = load_manifest(args.manifest)

    entry = get_solution(
        manifest,
        args.solution_id,
    )

    record = find_checkpoint(
        entry,
        args.iterations,
    )

    if record is None:
        raise SystemExit(
            f"No recorded checkpoint at "
            f"{args.iterations:,} iterations."
        )

    evaluation = record["evaluation"]

    if (
        evaluation is None
        or not evaluation["benchmark_run"]
    ):
        raise SystemExit(
            "Run 'evaluate' with the standard "
            "preset before releasing."
        )

    if (
        evaluation["verdict"] != "PASS"
        and not args.allow_fail
    ):
        raise SystemExit(
            f"Gates verdict is "
            f"{evaluation['verdict']} (failing "
            f"{evaluation['failing_gates']}); "
            f"pass --allow-fail to release "
            f"anyway."
        )

    entry["released"] = {
        "iterations": args.iterations,
        "verdict": evaluation["verdict"],
        "released_at_utc": utc_now(),
    }

    entry["status"] = "released"

    save_manifest(args.manifest, manifest)

    print(
        f"Released {args.solution_id} at "
        f"{args.iterations:,} iterations "
        f"(gates {evaluation['verdict']})."
    )


def format_solution(
    manifest_path: Path,
    solution_id: str,
    entry: dict,
) -> list[str]:
    game = entry["game"]
    abstraction = entry["abstraction"]

    lines = [
        f"{solution_id} [{entry['status']}]",
        (
            f"  game: stack {game['stack']:g} "
            f"(blinds {game['small_blind']:g}/"
            f"{game['big_blind']:g}, ante "
            f"{game['big_blind_ante']:g}), "
            f"max_draw {game['max_draw']}"
        ),
        (
            f"  abstraction: "
            f"{abstraction['abstraction']}, "
            f"sizing {abstraction['bet_sizing']}, "
            f"{abstraction['traversal_mode']}, "
            f"draw {abstraction['draw_action_mode']}; "
            f"seed {entry['seed']} "
            f"({entry['seed_mode']})"
        ),
        f"  milestones: {entry['milestones']}",
    ]

    state_summary = read_state_summary(
        solution_dir(
            manifest_path,
            solution_id,
        )
        / STATE_FILE_NAME
    )

    if state_summary is not None:
        lines.append(
            f"  training state: "
            f"{state_summary['completed_iterations']:,} "
            f"iterations, "
            f"{state_summary['cfr_nodes']:,} nodes"
        )

    for record in entry["checkpoints"]:
        evaluation = record["evaluation"]

        if evaluation is None:
            verdict = "not evaluated"
        else:
            verdict = (
                f"{evaluation['verdict']} "
                f"({evaluation['preset']}"
                + (
                    f", fail {','.join(evaluation['failing_gates'])}"
                    if evaluation["failing_gates"]
                    else ""
                )
                + ")"
            )

            if evaluation["sbr_lower_bound"] is not None:
                verdict += (
                    f", SBR lb "
                    f"{evaluation['sbr_lower_bound']:+.2f}"
                )

        peak = record["peak_rss_gb_max"]

        lines.append(
            f"  {record['iterations']:>8,}: "
            f"{record['cfr_nodes']:,} nodes, "
            f"{record['wall_seconds_total'] / 3600:.2f} h, "
            f"peak "
            + (
                f"{peak:.2f} GB"
                if peak is not None
                else "n/a"
            )
            + f", {verdict}"
        )

    lines.append(
        f"  stopping rule: "
        f"{stopping_advice(entry)}"
    )

    if entry["released"] is not None:
        lines.append(
            f"  released: "
            f"{entry['released']['iterations']:,} "
            f"(gates {entry['released']['verdict']})"
        )

    if entry["note"]:
        lines.append(
            f"  note: {entry['note']}"
        )

    return lines


def command_status(
    args: argparse.Namespace,
) -> None:
    manifest = load_manifest(args.manifest)

    if args.solution_id is not None:
        ids = [args.solution_id]
        get_solution(manifest, args.solution_id)
    else:
        ids = sorted(manifest["solutions"])

    if not ids:
        print("No solutions in the manifest.")
        return

    for solution_id in ids:
        for line in format_solution(
            args.manifest,
            solution_id,
            manifest["solutions"][solution_id],
        ):
            print(line)


COMMANDS = {
    "add": command_add,
    "train": command_train,
    "status": command_status,
    "evaluate": command_evaluate,
    "release": command_release,
}


def main(
    argv: list[str] | None = None,
) -> None:
    args = parse_args(argv)

    args.manifest = args.manifest.resolve()

    COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
