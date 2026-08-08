from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
)
import gzip
from pathlib import Path
import pickle
from typing import Any

from solver.bet_sizing import (
    BetSizingPolicy,
)
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


CHECKPOINT_FORMAT_VERSION = 2
SUPPORTED_CHECKPOINT_VERSIONS = {
    1,
    2,
}

CHECKPOINT_GAME = "2-7-single-draw"


@dataclass(frozen=True)
class StrategyCheckpointMetadata:
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

    bet_sizing_mode: str = "none"

    bet_pot_fractions: (
        tuple[float, ...]
        | None
    ) = None

    bet_include_all_in: (
        bool
        | None
    ) = None

    bet_all_in_threshold: (
        float
        | None
    ) = None

    bet_chip_increment: (
        float
        | None
    ) = None

    def __post_init__(self) -> None:
        if self.format_version not in (
            SUPPORTED_CHECKPOINT_VERSIONS
        ):
            raise ValueError(
                "Unsupported checkpoint "
                "format version."
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

        if self.bet_sizing_mode not in {
            "none",
            "fixed",
            "policy",
        }:
            raise ValueError(
                "Unknown checkpoint betting "
                "sizing mode."
            )

        if (
            self.bet_pot_fractions
            is not None
            and any(
                fraction <= 0
                for fraction
                in self.bet_pot_fractions
            )
        ):
            raise ValueError(
                "Checkpoint pot fractions "
                "must be positive."
            )


@dataclass(frozen=True)
class LoadedStrategyCheckpoint:
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
    bet_sizing_policy: (
        BetSizingPolicy
        | None
    ) = None,
) -> StrategyCheckpointMetadata:
    (
        bet_sizing_mode,
        pot_fractions,
        include_all_in,
        all_in_threshold,
        chip_increment,
    ) = _betting_metadata(
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
    )

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
        bet_sizing_mode=(
            bet_sizing_mode
        ),
        bet_pot_fractions=(
            pot_fractions
        ),
        bet_include_all_in=(
            include_all_in
        ),
        bet_all_in_threshold=(
            all_in_threshold
        ),
        bet_chip_increment=(
            chip_increment
        ),
    )


def save_strategy_checkpoint(
    path: str | Path,
    *,
    strategy_index: StrategyIndex,
    metadata: StrategyCheckpointMetadata,
) -> Path:
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
            CHECKPOINT_FORMAT_VERSION
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

    if format_version not in (
        SUPPORTED_CHECKPOINT_VERSIONS
    ):
        raise ValueError(
            "Unsupported checkpoint format "
            f"version: {format_version}"
        )

    raw_metadata = payload.get(
        "metadata"
    )

    if not isinstance(
        raw_metadata,
        StrategyCheckpointMetadata,
    ):
        raise ValueError(
            "Checkpoint metadata is missing "
            "or invalid."
        )

    metadata = _upgrade_metadata(
        raw_metadata,
        payload_version=format_version,
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


def _betting_metadata(
    *,
    raise_sizes: (
        tuple[float, ...]
        | None
    ),
    bet_sizing_policy: (
        BetSizingPolicy
        | None
    ),
) -> tuple[
    str,
    tuple[float, ...] | None,
    bool | None,
    float | None,
    float | None,
]:
    if raise_sizes == ():
        return (
            "none",
            None,
            None,
            None,
            None,
        )

    if raise_sizes is not None:
        return (
            "fixed",
            None,
            None,
            None,
            None,
        )

    policy = (
        bet_sizing_policy
        if bet_sizing_policy is not None
        else BetSizingPolicy()
    )

    return (
        "policy",
        policy.pot_fractions,
        policy.include_all_in,
        policy.all_in_threshold,
        policy.chip_increment,
    )


def _upgrade_metadata(
    metadata: StrategyCheckpointMetadata,
    *,
    payload_version: int,
) -> StrategyCheckpointMetadata:
    if payload_version == 2:
        return metadata

    raise_sizes = getattr(
        metadata,
        "raise_sizes",
        (),
    )

    if raise_sizes == ():
        bet_sizing_mode = "none"
    elif raise_sizes is None:
        bet_sizing_mode = "policy"
    else:
        bet_sizing_mode = "fixed"

    return StrategyCheckpointMetadata(
        format_version=1,
        game=getattr(
            metadata,
            "game",
            CHECKPOINT_GAME,
        ),
        created_at_utc=getattr(
            metadata,
            "created_at_utc",
            "",
        ),
        abstraction=getattr(
            metadata,
            "abstraction",
            "exact",
        ),
        max_draw=getattr(
            metadata,
            "max_draw",
            3,
        ),
        draw_action_mode=getattr(
            metadata,
            "draw_action_mode",
            "full",
        ),
        completed_iterations=getattr(
            metadata,
            "completed_iterations",
            0,
        ),
        raise_sizes=raise_sizes,
        bet_sizing_mode=(
            bet_sizing_mode
        ),
        bet_pot_fractions=None,
        bet_include_all_in=None,
        bet_all_in_threshold=None,
        bet_chip_increment=None,
    )


def _validate_metadata_compatibility(
    metadata: StrategyCheckpointMetadata,
) -> None:
    if metadata.format_version not in (
        SUPPORTED_CHECKPOINT_VERSIONS
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