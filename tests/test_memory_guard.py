from collections.abc import Callable
from pathlib import Path
import sys

import pytest

from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.memory_guard import (
    BYTES_PER_GB,
    DEFAULT_MAX_RSS_GB,
    RSSGuard,
    iteration_chunks,
)
from solver.single_draw_game import SingleDrawGame


def make_reader(
    values_gb: list[float],
) -> tuple[Callable[[], int], list[int]]:
    """
    Fake RSS reader. Returns values_gb in order,
    then repeats the last value. Records calls.
    """
    values = [
        int(value * BYTES_PER_GB)
        for value in values_gb
    ]

    calls: list[int] = []

    def reader() -> int:
        index = min(
            len(calls),
            len(values) - 1,
        )

        calls.append(index)

        return values[index]

    return reader, calls


def failing_reader() -> int:
    raise AssertionError(
        "Disabled guard must not read RSS."
    )


def test_default_limit_is_three_gb() -> None:
    assert DEFAULT_MAX_RSS_GB == 3.0

    guard = RSSGuard(
        max_rss_gb=DEFAULT_MAX_RSS_GB,
        rss_reader=failing_reader,
    )

    assert guard.enabled is True
    assert guard.limit_bytes == 3 * BYTES_PER_GB


def test_zero_limit_disables_guard_without_reading_rss() -> None:
    guard = RSSGuard(
        max_rss_gb=0.0,
        rss_reader=failing_reader,
    )

    assert guard.enabled is False
    assert guard.check() is None

    with pytest.raises(RuntimeError):
        guard.limit_bytes


def test_rss_below_limit_is_not_exceeded() -> None:
    reader, calls = make_reader([2.0])

    check = RSSGuard(
        max_rss_gb=3.0,
        rss_reader=reader,
    ).check()

    assert check is not None
    assert check.exceeded is False
    assert check.rss_gb == pytest.approx(2.0)
    assert check.limit_gb == pytest.approx(3.0)
    assert calls == [0]


def test_rss_above_limit_is_exceeded() -> None:
    reader, _ = make_reader([3.5])

    check = RSSGuard(
        max_rss_gb=3.0,
        rss_reader=reader,
    ).check()

    assert check is not None
    assert check.exceeded is True


def test_rss_equal_to_limit_is_not_exceeded() -> None:
    reader, _ = make_reader([3.0])

    check = RSSGuard(
        max_rss_gb=3.0,
        rss_reader=reader,
    ).check()

    assert check is not None
    assert check.exceeded is False


def test_iteration_chunks_cover_total() -> None:
    assert list(iteration_chunks(10, 3)) == [3, 3, 3, 1]
    assert list(iteration_chunks(6, 3)) == [3, 3]
    assert list(iteration_chunks(2, 5)) == [2]
    assert list(iteration_chunks(0, 5)) == []


def test_iteration_chunks_reject_bad_arguments() -> None:
    with pytest.raises(ValueError):
        list(iteration_chunks(10, 0))

    with pytest.raises(ValueError):
        list(iteration_chunks(-1, 5))


def _seeded_factory() -> Callable[[], SingleDrawGame]:
    config = GameConfig(
        player_count=2,
        starting_stack=20.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter

        game = SingleDrawGame(
            config=config,
            button_seat=0,
            deck_seed=42 + counter,
        )

        counter += 1

        return game

    return factory


def test_chunked_training_matches_single_call() -> None:
    """
    The RSS guard splits train() into chunks. This
    must not change nodes, regrets or strategy sums.
    """
    single = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    chunked = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        traversal_mode="external_sampling",
        random_seed=42,
    )

    single.train(
        _seeded_factory(),
        iterations=6,
    )

    chunked_factory = _seeded_factory()

    for chunk_size in iteration_chunks(6, 4):
        chunked.train(
            chunked_factory,
            iterations=chunk_size,
        )

    assert single.completed_iterations == 6
    assert chunked.completed_iterations == 6

    assert (
        list(single.node_store.nodes.keys())
        == list(chunked.node_store.nodes.keys())
    )

    for information_state, node in (
        single.node_store.nodes.items()
    ):
        other = chunked.node_store.nodes[
            information_state
        ]

        assert node.regret_sum == other.regret_sum
        assert node.strategy_sum == other.strategy_sum


