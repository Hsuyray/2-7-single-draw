import random
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from math import prod
from typing import Literal

from solver.action_executor import (
    apply_solver_action,
)
from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.cfr_action_codec import (
    canonical_solver_actions_for_game,
    executable_solver_action_for_game,
)
from solver.information_state import (
    AbstractionMode,
    InformationState,
)
from solver.legal_actions import (
    DrawActionMode,
    SolverAction,
    legal_actions,
)
from solver.node_store import (
    NodeStore,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)
from solver.strategy_index import (
    StrategyIndex,
)
from solver.terminal_utility import (
    terminal_utility,
)
from pathlib import Path

from solver.strategy_checkpoint import (
    StrategyCheckpointMetadata,
    build_checkpoint_metadata,
    save_strategy_checkpoint,
)

GameFactory = Callable[
    [],
    SingleDrawGame,
]


TraversalMode = Literal[
    "full",
    "external_sampling",
]


DrawActionModeSetting = Literal[
    "auto",
    "full",
    "candidate",
]


@dataclass
class CFRTrainer:
    max_draw: int = 3

    # None:
    #     use bet_sizing_policy
    #
    # ():
    #     disable raises
    #
    # non-empty tuple:
    #     explicit absolute raise-to sizes
    raise_sizes: (
        tuple[float, ...]
        | None
    ) = ()

    bet_sizing_policy: (
        BetSizingPolicy
        | None
    ) = None

    abstraction: AbstractionMode = "exact"

    traversal_mode: TraversalMode = "full"

    draw_action_mode: (
        DrawActionModeSetting
    ) = "auto"

    random_seed: int | None = None

    node_store: NodeStore = field(
        default_factory=NodeStore,
    )

    completed_iterations: int = 0

    _random: random.Random = field(
        init=False,
        repr=False,
    )

    _resolved_draw_action_mode: (
        DrawActionMode
    ) = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.traversal_mode not in {
            "full",
            "external_sampling",
        }:
            raise ValueError(
                "Traversal mode must be "
                "'full' or "
                "'external_sampling'."
            )

        if self.draw_action_mode not in {
            "auto",
            "full",
            "candidate",
        }:
            raise ValueError(
                "Draw action mode must be "
                "'auto', 'full', or "
                "'candidate'."
            )

        if self.max_draw < 0:
            raise ValueError(
                "Maximum draw cannot "
                "be negative."
            )

        if self.max_draw > 5:
            raise ValueError(
                "Maximum draw cannot "
                "exceed five cards."
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
                "Raise sizes cannot "
                "be negative."
            )

        if (
            self.abstraction == "bucket"
            and self.draw_action_mode
            == "candidate"
        ):
            raise ValueError(
                "Bucket abstraction currently "
                "requires full draw actions. "
                "Candidate actions may differ "
                "between hands sharing the "
                "same bucket."
            )

        self._resolved_draw_action_mode = (
            self._resolve_draw_action_mode()
        )
    
        self._random = random.Random(
            self.random_seed
        )

    @property
    def resolved_draw_action_mode(
        self,
    ) -> DrawActionMode:
        return (
            self._resolved_draw_action_mode
        )

    @property
    def uses_bet_sizing_policy(
        self,
    ) -> bool:
        return self.raise_sizes is None

    def _resolve_draw_action_mode(
        self,
    ) -> DrawActionMode:
        if self.draw_action_mode == "full":
            return "full"

        if (
            self.draw_action_mode
            == "candidate"
        ):
            return "candidate"

        return "full"

    def train(
        self,
        game_factory: GameFactory,
        *,
        iterations: int,
    ) -> None:
        if iterations <= 0:
            raise ValueError(
                "Iterations must be positive."
            )

        for _ in range(iterations):
            sampled_game = game_factory()

            self._validate_game(
                sampled_game
            )

            for traversing_seat in range(2):
                game_copy = deepcopy(
                    sampled_game
                )

                if (
                    self.traversal_mode
                    == "full"
                ):
                    self._full_cfr(
                        game=game_copy,
                        traversing_seat=(
                            traversing_seat
                        ),
                        reach_probabilities=(
                            1.0,
                            1.0,
                        ),
                    )

                else:
                    self._external_sampling_cfr(
                        game=game_copy,
                        traversing_seat=(
                            traversing_seat
                        ),
                        traverser_reach=1.0,
                    )

            self.completed_iterations += 1

    def _full_cfr(
        self,
        *,
        game: SingleDrawGame,
        traversing_seat: int,
        reach_probabilities: tuple[
            float,
            float,
        ],
    ) -> float:
        if game.phase == GamePhase.COMPLETE:
            return terminal_utility(
                game,
                seat=traversing_seat,
            )

        acting_seat = game.acting_seat

        if acting_seat is None:
            raise RuntimeError(
                "Non-terminal game has no "
                "acting player."
            )

        actions = self._legal_actions(
            game
        )

        if not actions:
            raise RuntimeError(
                "Non-terminal game has no "
                "legal actions."
            )

        node = self._get_node(
            game=game,
            acting_seat=acting_seat,
            actions=actions,
        )

        strategy = (
            node.current_strategy()
        )

        if (
            acting_seat
            == traversing_seat
        ):
            node.accumulate_strategy(
                realization_weight=(
                    reach_probabilities[
                        acting_seat
                    ]
                )
            )

        action_utilities: dict[
            SolverAction,
            float,
        ] = {}

        node_utility = 0.0

        for action in actions:
            next_game = (
                self._apply_node_action(
                    game=game,
                    action=action,
                )
            )

            next_reach = list(
                reach_probabilities
            )

            next_reach[
                acting_seat
            ] *= strategy[
                action
            ]

            action_utility = self._full_cfr(
                game=next_game,
                traversing_seat=(
                    traversing_seat
                ),
                reach_probabilities=(
                    next_reach[0],
                    next_reach[1],
                ),
            )

            action_utilities[
                action
            ] = action_utility

            node_utility += (
                strategy[action]
                * action_utility
            )

        if (
            acting_seat
            == traversing_seat
        ):
            counterfactual_reach = prod(
                probability
                for seat, probability
                in enumerate(
                    reach_probabilities
                )
                if seat
                != traversing_seat
            )

            regrets = {
                action: (
                    counterfactual_reach
                    * (
                        action_utilities[
                            action
                        ]
                        - node_utility
                    )
                )
                for action in actions
            }

            node.add_regrets(
                regrets
            )

        return node_utility

    def _external_sampling_cfr(
        self,
        *,
        game: SingleDrawGame,
        traversing_seat: int,
        traverser_reach: float,
    ) -> float:
        if game.phase == GamePhase.COMPLETE:
            return terminal_utility(
                game,
                seat=traversing_seat,
            )

        acting_seat = game.acting_seat

        if acting_seat is None:
            raise RuntimeError(
                "Non-terminal game has no "
                "acting player."
            )

        actions = self._legal_actions(
            game
        )

        if not actions:
            raise RuntimeError(
                "Non-terminal game has no "
                "legal actions."
            )

        node = self._get_node(
            game=game,
            acting_seat=acting_seat,
            actions=actions,
        )

        strategy = (
            node.current_strategy()
        )

        if (
            acting_seat
            != traversing_seat
        ):
            sampled_action = (
                self._sample_action(
                    actions=actions,
                    strategy=strategy,
                )
            )

            next_game = (
                self._apply_node_action(
                    game=game,
                    action=sampled_action,
                )
            )

            return (
                self._external_sampling_cfr(
                    game=next_game,
                    traversing_seat=(
                        traversing_seat
                    ),
                    traverser_reach=(
                        traverser_reach
                    ),
                )
            )

        node.accumulate_strategy(
            realization_weight=(
                traverser_reach
            )
        )

        action_utilities: dict[
            SolverAction,
            float,
        ] = {}

        node_utility = 0.0

        for action in actions:
            next_game = (
                self._apply_node_action(
                    game=game,
                    action=action,
                )
            )

            action_utility = (
                self._external_sampling_cfr(
                    game=next_game,
                    traversing_seat=(
                        traversing_seat
                    ),
                    traverser_reach=(
                        traverser_reach
                        * strategy[action]
                    ),
                )
            )

            action_utilities[
                action
            ] = action_utility

            node_utility += (
                strategy[action]
                * action_utility
            )

        regrets = {
            action: (
                action_utilities[action]
                - node_utility
            )
            for action in actions
        }

        node.add_regrets(
            regrets
        )

        return node_utility

    def _legal_actions(
        self,
        game: SingleDrawGame,
    ) -> tuple[
        SolverAction,
        ...,
    ]:
        actual_actions = legal_actions(
            game,
            max_draw=self.max_draw,
            raise_sizes=(
                self.raise_sizes
            ),
            bet_sizing_policy=(
                self.bet_sizing_policy
            ),
            draw_action_mode=(
                self._resolved_draw_action_mode
            ),
        )

        if (
            self.abstraction
            != "exact"
        ):
            return actual_actions

        return canonical_solver_actions_for_game(
            game=game,
            actions=actual_actions,
        )

    def _apply_node_action(
        self,
        *,
        game: SingleDrawGame,
        action: SolverAction,
    ) -> SingleDrawGame:
        """
        Execute one CFR node action.

        Exact-mode draw actions are stored in
        canonical index space and translated
        back into the current physical hand
        ordering before execution.
        """
        executable_action = action

        if self.abstraction == "exact":
            executable_action = (
                executable_solver_action_for_game(
                    game=game,
                    action=action,
                )
            )

        return apply_solver_action(
            game,
            executable_action,
        )

    def _get_node(
        self,
        *,
        game: SingleDrawGame,
        acting_seat: int,
        actions: tuple[
            SolverAction,
            ...,
        ],
    ):
        information_state = (
            InformationState.from_game(
                game,
                observer_seat=acting_seat,
                abstraction=(
                    self.abstraction
                ),
            )
        )

        node = (
            self.node_store.get_or_create(
                information_state,
                actions,
            )
        )

        node.record_visit()

        return node

    def _sample_action(
        self,
        *,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: dict[
            SolverAction,
            float,
        ],
    ) -> SolverAction:
        threshold = (
            self._random.random()
        )

        cumulative_probability = 0.0

        for action in actions:
            cumulative_probability += (
                strategy[action]
            )

            if (
                threshold
                <= cumulative_probability
            ):
                return action

        return actions[-1]

    def average_strategies(
        self,
    ) -> dict:
        return (
            self.node_store
            .average_strategies()
        )

    def strategy_index(
        self,
    ) -> StrategyIndex:
        return (
            StrategyIndex.from_strategies(
                self.average_strategies()
            )
        )

    def checkpoint_metadata(
        self,
    ) -> StrategyCheckpointMetadata:
        """
        Build checkpoint metadata from the
        trainer's current configuration.
        """
        return build_checkpoint_metadata(
            abstraction=self.abstraction,
            max_draw=self.max_draw,
            draw_action_mode=(
                self.resolved_draw_action_mode
            ),
            completed_iterations=(
                self.completed_iterations
            ),
            raise_sizes=self.raise_sizes,
        )

    def save_checkpoint(
        self,
        path: str | Path,
    ) -> Path:
        """
        Save the trainer's current average
        strategy as a compressed checkpoint.
        """
        if len(self.node_store) == 0:
            raise RuntimeError(
                "Cannot save a checkpoint "
                "before any CFR nodes have "
                "been trained."
            )

        strategy_index = (
            self.strategy_index()
        )

        return save_strategy_checkpoint(
            path,
            strategy_index=strategy_index,
            metadata=(
                self.checkpoint_metadata()
            ),
        )
    
    def _validate_game(
        self,
        game: SingleDrawGame,
    ) -> None:
        if game.config.player_count != 2:
            raise ValueError(
                "This CFR prototype "
                "currently supports "
                "heads-up games only."
            )

        if game.phase not in {
            GamePhase.PREDRAW_BETTING,
            GamePhase.DRAW,
        }:
            raise ValueError(
                "Training games must begin "
                "during pre-draw betting "
                "or the draw phase."
            )