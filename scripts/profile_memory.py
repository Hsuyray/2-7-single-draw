"""
Small, bounded memory-profiling run for the CFR trainer.

Logs iteration, CFR node count and process RSS to a CSV at
a fixed iteration interval, then prints a tracemalloc
breakdown. Measurement only: training uses the same
CFRTrainer, game config and seeding as
scripts/save_training_checkpoint.py.

Usage:
    python -m scripts.profile_memory
    python -m scripts.profile_memory --iterations 1000 --sample-every 50
"""

import argparse
from collections import Counter
from collections.abc import Iterable
import csv
from pathlib import Path
import sys
import time
import tracemalloc


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from scripts.save_training_checkpoint import (  # noqa: E402
    resolve_bet_sizing,
)
from solver.cfr_trainer import (  # noqa: E402
    CFRTrainer,
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.memory_guard import (  # noqa: E402
    DEFAULT_MAX_RSS_GB,
    RSSCheck,
    RSSGuard,
    bytes_to_gb,
    current_rss_bytes,
    iteration_chunks,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


HARD_MAX_ITERATIONS = 5_000

DEFAULT_ITERATIONS = 300

DEFAULT_SAMPLE_EVERY = 25

DEFAULT_OUTPUT_DIR = (
    Path("experiments")
    / "memory_profile"
)

CSV_FIELDS = (
    "event",
    "iteration",
    "cfr_nodes",
    "rss_bytes",
    "rss_gb",
    "traced_current_bytes",
    "traced_peak_bytes",
    "elapsed_seconds",
)


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded memory-profiling run: "
            "logs iteration, CFR node count "
            "and RSS to CSV, then prints a "
            "tracemalloc breakdown."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=(
            "Iterations to train. Hard cap: "
            f"{HARD_MAX_ITERATIONS:,}."
        ),
    )

    parser.add_argument(
        "--sample-every",
        type=int,
        default=DEFAULT_SAMPLE_EVERY,
        help=(
            "Iterations between CSV samples "
            "(and RSS guard checks)."
        ),
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--max-draw",
        type=int,
        default=5,
        choices=range(
            0,
            6,
        ),
    )

    parser.add_argument(
        "--abstraction",
        choices=(
            "exact",
            "bucket",
        ),
        default="bucket",
    )

    parser.add_argument(
        "--traversal-mode",
        choices=(
            "full",
            "external_sampling",
        ),
        default="external_sampling",
    )

    parser.add_argument(
        "--draw-action-mode",
        choices=(
            "auto",
            "full",
            "candidate",
        ),
        default="auto",
    )

    parser.add_argument(
        "--bet-sizing",
        choices=(
            "none",
            "fast",
            "full",
        ),
        default="fast",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--seed-mode",
        choices=(
            "fixed",
            "sequential",
        ),
        default="sequential",
    )

    parser.add_argument(
        "--max-rss-gb",
        type=float,
        default=DEFAULT_MAX_RSS_GB,
        help=(
            "Stop cleanly if process RSS "
            "exceeds this limit, in GB. "
            "0 disables the guard."
        ),
    )

    parser.add_argument(
        "--no-tracemalloc",
        action="store_true",
        help=(
            "Disable tracemalloc. tracemalloc "
            "slows training and adds its own "
            "memory to RSS; use this flag for "
            "RSS-only runs."
        ),
    )

    parser.add_argument(
        "--tracemalloc-frames",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help=(
            "Number of tracemalloc entries "
            "to report."
        ),
    )

    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "CSV output path. Default: "
            "experiments/memory_profile/"
            "profile_<config>.csv"
        ),
    )

    parser.add_argument(
        "--checkpoint-output",
        type=Path,
        default=None,
        help=(
            "Optionally save a checkpoint at "
            "the end and log RSS after the "
            "save. Default: no checkpoint."
        ),
    )

    return parser.parse_args(argv)


