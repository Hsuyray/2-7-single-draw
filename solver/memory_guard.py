"""
Process-memory (RSS) guard for long training runs.

Measurement only. Nothing here touches CFR logic,
RNG state, or checkpoint contents.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass


BYTES_PER_GB = 1024 ** 3

DEFAULT_MAX_RSS_GB = 3.0

DEFAULT_RSS_CHECK_EVERY = 100


def current_rss_bytes() -> int:
    """
    Resident set size of this process, in bytes.

    psutil is imported lazily so that a disabled
    guard never needs it.
    """
    import psutil

    return int(
        psutil.Process().memory_info().rss
    )


def peak_rss_bytes() -> int | None:
    """
    High-water mark of this process's resident memory, in bytes,
    or None where the platform does not report it.

    Windows: psutil's peak_wset. Linux/macOS: resource.ru_maxrss
    (kilobytes on Linux, bytes on macOS). Unlike a sampled RSS, the
    high-water mark includes short peaks, such as the one reached
    while a checkpoint is being built and written.
    """
    import sys

    import psutil

    info = psutil.Process().memory_info()

    peak = getattr(info, "peak_wset", None)

    if peak is not None:
        return int(peak)

    try:
        import resource
    except ImportError:
        return None

    maxrss = resource.getrusage(
        resource.RUSAGE_SELF
    ).ru_maxrss

    if sys.platform == "darwin":
        return int(maxrss)

    return int(maxrss) * 1024


def bytes_to_gb(
    value: int,
) -> float:
    return value / BYTES_PER_GB


@dataclass(frozen=True)
class RSSCheck:
    rss_bytes: int
    limit_bytes: int

    @property
    def rss_gb(self) -> float:
        return bytes_to_gb(
            self.rss_bytes
        )

    @property
    def limit_gb(self) -> float:
        return bytes_to_gb(
            self.limit_bytes
        )

    @property
    def exceeded(self) -> bool:
        return (
            self.rss_bytes
            > self.limit_bytes
        )


@dataclass(frozen=True)
class RSSGuard:
    """
    max_rss_gb <= 0 disables the guard. A disabled
    guard never calls rss_reader.
    """

    max_rss_gb: float

    rss_reader: Callable[[], int] = (
        current_rss_bytes
    )

    @property
    def enabled(self) -> bool:
        return self.max_rss_gb > 0

    @property
    def limit_bytes(self) -> int:
        if not self.enabled:
            raise RuntimeError(
                "Disabled RSS guard has "
                "no limit."
            )

        return int(
            self.max_rss_gb
            * BYTES_PER_GB
        )

    def check(
        self,
    ) -> RSSCheck | None:
        if not self.enabled:
            return None

        return RSSCheck(
            rss_bytes=int(
                self.rss_reader()
            ),
            limit_bytes=(
                self.limit_bytes
            ),
        )


def iteration_chunks(
    total_iterations: int,
    chunk_size: int,
) -> Iterator[int]:
    """
    Split total_iterations into consecutive chunk
    sizes of at most chunk_size. The chunks sum to
    total_iterations.
    """
    if total_iterations < 0:
        raise ValueError(
            "Total iterations cannot "
            "be negative."
        )

    if chunk_size <= 0:
        raise ValueError(
            "Chunk size must be positive."
        )

    remaining = total_iterations

    while remaining > 0:
        this_chunk = min(
            chunk_size,
            remaining,
        )

        yield this_chunk

        remaining -= this_chunk
