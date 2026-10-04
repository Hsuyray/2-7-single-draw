import csv
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.profile_memory import (
    CSV_FIELDS,
    HARD_MAX_ITERATIONS,
    action_count_histogram,
    build_sample_row,
    default_csv_path,
    format_sample_line,
    nodes_by_phase,
    parse_args,
    peak_rss_bytes,
    validate_args,
)
from solver.memory_guard import BYTES_PER_GB


def test_default_args_are_small_max_draw_five_seed_42() -> None:
    args = parse_args([])

    validate_args(args)

    assert args.max_draw == 5
    assert args.seed == 42
    assert args.iterations == 300
    assert args.iterations <= HARD_MAX_ITERATIONS
    assert args.max_rss_gb == 3.0


@pytest.mark.parametrize(
    "argv",
    [
        ["--iterations", "0"],
        ["--iterations", str(HARD_MAX_ITERATIONS + 1)],
        ["--sample-every", "0"],
        ["--max-rss-gb", "-1"],
        ["--top", "0"],
        ["--tracemalloc-frames", "0"],
        ["--draw-action-mode", "candidate"],
    ],
)
def test_invalid_args_are_rejected(
    argv: list[str],
) -> None:
    with pytest.raises(ValueError):
        validate_args(parse_args(argv))


def test_hard_cap_itself_is_allowed() -> None:
    validate_args(
        parse_args(
            ["--iterations", str(HARD_MAX_ITERATIONS)]
        )
    )


def test_default_csv_path_encodes_config() -> None:
    path = default_csv_path(
        max_draw=5,
        abstraction="bucket",
        bet_sizing="fast",
        seed=42,
        iterations=300,
    )

    assert path == (
        Path("experiments")
        / "memory_profile"
        / "profile_md5_bucket_fast_s42_it300.csv"
    )


def test_sample_row_without_tracemalloc() -> None:
    row = build_sample_row(
        event="sample",
        iteration=25,
        cfr_nodes=1_234,
        rss_bytes=int(1.5 * BYTES_PER_GB),
        traced=None,
        elapsed_seconds=1.23456,
    )

    assert tuple(row) == CSV_FIELDS
    assert row["iteration"] == 25
    assert row["cfr_nodes"] == 1_234
    assert row["rss_gb"] == 1.5
    assert row["traced_current_bytes"] == ""
    assert row["traced_peak_bytes"] == ""
    assert row["elapsed_seconds"] == 1.235


def test_sample_row_with_tracemalloc() -> None:
    row = build_sample_row(
        event="start",
        iteration=0,
        cfr_nodes=0,
        rss_bytes=100,
        traced=(10, 20),
        elapsed_seconds=0.0,
    )

    assert row["traced_current_bytes"] == 10
    assert row["traced_peak_bytes"] == 20


def test_sample_rows_round_trip_through_csv() -> None:
    rows = [
        build_sample_row(
            event="sample",
            iteration=iteration,
            cfr_nodes=iteration * 10,
            rss_bytes=iteration * 1_000,
            traced=None,
            elapsed_seconds=float(iteration),
        )
        for iteration in (25, 50)
    ]

    buffer = io.StringIO()

    writer = csv.DictWriter(
        buffer,
        fieldnames=CSV_FIELDS,
    )

    writer.writeheader()
    writer.writerows(rows)

    buffer.seek(0)

    read_back = list(csv.DictReader(buffer))

    assert [row["iteration"] for row in read_back] == ["25", "50"]
    assert [row["cfr_nodes"] for row in read_back] == ["250", "500"]
    assert tuple(read_back[0]) == CSV_FIELDS


def test_format_sample_line() -> None:
    row = build_sample_row(
        event="sample",
        iteration=50,
        cfr_nodes=7,
        rss_bytes=BYTES_PER_GB,
        traced=None,
        elapsed_seconds=2.0,
    )

    line = format_sample_line(row)

    assert line.startswith("[sample] ")
    assert "iteration=50" in line
    assert "CFR_nodes=7" in line
    assert "rss=1.0GB" in line


def test_nodes_by_phase_counts_and_sorts() -> None:
    states = [
        SimpleNamespace(phase="postdraw_betting"),
        SimpleNamespace(phase="draw"),
        SimpleNamespace(phase="draw"),
        SimpleNamespace(phase="predraw_betting"),
    ]

    assert nodes_by_phase(states) == {
        "draw": 2,
        "postdraw_betting": 1,
        "predraw_betting": 1,
    }


def test_action_count_histogram() -> None:
    nodes = [
        SimpleNamespace(actions=("a", "b")),
        SimpleNamespace(actions=("a", "b", "c")),
        SimpleNamespace(actions=("x", "y")),
    ]

    assert action_count_histogram(nodes) == {
        2: 2,
        3: 1,
    }


def test_peak_rss_bytes() -> None:
    rows = [
        {"rss_bytes": 5},
        {"rss_bytes": 9},
        {"rss_bytes": 7},
    ]

    assert peak_rss_bytes(rows) == 9
    assert peak_rss_bytes([]) == 0