def validate_args(
    args: argparse.Namespace,
) -> None:
    if not (
        1
        <= args.iterations
        <= HARD_MAX_ITERATIONS
    ):
        raise ValueError(
            "Iterations must be between 1 "
            f"and {HARD_MAX_ITERATIONS:,}."
        )

    if args.sample_every <= 0:
        raise ValueError(
            "Sample interval must be "
            "positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Starting stack must be positive."
        )

    if (
        args.abstraction == "bucket"
        and args.draw_action_mode
        == "candidate"
    ):
        raise ValueError(
            "Bucket abstraction currently "
            "requires --draw-action-mode "
            "auto or full."
        )

    if args.max_rss_gb < 0:
        raise ValueError(
            "Max RSS cannot be negative. "
            "Use 0 to disable the guard."
        )

    if args.tracemalloc_frames < 1:
        raise ValueError(
            "tracemalloc frames must be "
            "at least 1."
        )

    if args.top < 1:
        raise ValueError(
            "Top count must be at least 1."
        )


def default_csv_path(
    *,
    max_draw: int,
    abstraction: str,
    bet_sizing: str,
    seed: int,
    iterations: int,
) -> Path:
    return DEFAULT_OUTPUT_DIR / (
        f"profile_md{max_draw}"
        f"_{abstraction}"
        f"_{bet_sizing}"
        f"_s{seed}"
        f"_it{iterations}.csv"
    )


def build_sample_row(
    *,
    event: str,
    iteration: int,
    cfr_nodes: int,
    rss_bytes: int,
    traced: tuple[int, int] | None,
    elapsed_seconds: float,
) -> dict[str, object]:
    """
    traced is (current, peak) from
    tracemalloc.get_traced_memory(), or None
    when tracemalloc is off.
    """
    if traced is None:
        traced_current: object = ""
        traced_peak: object = ""
    else:
        traced_current = traced[0]
        traced_peak = traced[1]

    return {
        "event": event,
        "iteration": iteration,
        "cfr_nodes": cfr_nodes,
        "rss_bytes": rss_bytes,
        "rss_gb": round(
            bytes_to_gb(rss_bytes),
            4,
        ),
        "traced_current_bytes": (
            traced_current
        ),
        "traced_peak_bytes": traced_peak,
        "elapsed_seconds": round(
            elapsed_seconds,
            3,
        ),
    }


def format_sample_line(
    row: dict[str, object],
) -> str:
    return (
        f"[{row['event']}] "
        f"iteration={row['iteration']}, "
        f"CFR_nodes={row['cfr_nodes']}, "
        f"rss={row['rss_gb']}GB, "
        f"elapsed={row['elapsed_seconds']}s"
    )


def nodes_by_phase(
    information_states: Iterable[object],
) -> dict[str, int]:
    """
    Count info sets by their .phase attribute
    (InformationState.phase).
    """
    counts = Counter(
        str(state.phase)  # type: ignore[attr-defined]
        for state in information_states
    )

    return dict(
        sorted(counts.items())
    )


def action_count_histogram(
    nodes: Iterable[object],
) -> dict[int, int]:
    """
    Count CFR nodes by number of actions
    (len(CFRNode.actions)).
    """
    counts = Counter(
        len(node.actions)  # type: ignore[attr-defined]
        for node in nodes
    )

    return dict(
        sorted(counts.items())
    )


def peak_rss_bytes(
    rows: Iterable[dict[str, object]],
) -> int:
    return max(
        (
            int(row["rss_bytes"])  # type: ignore[call-overload]
            for row in rows
        ),
        default=0,
    )


def _cache_info_lines() -> list[str]:
    """
    Current sizes of the lru_caches found in
    solver/ (see docs/AUDIT.md).
    """
    from solver import (
        draw_range_transition,
        postdraw_strength_bucket,
    )

    candidates = (
        (
            "postdraw_strength_bucket."
            "_score_frequencies",
            getattr(
                postdraw_strength_bucket,
                "_score_frequencies",
                None,
            ),
        ),
        (
            "postdraw_strength_bucket."
            "_score_to_bucket",
            getattr(
                postdraw_strength_bucket,
                "_score_to_bucket",
                None,
            ),
        ),
        (
            "draw_range_transition."
            "_cached_transition_exact_key",
            getattr(
                draw_range_transition,
                "_cached_transition_exact_key",
                None,
            ),
        ),
    )

    lines: list[str] = []

    for name, function in candidates:
        cache_info = getattr(
            function,
            "cache_info",
            None,
        )

        if cache_info is None:
            lines.append(
                f"  {name}: not found"
            )
            continue

        info = cache_info()

        lines.append(
            f"  {name}: "
            f"currsize={info.currsize:,}, "
            f"maxsize={info.maxsize}, "
            f"hits={info.hits:,}, "
            f"misses={info.misses:,}"
        )

    return lines


