"""
Single evaluation entry point for a saved strategy checkpoint
(workstream A2, design in docs/A2_DESIGN.md).

Evaluates the checkpoint itself; nothing is retrained.

    python -m scripts.evaluate_checkpoint checkpoints/production_v1.chk.gz
    python -m scripts.evaluate_checkpoint NEW.chk.gz --previous OLD.chk.gz
    python -m scripts.evaluate_checkpoint X.chk.gz --preset quick --sections static,coverage
    python -m scripts.evaluate_checkpoint --compare A.json B.json

Writes <out-dir>/<name>__<sha8>__<preset>__s<seed>.json and a .txt
with the same summary that is printed to stdout. Progress goes to
stderr. Two runs with the same arguments produce JSON that is
identical outside the "timing" and "environment" keys; --compare
checks exactly that.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from solver.benchmark_gates import (
    evaluate_gates,
    render_gates,
)
from solver.checkpoint_evaluation import (
    AssumedGameConfig,
    CheckpointConfigError,
    evaluate_baselines,
    evaluate_coverage,
    evaluate_head_to_head,
    evaluate_sampled_best_response,
    incompatible_fields,
    setup_from_metadata,
    static_statistics,
    strategy_distance,
)
from solver.memory_guard import (
    bytes_to_gb,
    peak_rss_bytes,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)


# 2 (day53): SBR section uses grouped SBR by default
# and records its grouping.
REPORT_VERSION = 2

# Ignored by --compare: they legitimately differ
# between otherwise identical runs.
VOLATILE_KEYS = (
    "timing",
    "environment",
)

ALL_SECTIONS = (
    "static",
    "coverage",
    "button1",
    "sbr",
    "baselines",
    "previous",
)

# Provisional sizes; see docs/A2_DESIGN.md 6.2 and
# docs/EXPERIMENT_LOG.md for measured run times.
PRESETS = {
    "quick": {
        "deals": 1_000,
        "button1_deals": 100,
        "top": 10,
        "sbr_repeats": 2,
        "sbr_response_deals": 50,
        "sbr_validation_deals": 200,
        "sbr_sweeps": 3,
        "match_deal_pairs": 200,
    },
    "standard": {
        "deals": 20_000,
        "button1_deals": 2_000,
        "top": 25,
        "sbr_repeats": 5,
        "sbr_response_deals": 100,
        "sbr_validation_deals": 1_000,
        "sbr_sweeps": 3,
        "match_deal_pairs": 5_000,
    },
}


DEFAULT_SBR_GROUPING = "coarse"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a saved 2-7 Single Draw "
            "strategy checkpoint (no retraining)."
        )
    )

    parser.add_argument(
        "checkpoint",
        nargs="?",
    )

    parser.add_argument(
        "--previous",
        help=(
            "Earlier checkpoint for strategy "
            "distance and head-to-head. Must "
            "share the game config and action "
            "abstraction."
        ),
    )

    parser.add_argument(
        "--preset",
        choices=tuple(PRESETS),
        default="standard",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2027,
    )

    for name in PRESETS["standard"]:
        parser.add_argument(
            "--" + name.replace("_", "-"),
            type=int,
            dest=name,
            help=(
                "Override the preset value."
            ),
        )

    parser.add_argument(
        "--sbr-grouping",
        choices=("coarse", "none"),
        default=DEFAULT_SBR_GROUPING,
        help=(
            "coarse = grouped SBR (benchmark "
            "default); none = original "
            "per-state SBR. A non-default value "
            "makes the run a non-benchmark run."
        ),
    )

    parser.add_argument(
        "--sections",
        default=",".join(ALL_SECTIONS),
        help=(
            "Comma-separated subset of: "
            + ", ".join(ALL_SECTIONS)
        ),
    )

    parser.add_argument(
        "--assume-config",
        help=(
            "STACK,SB,BB,ANTE for checkpoints "
            "whose metadata lacks the game "
            "config. Only fills missing fields."
        ),
    )

    parser.add_argument(
        "--out-dir",
        default="experiments/eval",
    )

    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print only; write no files.",
    )

    parser.add_argument(
        "--gates",
        metavar="REPORT_JSON",
        help=(
            "Re-evaluate the benchmark gates of "
            "a saved report and print them."
        ),
    )

    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("A_JSON", "B_JSON"),
        help=(
            "Compare two reports, ignoring "
            "timing and environment."
        ),
    )

    return parser.parse_args()


def resolve_parameters(
    args: argparse.Namespace,
) -> dict:
    parameters = dict(
        PRESETS[args.preset]
    )

    overridden = []

    for name in parameters:
        value = getattr(
            args,
            name,
        )

        if value is not None:
            if value <= 0:
                raise ValueError(
                    f"--{name} must be positive."
                )

            parameters[name] = value
            overridden.append(name)

    parameters["sbr_grouping"] = (
        args.sbr_grouping
    )

    if args.sbr_grouping != DEFAULT_SBR_GROUPING:
        overridden.append("sbr_grouping")

    sections = [
        section.strip()
        for section in args.sections.split(",")
        if section.strip()
    ]

    unknown = set(sections) - set(
        ALL_SECTIONS
    )

    if unknown:
        raise ValueError(
            "Unknown sections: "
            + ", ".join(sorted(unknown))
        )

    parameters["sections"] = [
        section
        for section in ALL_SECTIONS
        if section in sections
    ]

    parameters["preset"] = args.preset
    parameters["overridden"] = overridden
    parameters["seed"] = args.seed

    return parameters


def parse_assumed_config(
    text: str | None,
) -> AssumedGameConfig | None:
    if text is None:
        return None

    values = [
        float(part)
        for part in text.split(",")
    ]

    if len(values) != 4:
        raise ValueError(
            "--assume-config needs "
            "STACK,SB,BB,ANTE."
        )

    return AssumedGameConfig(
        starting_stack=values[0],
        small_blind=values[1],
        big_blind=values[2],
        big_blind_ante=values[3],
    )


def file_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1 << 20),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    except (OSError, subprocess.CalledProcessError):
        return None


def metadata_dict(
    metadata,
) -> dict:
    return {
        name: (
            list(value)
            if isinstance(value, tuple)
            else value
        )
        for name, value in vars(
            metadata
        ).items()
    }


def progress(
    message: str,
) -> None:
    print(
        message,
        file=sys.stderr,
        flush=True,
    )


def load_checkpoint(
    path_text: str,
    timing: dict,
    key: str,
):
    path = Path(path_text)

    progress(
        f"Loading {path} ..."
    )

    started = perf_counter()

    loaded = load_strategy_checkpoint(
        path
    )

    timing[key] = perf_counter() - started

    identity = {
        "name": path.name,
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
        "strategy_count": (
            loaded.strategy_count
        ),
        "metadata": metadata_dict(
            loaded.metadata
        ),
    }

    return (
        loaded,
        identity,
    )


def build_report(
    args: argparse.Namespace,
    parameters: dict,
) -> dict:
    timing: dict = {}
    sections = parameters["sections"]
    seed = parameters["seed"]

    (
        loaded,
        identity,
    ) = load_checkpoint(
        args.checkpoint,
        timing,
        "load_s",
    )

    setup = setup_from_metadata(
        loaded.metadata,
        assumed=parse_assumed_config(
            args.assume_config
        ),
    )

    index = loaded.strategy_index

    report: dict = {
        "report_version": REPORT_VERSION,
        "checkpoint": identity,
        "setup": setup.to_dict(),
        "parameters": parameters,
        "current_vs_average": {
            "available": False,
            "reason": (
                "Checkpoints store the average "
                "strategy only (no regrets), so "
                "the current strategy cannot be "
                "reconstructed. Use the distance "
                "to a previous checkpoint and "
                "the SBR proxy instead."
            ),
        },
    }

    visits = None

    if "static" in sections:
        progress("Static statistics ...")
        started = perf_counter()

        report["static"] = static_statistics(
            index
        )

        timing["static_s"] = (
            perf_counter() - started
        )

    if (
        "coverage" in sections
        or "previous" in sections
    ):
        progress(
            f"Coverage ({parameters['deals']:,} "
            "deals, button 0) ..."
        )

        started = perf_counter()

        (
            report["coverage"],
            visits,
        ) = evaluate_coverage(
            index,
            setup,
            deals=parameters["deals"],
            seed=seed,
            top=parameters["top"],
        )

        timing["coverage_s"] = (
            perf_counter() - started
        )

    if "button1" in sections:
        progress(
            "Coverage diagnostic "
            f"({parameters['button1_deals']:,} "
            "deals, button 1) ..."
        )

        started = perf_counter()

        (
            section,
            _,
        ) = evaluate_coverage(
            index,
            setup,
            deals=parameters["button1_deals"],
            seed=seed,
            top=parameters["top"],
            button_seat=1,
            label="coverage_button_1",
        )

        section["note"] = (
            "Training only uses button_seat=0 "
            "and PublicNodeKey stores the "
            "absolute button seat, so button-1 "
            "states are expected to be missing. "
            "Diagnostic only; not part of the "
            "main coverage."
        )

        report["coverage_button_1"] = section

        timing["button1_s"] = (
            perf_counter() - started
        )

    if "sbr" in sections:
        progress(
            "Sampled best response "
            f"({parameters['sbr_repeats']} "
            "repeats per seat) ..."
        )

        started = perf_counter()

        (
            report["sbr"],
            timing["sbr_runs_s"],
        ) = evaluate_sampled_best_response(
            index,
            setup,
            seed=seed,
            repeats=parameters["sbr_repeats"],
            response_deals=parameters[
                "sbr_response_deals"
            ],
            validation_deals=parameters[
                "sbr_validation_deals"
            ],
            sweeps=parameters["sbr_sweeps"],
            grouping=parameters["sbr_grouping"],
            progress=progress,
        )

        timing["sbr_s"] = (
            perf_counter() - started
        )

    if "baselines" in sections:
        progress(
            "Baselines "
            f"({parameters['match_deal_pairs']:,} "
            "deal pairs each) ..."
        )

        started = perf_counter()

        report["baselines"] = evaluate_baselines(
            index,
            setup,
            seed=seed,
            deal_pairs=parameters[
                "match_deal_pairs"
            ],
        )

        timing["baselines_s"] = (
            perf_counter() - started
        )

    if (
        "previous" in sections
        and args.previous is not None
    ):
        (
            previous,
            previous_identity,
        ) = load_checkpoint(
            args.previous,
            timing,
            "previous_load_s",
        )

        differing = incompatible_fields(
            loaded.metadata,
            previous.metadata,
        )

        section: dict = {
            "checkpoint": previous_identity,
            "compatible": not differing,
            "incompatible_fields": {
                name: {
                    "current": metadata_dict(
                        loaded.metadata
                    )[name],
                    "previous": metadata_dict(
                        previous.metadata
                    )[name],
                }
                for name in differing
            },
        }

        if differing:
            section["refused"] = (
                "Game config or action "
                "abstraction differ; the two "
                "strategies do not play the same "
                "game, so distance and "
                "head-to-head are undefined."
            )

        else:
            progress(
                "Distance to previous ..."
            )

            started = perf_counter()

            section["distance"] = (
                strategy_distance(
                    index,
                    previous.strategy_index,
                    visits=visits,
                )
            )

            progress(
                "Head-to-head "
                f"({parameters['match_deal_pairs']:,} "
                "deal pairs) ..."
            )

            section["head_to_head"] = (
                evaluate_head_to_head(
                    index,
                    previous.strategy_index,
                    setup,
                    seed=seed,
                    deal_pairs=parameters[
                        "match_deal_pairs"
                    ],
                )
            )

            timing["previous_s"] = (
                perf_counter() - started
            )

        report["previous"] = section

    report["gates"] = evaluate_gates(
        report
    )

    peak = peak_rss_bytes()

    timing["peak_rss_gb"] = (
        None
        if peak is None
        else round(
            bytes_to_gb(peak),
            3,
        )
    )

    report["timing"] = timing

    report["environment"] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(),
    }

    return report


# ----------------------------------------------------------------
# Summary
# ----------------------------------------------------------------


def pct(
    value: float | None,
) -> str:
    return (
        "n/a"
        if value is None
        else f"{value:.2%}"
    )


def render_summary(
    report: dict,
) -> str:
    lines: list[str] = []
    add = lines.append

    checkpoint = report["checkpoint"]
    metadata = checkpoint["metadata"]
    parameters = report["parameters"]

    add("=" * 72)
    add("CHECKPOINT EVALUATION")
    add("=" * 72)
    add(f"  checkpoint: {checkpoint['name']}")
    add(f"  sha256: {checkpoint['sha256']}")
    add(
        f"  format v{metadata['format_version']}, "
        f"{metadata['completed_iterations']:,} iterations, "
        f"{checkpoint['strategy_count']:,} strategies"
    )
    add(
        f"  abstraction={metadata['abstraction']} "
        f"max_draw={metadata['max_draw']} "
        f"draw_action_mode={metadata['draw_action_mode']} "
        f"bet_sizing={metadata['bet_sizing_mode']} "
        f"{metadata['bet_pot_fractions']}"
    )
    add(
        f"  preset={parameters['preset']} "
        f"seed={parameters['seed']} "
        f"overridden={parameters['overridden'] or '-'}"
    )

    setup = report["setup"]

    if setup["assumed_fields"]:
        add(
            "  WARNING: assumed game config for "
            + ", ".join(setup["assumed_fields"])
        )

    static = report.get("static")

    if static is not None:
        add("")
        add("STATIC")
        add(
            f"  invalid strategies: "
            f"{static['invalid_strategies']}"
        )

        for phase, stats in static[
            "by_phase"
        ].items():
            add(
                f"  {phase:<17} "
                f"states={stats['information_states']:>9,} "
                f"public={stats['public_nodes']:>7,} "
                f"near-uniform={pct(stats['near_uniform_fraction']):>7} "
                f"deterministic={pct(stats['deterministic_fraction']):>7}"
            )

    coverage = report.get("coverage")

    if coverage is not None:
        overall = coverage["overall"]
        first_miss = coverage["first_miss"]

        add("")
        add(
            f"COVERAGE (self-play, {coverage['deals']:,} "
            "deals, button 0)"
        )
        add(
            f"  overall: {pct(overall['rate'])} "
            f"(se {pct(overall['standard_error'])}, "
            f"{overall['matched']:,}/{overall['total']:,})"
        )

        for phase, stats in coverage[
            "by_phase"
        ].items():
            add(
                f"  {phase:<17} {pct(stats['rate']):>7} "
                f"({stats['matched']:,}/{stats['total']:,})"
                f"  near-uniform when played: "
                f"{pct(stats['near_uniform_played'])}"
            )

        add(
            f"  deals with any miss: "
            f"{pct(first_miss['rate'])}; first miss by phase: "
            + (
                ", ".join(
                    f"{phase}={count:,}"
                    for phase, count in first_miss[
                        "by_phase"
                    ].items()
                )
                or "-"
            )
        )
        add(
            f"  action-space mismatches: "
            f"{coverage['action_space_mismatches']}"
            + (
                ""
                if coverage[
                    "action_space_mismatches"
                ] == 0
                else "   <-- metadata rebuild or "
                "legal actions disagree; other "
                "numbers are suspect"
            )
        )

        self_play = coverage["self_play"]

        add(
            f"  self-play seat 0: "
            f"{self_play['seat_0_utility']:+.4f} "
            f"± {self_play['seat_0_standard_error']:.4f} "
            f"chips/deal; max zero-sum error "
            f"{self_play['max_zero_sum_error']:.2e}"
        )

        if coverage["top_missing_public_nodes"]:
            add("  top missing public nodes:")

            for node in coverage[
                "top_missing_public_nodes"
            ][:10]:
                add(
                    f"    {node['count']:>6,}  "
                    f"pot={node['pot']:g} "
                    f"bet={node['current_bet']:g}  "
                    f"{node['history'] or '(root)'}"
                )

    button1 = report.get("coverage_button_1")

    if button1 is not None:
        add("")
        add(
            f"BUTTON 1 DIAGNOSTIC ({button1['deals']:,} deals): "
            f"coverage {pct(button1['overall']['rate'])}"
        )

    sbr = report.get("sbr")

    if sbr is not None:
        add("")
        add(
            f"SBR PROXY ({sbr['repeats']} repeats/seat, "
            f"{sbr['response_deals']:,} response deals, "
            f"{sbr['validation_deals']:,} validation deals, "
            f"<= {sbr['max_sweeps']} sweeps, "
            f"grouping {sbr.get('grouping', 'none')})"
        )

        for seat_name, summary in sbr[
            "gain_by_seat"
        ].items():
            add(
                f"  {seat_name}: mean gain "
                f"{summary['mean']:+.4f} "
                f"sd {summary['sd']:.4f} "
                f"[{summary['min']:+.4f}, {summary['max']:+.4f}]"
            )

        mean_gain = sbr["mean_seat_gain"]

        add(
            f"  mean over seats: {mean_gain['mean']:+.4f} "
            f"± {mean_gain['standard_error']:.4f} (se over repeats)"
        )

        validation_errors = [
            run["gain_standard_error"]
            for runs in sbr["runs"].values()
            for run in runs
        ]

        add(
            "  per-run gain se (validation noise): "
            f"{min(validation_errors):.4f}.."
            f"{max(validation_errors):.4f}"
        )

        fallback_shares = [
            run["response_fallback_share"]
            for runs in sbr["runs"].values()
            for run in runs
            if "response_fallback_share" in run
        ]

        if fallback_shares:
            add(
                "  responder validation decisions "
                "from fallback: "
                f"{pct(min(fallback_shares))}.."
                f"{pct(max(fallback_shares))}"
            )
        add("  proxy only; NOT exploitability")

    baselines = report.get("baselines")

    if baselines is not None:
        add("")
        add(
            f"BASELINES (duplicate, "
            f"{baselines['deal_pairs']:,} deal pairs)"
        )

        for name, match in baselines[
            "opponents"
        ].items():
            add(
                f"  vs {name:<13} "
                f"{match['utility']:+.4f} "
                f"± {match['standard_error']:.4f} "
                f"chips/deal (profile coverage "
                f"{pct(match['profile_coverage'])})"
            )

    previous = report.get("previous")

    if previous is not None:
        add("")
        add(
            f"PREVIOUS: {previous['checkpoint']['name']}"
        )

        if not previous["compatible"]:
            add(
                "  refused: differing fields "
                + ", ".join(
                    previous[
                        "incompatible_fields"
                    ]
                )
            )

        else:
            distance = previous["distance"]

            add(
                f"  visit-weighted L1: "
                f"{distance['visit_weighted_l1']}"
            )

            for phase, stats in distance[
                "by_phase"
            ].items():
                add(
                    f"  {phase:<17} "
                    f"weighted={stats['visit_weighted_l1']} "
                    f"median={stats['median_l1']} "
                    f"shared={stats['shared_states']:,}"
                )

            match = previous["head_to_head"]

            add(
                f"  head-to-head: "
                f"{match['utility']:+.4f} "
                f"± {match['standard_error']:.4f} "
                "chips/deal for the current checkpoint"
            )

    add("")
    add(
        "current-vs-average: unavailable "
        "(checkpoint has no regrets)"
    )

    gates = report.get("gates")

    if gates is not None:
        add("")

        for line in render_gates(gates):
            add(line)

    timing = report["timing"]

    add("")
    add(
        "TIMING  "
        + "  ".join(
            f"{key}={value:.1f}"
            for key, value in timing.items()
            if isinstance(value, float)
            and key != "peak_rss_gb"
        )
        + f"  peak_rss_gb={timing['peak_rss_gb']}"
    )

    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------
# Compare
# ----------------------------------------------------------------


def diff_values(
    first,
    second,
    path: str,
    out: list[str],
) -> None:
    if isinstance(first, dict) and isinstance(
        second,
        dict,
    ):
        for key in sorted(
            set(first) | set(second)
        ):
            if key not in first:
                out.append(
                    f"{path}/{key}: only in B"
                )
            elif key not in second:
                out.append(
                    f"{path}/{key}: only in A"
                )
            else:
                diff_values(
                    first[key],
                    second[key],
                    f"{path}/{key}",
                    out,
                )

        return

    if isinstance(first, list) and isinstance(
        second,
        list,
    ) and len(first) == len(second):
        for position, (
            left,
            right,
        ) in enumerate(
            zip(first, second)
        ):
            diff_values(
                left,
                right,
                f"{path}[{position}]",
                out,
            )

        return

    if first != second:
        out.append(
            f"{path}: {first!r} != {second!r}"
        )


def compare_reports(
    first_path: str,
    second_path: str,
) -> list[str]:
    first = json.loads(
        Path(first_path).read_text(
            encoding="utf-8"
        )
    )
    second = json.loads(
        Path(second_path).read_text(
            encoding="utf-8"
        )
    )

    for key in VOLATILE_KEYS:
        first.pop(key, None)
        second.pop(key, None)

    differences: list[str] = []

    diff_values(
        first,
        second,
        "",
        differences,
    )

    return differences


def output_stem(
    report: dict,
) -> str:
    checkpoint = report["checkpoint"]
    parameters = report["parameters"]

    name = checkpoint["name"]

    for suffix in (
        ".gz",
        ".chk",
    ):
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    preset = parameters["preset"]

    if (
        parameters["overridden"]
        or parameters["sections"]
        != list(ALL_SECTIONS)
    ):
        preset += "-custom"

    return (
        f"{name}__{checkpoint['sha256'][:8]}"
        f"__{preset}__s{parameters['seed']}"
    )


def main() -> None:
    args = parse_args()

    if args.compare is not None:
        differences = compare_reports(
            *args.compare
        )

        if differences:
            print(
                f"{len(differences)} difference(s) "
                "outside timing/environment:"
            )

            for line in differences[:200]:
                print("  " + line)

            sys.exit(1)

        print(
            "Reports identical outside "
            "timing/environment."
        )

        return

    if args.gates is not None:
        saved = json.loads(
            Path(args.gates).read_text(
                encoding="utf-8"
            )
        )

        gates = evaluate_gates(saved)

        print(
            f"{saved['checkpoint']['name']} "
            f"(report preset "
            f"{saved['parameters']['preset']})"
        )

        for line in render_gates(gates):
            print(line)

        return

    if args.checkpoint is None:
        raise SystemExit(
            "checkpoint is required unless "
            "--compare is given"
        )

    parameters = resolve_parameters(
        args
    )

    try:
        report = build_report(
            args,
            parameters,
        )

    except CheckpointConfigError as error:
        raise SystemExit(
            f"Cannot evaluate checkpoint: {error}"
        )

    summary = render_summary(
        report
    )

    print(summary, end="")

    if args.no_write:
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    stem = output_stem(report)

    json_path = out_dir / f"{stem}.json"
    text_path = out_dir / f"{stem}.txt"

    json_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    text_path.write_text(
        summary,
        encoding="utf-8",
    )

    progress(
        f"Wrote {json_path} and {text_path}"
    )


if __name__ == "__main__":
    main()
