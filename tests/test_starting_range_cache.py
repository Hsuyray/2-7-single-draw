from pathlib import Path

import pytest

from solver.hand_universe import (
    count_exact_keys,
    iter_starting_hands,
)
from solver.starting_range import (
    StartingRange,
)
from solver.starting_range_cache import (
    StartingRangeCache,
)


def make_small_range() -> StartingRange:
    hands = []

    for hand in iter_starting_hands():
        hands.append(
            hand
        )

        if len(hands) == 100:
            break

    counts = count_exact_keys(
        hands
    )

    return StartingRange.from_counts(
        counts
    )


def test_cache_path_depends_on_abstraction(
    tmp_path: Path,
) -> None:
    cache = StartingRangeCache(
        cache_dir=tmp_path
    )

    exact = cache.cache_path(
        "exact"
    )

    bucket = cache.cache_path(
        "bucket"
    )

    assert exact != bucket

    assert (
        exact.name
        == "starting_range_exact.pkl"
    )

    assert (
        bucket.name
        == "starting_range_bucket.pkl"
    )


def test_cache_does_not_exist_initially(
    tmp_path: Path,
) -> None:
    cache = StartingRangeCache(
        cache_dir=tmp_path
    )

    assert not cache.exists(
        "exact"
    )


def test_save_creates_cache_file(
    tmp_path: Path,
) -> None:
    cache = StartingRangeCache(
        cache_dir=tmp_path
    )

    starting_range = (
        make_small_range()
    )

    path = cache.save(
        abstraction="exact",
        starting_range=starting_range,
    )

    assert path.exists()

    assert cache.exists(
        "exact"
    )


def test_save_and_load_round_trip(
    tmp_path: Path,
) -> None:
    cache = StartingRangeCache(
        cache_dir=tmp_path
    )

    starting_range = (
        make_small_range()
    )

    cache.save(
        abstraction="exact",
        starting_range=starting_range,
    )

    loaded = cache.load(
        "exact"
    )

    assert (
        loaded.weights
        == starting_range.weights
    )

    assert (
        loaded.total_weight
        == starting_range.total_weight
    )


def test_loading_missing_cache_raises(
    tmp_path: Path,
) -> None:
    cache = StartingRangeCache(
        cache_dir=tmp_path
    )

    with pytest.raises(
        FileNotFoundError
    ):
        cache.load(
            "exact"
        )