def _tracemalloc_report_lines(
    snapshot: tracemalloc.Snapshot,
    *,
    top: int,
) -> list[str]:
    snapshot = snapshot.filter_traces(
        (
            tracemalloc.Filter(
                False,
                tracemalloc.__file__,
            ),
            tracemalloc.Filter(
                False,
                "<frozen importlib._bootstrap>",
            ),
            tracemalloc.Filter(
                False,
                "<frozen importlib._bootstrap_external>",
            ),
            tracemalloc.Filter(
                False,
                "<unknown>",
            ),
        )
    )

    lines: list[str] = []

    for key_type in (
        "filename",
        "lineno",
    ):
        statistics = snapshot.statistics(
            key_type
        )

        total_bytes = sum(
            stat.size
            for stat in statistics
        )

        lines.append(
            f"tracemalloc top {top} by "
            f"{key_type} (total traced "
            f"{bytes_to_gb(total_bytes):.4f} GB):"
        )

        for rank, stat in enumerate(
            statistics[:top],
            start=1,
        ):
            frame = stat.traceback[0]

            location = (
                frame.filename
                if key_type == "filename"
                else (
                    f"{frame.filename}:"
                    f"{frame.lineno}"
                )
            )

            lines.append(
                f"  {rank:>3}. "
                f"{stat.size / (1024 ** 2):10.2f} MiB "
                f"{stat.count:>10,} blocks  "
                f"{location}"
            )

        lines.append("")

    return lines


