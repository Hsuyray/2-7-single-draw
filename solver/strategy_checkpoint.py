from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
)
import gzip
from pathlib import Path
import pickle
from typing import Any

from solver.information_state import (
    AbstractionMode,
    InformationState,
)
from solver.legal_actions import (
    SolverAction,
)
from solver.strategy_index import (
    StrategyIndex,
)


CHECKPOINT_FORMAT_VERSION = 1
CHECKPOINT_GAME = "2-7-single-draw"


@dataclass(frozen=True)
class StrategyCheckpointMetadata:
    """
    Describes the training configuration
    associated with one saved strategy.
    """

    format_version: int
    game: str
    created_at_utc: str
    abstraction: AbstractionMode
    max_draw: int
    draw_action_mode: str
    completed_iterations: int
    raise_sizes: (
        tuple[float, ...]
        | None
    )

    def __post_init__(self) -> None:
        if self.format_version < 1:
            raise ValueError(
                "Checkpoint format version "
                "must be positive."
            )

        if not self.game:
            raise ValueError(
                "Checkpoint game name cannot "
                "be empty."
            )

        if not (
            0
            <= self.max_draw
            <= 5
        ):
            raise ValueError(
                "Checkpoint max_draw must be "
                "between zero and five."
            )

        if self.completed_iterations < 0:
            raise ValueError(
                "Completed iterations cannot "
                "be negative."
            )

        if (
            self.raise_sizes is not None
            and any(
                raise_to < 0
                for raise_to
                in self.raise_sizes
            )
        ):
            raise ValueError(
                "Checkpoint raise sizes cannot "
                "be negative."
            )


@dataclass(frozen=True)
class LoadedStrategyCheckpoint:
    """
    Fully validated checkpoint returned by
    load_strategy_checkpoint().
    """

    metadata: StrategyCheckpointMetadata
    strategy_index: StrategyIndex

    @property
    def strategy_count(self) -> int:
        return len(
            self.strategy_index
        )


def build_checkpoint_metadata(
    *,
    abstraction: AbstractionMode,
    max_draw: int,
    draw_action_mode: str,
    completed_iterations: int,
    raise_sizes: (
        tuple[float, ...]
        | None
    ),
) -> StrategyCheckpointMetadata:
    return StrategyCheckpointMetadata(
        format_version=(
            CHECKPOINT_FORMAT_VERSION
        ),
        game=CHECKPOINT_GAME,
        created_at_utc=(
            datetime.now(
                UTC
            ).isoformat()
        ),
        abstraction=abstraction,
        max_draw=max_draw,
        draw_action_mode=(
            draw_action_mode
        ),
        completed_iterations=(
            completed_iterations
        ),
        raise_sizes=raise_sizes,
    )


def save_strategy_checkpoint(
    path: str | Path,
    *,
    strategy_index: StrategyIndex,
    metadata: StrategyCheckpointMetadata,
) -> Path:
    """
    Save metadata and solved average
    strategies to a compressed checkpoint.

    Only load checkpoint files produced by a
    trusted source, because pickle is not safe
    for untrusted input.
    """
    _validate_metadata_compatibility(
        metadata
    )

    strategies = (
        strategy_index.strategies()
    )

    _validate_strategy_mapping(
        strategies
    )

    payload = {
        "format_version": (
            metadata.format_version
        ),
        "metadata": metadata,
        "strategies": strategies,
    }

    output_path = Path(
        path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        output_path.with_suffix(
            output_path.suffix
            + ".tmp"
        )
    )

    try:
        with gzip.open(
            temporary_path,
            "wb",
        ) as checkpoint_file:
            pickle.dump(
                payload,
                checkpoint_file,
                protocol=(
                    pickle.HIGHEST_PROTOCOL
                ),
            )

        temporary_path.replace(
            output_path
        )

    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return output_path


def load_strategy_checkpoint(
    path: str | Path,
) -> LoadedStrategyCheckpoint:
    """
    Load and validate a trusted strategy
    checkpoint.
    """
    checkpoint_path = Path(
        path
    )

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Checkpoint does not exist: "
            f"{checkpoint_path}"
        )

    if not checkpoint_path.is_file():
        raise ValueError(
            "Checkpoint path must refer to "
            "a file."
        )

    try:
        with gzip.open(
            checkpoint_path,
            "rb",
        ) as checkpoint_file:
            payload = pickle.load(
                checkpoint_file
            )

    except (
        OSError,
        EOFError,
        pickle.UnpicklingError,
    ) as error:
        raise ValueError(
            "Checkpoint file is invalid or "
            "corrupted."
        ) from error

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Checkpoint payload must be "
            "a dictionary."
        )

    format_version = payload.get(
        "format_version"
    )

    if (
        format_version
        != CHECKPOINT_FORMAT_VERSION
    ):
        raise ValueError(
            "Unsupported checkpoint format "
            f"version: {format_version}"
        )

    metadata = payload.get(
        "metadata"
    )

    if not isinstance(
        metadata,
        StrategyCheckpointMetadata,
    ):
        raise ValueError(
            "Checkpoint metadata is missing "
            "or invalid."
        )

    _validate_metadata_compatibility(
        metadata
    )

    strategies = payload.get(
        "strategies"
    )

    if not isinstance(
        strategies,
        dict,
    ):
        raise ValueError(
            "Checkpoint strategies are "
            "missing or invalid."
        )

    _validate_strategy_mapping(
        strategies
    )

    strategy_index = (
        StrategyIndex.from_strategies(
            strategies
        )
    )

    return LoadedStrategyCheckpoint(
        metadata=metadata,
        strategy_index=(
            strategy_index
        ),
    )


def _validate_metadata_compatibility(
    metadata: StrategyCheckpointMetadata,
) -> None:
    if (
        metadata.format_version
        != CHECKPOINT_FORMAT_VERSION
    ):
        raise ValueError(
            "Unsupported checkpoint format "
            f"version: "
            f"{metadata.format_version}"
        )

    if metadata.game != CHECKPOINT_GAME:
        raise ValueError(
            "Checkpoint was created for a "
            "different game."
        )


def _validate_strategy_mapping(
    strategies: dict[
        Any,
        Any,
    ],
) -> None:
    if not strategies:
        raise ValueError(
            "Checkpoint must contain at "
            "least one strategy."
        )

    for (
        state,
        strategy,
    ) in strategies.items():
        if not isinstance(
            state,
            InformationState,
        ):
            raise ValueError(
                "Checkpoint contains an "
                "invalid information state."
            )

        if not isinstance(
            strategy,
            dict,
        ):
            raise ValueError(
                "Checkpoint contains an "
                "invalid strategy."
            )

        _validate_strategy(
            strategy
        )


def _validate_strategy(
    strategy: dict[
        SolverAction,
        float,
    ],
) -> None:
    if not strategy:
        raise ValueError(
            "Checkpoint strategies cannot "
            "be empty."
        )

    total_probability = 0.0

    for (
        _action,
        probability,
    ) in strategy.items():
        if not isinstance(
            probability,
            (
                int,
                float,
            ),
        ):
            raise ValueError(
                "Checkpoint strategy "
                "probabilities must be "
                "numeric."
            )

        if probability < 0:
            raise ValueError(
                "Checkpoint strategy "
                "probabilities cannot be "
                "negative."
            )

        total_probability += (
            probability
        )

    if abs(
        total_probability
        - 1.0
    ) > 1e-8:
        raise ValueError(
            "Checkpoint strategies must "
            "sum to one."
        )