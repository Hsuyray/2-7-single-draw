import pickle
from dataclasses import dataclass
from pathlib import Path

from solver.information_state import (
    AbstractionMode,
)
from solver.starting_range import (
    StartingRange,
)
from solver.starting_range_builder import (
    StartingRangeBuilder,
)


DEFAULT_CACHE_DIR = Path(
    "data"
) / "starting_ranges"


@dataclass(frozen=True)
class StartingRangeCache:
    cache_dir: Path = DEFAULT_CACHE_DIR

    def cache_path(
        self,
        abstraction: AbstractionMode,
    ) -> Path:
        return (
            self.cache_dir
            / f"starting_range_{abstraction}.pkl"
        )

    def exists(
        self,
        abstraction: AbstractionMode,
    ) -> bool:
        return self.cache_path(
            abstraction
        ).exists()

    def save(
        self,
        *,
        abstraction: AbstractionMode,
        starting_range: StartingRange,
    ) -> Path:
        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = self.cache_path(
            abstraction
        )

        with path.open("wb") as file:
            pickle.dump(
                starting_range,
                file,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        return path

    def load(
        self,
        abstraction: AbstractionMode,
    ) -> StartingRange:
        path = self.cache_path(
            abstraction
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Starting-range cache does not exist: {path}"
            )

        with path.open("rb") as file:
            starting_range = pickle.load(
                file
            )

        if not isinstance(
            starting_range,
            StartingRange,
        ):
            raise TypeError(
                "Cached object is not a StartingRange."
            )

        return starting_range

    def load_or_build(
        self,
        abstraction: AbstractionMode,
    ) -> StartingRange:
        if self.exists(
            abstraction
        ):
            return self.load(
                abstraction
            )

        builder = StartingRangeBuilder(
            abstraction=abstraction
        )

        starting_range = builder.build()

        self.save(
            abstraction=abstraction,
            starting_range=starting_range,
        )

        return starting_range