def main(
    argv: list[str] | None = None,
) -> None:
    args = parse_args(argv)

    validate_args(args)

    (
        raise_sizes,
        bet_sizing_policy,
    ) = resolve_bet_sizing(
        args.bet_sizing
    )

    csv_path = (
        args.csv
        if args.csv is not None
        else default_csv_path(
            max_draw=args.max_draw,
            abstraction=args.abstraction,
            bet_sizing=args.bet_sizing,
            seed=args.seed,
            iterations=args.iterations,
        )
    )

    report_path = csv_path.with_name(
        csv_path.stem
        + "_report.txt"
    )

    use_tracemalloc = (
        not args.no_tracemalloc
    )

    if use_tracemalloc:
        tracemalloc.start(
            args.tracemalloc_frames
        )

    # Same game config and seeding as
    # scripts/save_training_checkpoint.py.
    shared_game_config = GameConfig(
        player_count=2,
        starting_stack=args.stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    game_counter = 0

    def game_factory() -> SingleDrawGame:
        nonlocal game_counter

        if args.seed_mode == "fixed":
            game_seed = args.seed
        else:
            game_seed = (
                args.seed
                + game_counter
            )

        game_counter += 1

        return SingleDrawGame(
            config=shared_game_config,
            button_seat=0,
            deck_seed=game_seed,
        )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
        abstraction=args.abstraction,
        traversal_mode=(
            args.traversal_mode
        ),
        draw_action_mode=(
            args.draw_action_mode
        ),
        random_seed=args.seed,
        game_config=shared_game_config,
    )

    rss_guard = RSSGuard(
        max_rss_gb=args.max_rss_gb,
    )

    print("Memory profile started:")
    print(f"  iterations: {args.iterations:,}")
    print(f"  sample every: {args.sample_every:,}")
    print(f"  max draw: {args.max_draw}")
    print(f"  abstraction: {args.abstraction}")
    print(f"  traversal: {args.traversal_mode}")
    print(f"  bet sizing: {args.bet_sizing}")
    print(
        "  resolved draw actions: "
        f"{trainer.resolved_draw_action_mode}"
    )
    print(f"  stack: {args.stack}")
    print(f"  seed: {args.seed} ({args.seed_mode})")
    print(
        "  max RSS (GB): "
        + (
            str(args.max_rss_gb)
            if rss_guard.enabled
            else "disabled"
        )
    )
    print(f"  tracemalloc: {use_tracemalloc}")
    print(f"  csv: {csv_path}")
    print()

    csv_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows: list[dict[str, object]] = []

    stopped_by_guard = False

    start = time.perf_counter()

    def record(
        writer: csv.DictWriter,
        csv_file,
        event: str,
    ) -> dict[str, object]:
        row = build_sample_row(
            event=event,
            iteration=(
                trainer.completed_iterations
            ),
            cfr_nodes=len(
                trainer.node_store
            ),
            rss_bytes=current_rss_bytes(),
            traced=(
                tracemalloc.get_traced_memory()
                if tracemalloc.is_tracing()
                else None
            ),
            elapsed_seconds=(
                time.perf_counter()
                - start
            ),
        )

        writer.writerow(row)
        csv_file.flush()

        rows.append(row)

        print(format_sample_line(row))

        return row

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDS,
        )

        writer.writeheader()

        record(writer, csv_file, "start")

        for chunk_size in iteration_chunks(
            args.iterations,
            args.sample_every,
        ):
            trainer.train(
                game_factory,
                iterations=chunk_size,
            )

            row = record(
                writer,
                csv_file,
                "sample",
            )

            if rss_guard.enabled:
                rss_check = RSSCheck(
                    rss_bytes=int(
                        row["rss_bytes"]  # type: ignore[call-overload]
                    ),
                    limit_bytes=(
                        rss_guard.limit_bytes
                    ),
                )

                if rss_check.exceeded:
                    print()
                    print(
                        "WARNING: process RSS "
                        f"({rss_check.rss_gb:.2f} GB) "
                        "exceeded the limit "
                        f"({args.max_rss_gb} GB). "
                        "Stopping profile run."
                    )

                    stopped_by_guard = True

                    record(
                        writer,
                        csv_file,
                        "rss_limit",
                    )

                    break

        training_seconds = (
            time.perf_counter()
            - start
        )

        if (
            args.checkpoint_output
            is not None
        ):
            checkpoint_path = (
                trainer.save_checkpoint(
                    args.checkpoint_output
                )
            )

            print(
                "Saved checkpoint to "
                f"{checkpoint_path.resolve()}"
            )

            record(
                writer,
                csv_file,
                "after_checkpoint_save",
            )

    report: list[str] = []

    report.append(
        "Memory profile summary"
        + (
            " (STOPPED BY RSS GUARD)"
            if stopped_by_guard
            else ""
        )
    )
    report.append(
        "  completed iterations: "
        f"{trainer.completed_iterations:,}"
    )
    report.append(
        f"  CFR nodes: {len(trainer.node_store):,}"
    )
    report.append(
        f"  training seconds: {training_seconds:.1f}"
    )
    report.append(
        "  peak sampled RSS: "
        f"{bytes_to_gb(peak_rss_bytes(rows)):.3f} GB"
    )
    report.append(
        f"  tracemalloc: {use_tracemalloc}"
    )
    report.append("")

    report.append("CFR nodes by phase:")

    for phase, count in nodes_by_phase(
        trainer.node_store.nodes.keys()
    ).items():
        report.append(
            f"  {phase}: {count:,}"
        )

    report.append("")

    report.append(
        "CFR nodes by action count:"
    )

    for action_count, count in (
        action_count_histogram(
            trainer.node_store.nodes.values()
        ).items()
    ):
        report.append(
            f"  {action_count} actions: "
            f"{count:,}"
        )

    report.append("")

    report.append("lru_cache sizes:")

    report.extend(
        _cache_info_lines()
    )

    report.append("")

    if tracemalloc.is_tracing():
        snapshot = (
            tracemalloc.take_snapshot()
        )

        report.extend(
            _tracemalloc_report_lines(
                snapshot,
                top=args.top,
            )
        )

        tracemalloc.stop()

    report_text = "\n".join(report)

    print()
    print(report_text)

    report_path.write_text(
        report_text + "\n",
        encoding="utf-8",
    )

    print(f"CSV: {csv_path.resolve()}")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