# --- save_training_checkpoint loop, with a fake trainer ---


class FakeNodeStore:
    def __len__(self) -> int:
        return 7


class FakeTrainer:
    instances: list["FakeTrainer"] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.resolved_draw_action_mode = "full"
        self.completed_iterations = 0
        self.node_store = FakeNodeStore()
        self.train_calls: list[int] = []
        self.save_calls: list[Path] = []

        FakeTrainer.instances.append(self)

    def train(
        self,
        game_factory: object,
        *,
        iterations: int,
    ) -> None:
        self.train_calls.append(iterations)
        self.completed_iterations += iterations

    def save_checkpoint(
        self,
        path: Path,
    ) -> Path:
        self.save_calls.append(Path(path))
        return Path(path)


def _run_script(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reader: Callable[[], int],
    extra_args: list[str],
) -> FakeTrainer:
    import scripts.save_training_checkpoint as script

    FakeTrainer.instances = []

    monkeypatch.setattr(
        script,
        "CFRTrainer",
        FakeTrainer,
    )

    monkeypatch.setattr(
        script,
        "available_memory_gb",
        lambda: 100.0,
    )

    monkeypatch.setattr(
        script,
        "RSSGuard",
        lambda max_rss_gb: RSSGuard(
            max_rss_gb=max_rss_gb,
            rss_reader=reader,
        ),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "save_training_checkpoint",
            "--output",
            str(tmp_path / "out.chk.gz"),
            "--iterations",
            "1000",
            "--batch-size",
            "500",
            *extra_args,
        ],
    )

    script.main()

    assert len(FakeTrainer.instances) == 1

    return FakeTrainer.instances[0]


def test_script_stops_and_saves_once_when_rss_limit_exceeded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reader, calls = make_reader([0.5, 0.5, 2.0])

    trainer = _run_script(
        monkeypatch,
        tmp_path,
        reader,
        [
            "--max-rss-gb",
            "1.0",
            "--rss-check-every",
            "100",
        ],
    )

    assert trainer.train_calls == [100, 100, 100]
    assert trainer.completed_iterations == 300
    assert len(calls) == 3

    # Only the final save runs after the guard trips.
    assert trainer.save_calls == [tmp_path / "out.chk.gz"]

    output = capsys.readouterr().out

    assert "Training stopped early (RSS limit)" in output
    assert "WARNING: process RSS" in output


def test_script_with_guard_disabled_trains_full_batches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    trainer = _run_script(
        monkeypatch,
        tmp_path,
        failing_reader,
        [
            "--max-rss-gb",
            "0",
        ],
    )

    # Same call pattern as before the guard existed.
    assert trainer.train_calls == [500, 500]
    assert trainer.completed_iterations == 1000

    # One intermediate save per batch, plus the final save.
    assert len(trainer.save_calls) == 3

    output = capsys.readouterr().out

    assert "Training completed" in output
    assert "max RSS (GB): disabled" in output


def test_script_with_guard_not_triggered_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reader, calls = make_reader([0.5])

    trainer = _run_script(
        monkeypatch,
        tmp_path,
        reader,
        [
            "--max-rss-gb",
            "3.0",
            "--rss-check-every",
            "250",
        ],
    )

    assert trainer.train_calls == [250, 250, 250, 250]
    assert trainer.completed_iterations == 1000
    assert len(calls) == 4
    assert len(trainer.save_calls) == 3

    output = capsys.readouterr().out

    assert "Training completed" in output


def test_script_rejects_negative_rss_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        _run_script(
            monkeypatch,
            tmp_path,
            failing_reader,
            [
                "--max-rss-gb",
                "-1",
            ],
        )
