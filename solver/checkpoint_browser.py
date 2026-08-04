from dataclasses import dataclass
from pathlib import Path
from typing import cast

from solver.draw_transition_policy import (
    DrawTransitionConfig,
)
from solver.legal_actions import (
    DrawActionMode,
)
from solver.public_node_navigator import (
    PublicNodeNavigator,
)
from solver.range_tracker import (
    RangeTracker,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_browser import (
    StrategyBrowser,
)
from solver.strategy_checkpoint import (
    LoadedStrategyCheckpoint,
    load_strategy_checkpoint,
)


@dataclass(frozen=True)
class CheckpointBrowserSession:
    """
    A loaded strategy checkpoint together
    with a StrategyBrowser configured from
    its metadata.
    """

    checkpoint: LoadedStrategyCheckpoint
    browser: StrategyBrowser

    @property
    def completed_iterations(self) -> int:
        return (
            self.checkpoint
            .metadata
            .completed_iterations
        )

    @property
    def strategy_count(self) -> int:
        return (
            self.checkpoint
            .strategy_count
        )


def browser_from_checkpoint(
    path: str | Path,
    *,
    game: SingleDrawGame,
    range_tracker: (
        RangeTracker
        | None
    ) = None,
    draw_transition_config: (
        DrawTransitionConfig
        | None
    ) = None,
) -> CheckpointBrowserSession:
    """
    Load a saved strategy checkpoint and
    create a StrategyBrowser for the supplied
    game state.

    The browser configuration is restored
    from checkpoint metadata:

    - abstraction
    - max_draw
    - draw_action_mode
    - raise_sizes
    """
    checkpoint = (
        load_strategy_checkpoint(
            path
        )
    )

    metadata = checkpoint.metadata

    if metadata.draw_action_mode not in {
        "full",
        "candidate",
    }:
        raise ValueError(
            "Checkpoint draw action mode must "
            "be 'full' or 'candidate'."
        )

    draw_action_mode = cast(
        DrawActionMode,
        metadata.draw_action_mode,
    )

    browser = StrategyBrowser(
        navigator=(
            PublicNodeNavigator.from_game(
                game
            )
        ),
        strategy_index=(
            checkpoint.strategy_index
        ),
        abstraction=metadata.abstraction,
        range_tracker=range_tracker,
        max_draw=metadata.max_draw,
        raise_sizes=metadata.raise_sizes,
        draw_action_mode=(
            draw_action_mode
        ),
        draw_transition_config=(
            draw_transition_config
            if draw_transition_config
            is not None
            else DrawTransitionConfig()
        ),
    )

    return CheckpointBrowserSession(
        checkpoint=checkpoint,
        browser=browser,
    )