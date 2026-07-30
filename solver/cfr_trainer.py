import random
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from math import prod
from typing import Literal

from solver.action_executor import apply_solver_action
from solver.information_state import (
    AbstractionMode,
    InformationState,
)
from solver.strategy_index import StrategyIndex
from solver.legal_actions import (
    DrawActionMode,
    SolverAction,
    legal_actions,
)
from solver.node_store import NodeStore
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)
from solver.terminal_utility import terminal_utility


GameFactory = Callable[[], SingleDrawGame]

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
    raise_sizes: tuple[float, ...] = ()
    abstraction: AbstractionMode = "exact"
    traversal_mode: TraversalMode = "full"
    draw_action_mode: DrawActionModeSetting = "auto"
    random_seed: int | None = None
    node_store: NodeStore = field(
        default_factory=NodeStore,
    )
    completed_iterations: int = 0

    _random: random.Random = field(
        init=False,
        repr=False,
    )

    _resolved_draw_action_mode: DrawActionMode = field(
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
                "'full' or 'external_sampling'."
            )

        if self.draw_action_mode not in {
            "auto",
            "full",
            "candidate",
        }:
            raise ValueError(
                "Draw action mode must be "
                "'auto', 'full', or 'candidate'."
            )

        if self.max_draw < 0:
            raise ValueError(
                "Maximum draw cannot be negative."
            )

        if self.max_draw > 5:
            raise ValueError(
                "Maximum draw cannot exceed "
                "five cards."
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
        return self._resolved_draw_action_mode

    def _resolve_draw_action_mode(
        self,
    ) -> DrawActionMode:
        if self.draw_action_mode == "full":
            return "full"

        if self.draw_action_mode == "candidate":
            return "candidate"

        if self.abstraction == "exact":
            return "full"

        return "candidate"

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

            self._validate_game(sampled_game)

            for traversing_seat in range(2):
                game_copy = deepcopy(
                    sampled_game
                )

                if self.traversal_mode == "full":
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

        actions = self._legal_actions(game)

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

        strategy = node.current_strategy()

        if acting_seat == traversing_seat:
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
            next_game = apply_solver_action(
                game,
                action,
            )

            next_reach = list(
                reach_probabilities
            )

            next_reach[acting_seat] *= (
                strategy[action]
            )

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

            action_utilities[action] = (
                action_utility
            )

            node_utility += (
                strategy[action]
                * action_utility
            )

        if acting_seat == traversing_seat:
            counterfactual_reach = prod(
                probability
                for seat, probability
                in enumerate(
                    reach_probabilities
                )
                if seat != traversing_seat
            )

            regrets = {
                action: (
                    counterfactual_reach
                    * (
                        action_utilities[action]
                        - node_utility
                    )
                )
                for action in actions
            }

            node.add_regrets(regrets)

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

        actions = self._legal_actions(game)

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

        strategy = node.current_strategy()

        if acting_seat != traversing_seat:
            sampled_action = (
                self._sample_action(
                    actions=actions,
                    strategy=strategy,
                )
            )

            next_game = apply_solver_action(
                game,
                sampled_action,
            )

            return self._external_sampling_cfr(
                game=next_game,
                traversing_seat=(
                    traversing_seat
                ),
                traverser_reach=(
                    traverser_reach
                ),
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
            next_game = apply_solver_action(
                game,
                action,
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

            action_utilities[action] = (
                action_utility
            )

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

        node.add_regrets(regrets)

        return node_utility

    def _legal_actions(
        self,
        game: SingleDrawGame,
    ) -> tuple[SolverAction, ...]:
        return legal_actions(
            game,
            max_draw=self.max_draw,
            raise_sizes=self.raise_sizes,
            draw_action_mode=(
                self._resolved_draw_action_mode
            ),
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
                abstraction=self.abstraction,
            )
        )

        node = self.node_store.get_or_create(
            information_state,
            actions,
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
        threshold = self._random.random()
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

        # Prevent floating-point sums such as
        # 0.9999999999999999 from missing all actions.
        return actions[-1]

    def average_strategies(
        self,
    ) -> dict:
        return (
            self.node_store.average_strategies()
        )

    def strategy_index(
        self,
    ) -> StrategyIndex:
        return StrategyIndex.from_strategies(
            self.average_strategies()
        )

    def _validate_game(
        self,
        game: SingleDrawGame,
    ) -> None:
        if game.config.player_count != 2:
            raise ValueError(
                "This CFR prototype currently "
                "supports heads-up games only."
            )

        if game.phase not in {
            GamePhase.PREDRAW_BETTING,
            GamePhase.DRAW,
        }:
            raise ValueError(
                "Training games must begin during "
                "pre-draw betting or the draw phase."
            )


    