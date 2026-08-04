from dataclasses import dataclass
from typing import Literal

from solver.draw_range_sampling import (
    DrawSamplingConfig,
    sample_exact_draw_range,
)
from solver.draw_range_transition import (
    DEFAULT_DRAW_TRANSITION_BUDGET,
    DrawTransitionBudget,
    transition_exact_draw_range,
)
from solver.hand_abstraction import (
    ExactHandKey,
)
from solver.information_state import (
    PrivateHandKey,
)
from solver.strategy_index import (
    Strategy,
)


DrawTransitionMode = Literal[
    "exact",
    "sample",
    "auto",
]


@dataclass(frozen=True)
class DrawTransitionConfig:
    """
    Controls exact and sampled draw-range
    transitions.

    exact:
        Always use exact enumeration.

    sample:
        Always use Monte Carlo sampling.

    auto:
        Try exact enumeration first.
        If the exact workload exceeds the
        configured budget, use sampling.
    """

    mode: DrawTransitionMode = "auto"

    exact_budget: DrawTransitionBudget = (
        DEFAULT_DRAW_TRANSITION_BUDGET
    )

    sampling: DrawSamplingConfig = (
        DrawSamplingConfig()
    )

    def __post_init__(self) -> None:
        if self.mode not in {
            "exact",
            "sample",
            "auto",
        }:
            raise ValueError(
                "Unknown draw transition "
                f"mode: {self.mode}"
            )


@dataclass(frozen=True)
class DrawTransitionResult:
    """
    Result of one draw-range transition.

    method records whether the returned
    distribution came from exact enumeration
    or Monte Carlo sampling.
    """

    weights: dict[
        ExactHandKey,
        float,
    ]

    method: Literal[
        "exact",
        "sample",
    ]

    @property
    def hand_count(self) -> int:
        return len(
            self.weights
        )

    @property
    def total_weight(self) -> float:
        return sum(
            self.weights.values()
        )


def transition_draw_range(
    *,
    pre_draw_weights: dict[
        ExactHandKey,
        float,
    ],
    strategies: dict[
        PrivateHandKey,
        Strategy,
    ],
    public_draw_count: int,
    config: DrawTransitionConfig = (
        DrawTransitionConfig()
    ),
    normalize: bool = True,
) -> DrawTransitionResult:
    """
    Run an exact, sampled, or automatic
    exact-to-sampling draw transition.
    """
    if config.mode == "exact":
        weights = transition_exact_draw_range(
            pre_draw_weights=(
                pre_draw_weights
            ),
            strategies=strategies,
            public_draw_count=(
                public_draw_count
            ),
            normalize=normalize,
            budget=config.exact_budget,
        )

        return DrawTransitionResult(
            weights=weights,
            method="exact",
        )

    if config.mode == "sample":
        weights = sample_exact_draw_range(
            pre_draw_weights=(
                pre_draw_weights
            ),
            strategies=strategies,
            public_draw_count=(
                public_draw_count
            ),
            config=config.sampling,
            normalize=normalize,
        )

        return DrawTransitionResult(
            weights=weights,
            method="sample",
        )

    try:
        weights = transition_exact_draw_range(
            pre_draw_weights=(
                pre_draw_weights
            ),
            strategies=strategies,
            public_draw_count=(
                public_draw_count
            ),
            normalize=normalize,
            budget=config.exact_budget,
        )

        return DrawTransitionResult(
            weights=weights,
            method="exact",
        )

    except RuntimeError as error:
        if not _is_budget_error(
            error
        ):
            raise

    weights = sample_exact_draw_range(
        pre_draw_weights=(
            pre_draw_weights
        ),
        strategies=strategies,
        public_draw_count=(
            public_draw_count
        ),
        config=config.sampling,
        normalize=normalize,
    )

    return DrawTransitionResult(
        weights=weights,
        method="sample",
    )


def _is_budget_error(
    error: RuntimeError,
) -> bool:
    message = str(
        error
    )

    return (
        "configured budget" in message
        or (
            "hand-action pair budget"
            in message
        )
    )