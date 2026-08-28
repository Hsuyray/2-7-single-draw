import random
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.information_state import (
    AbstractionMode,
    InformationState,
)
from solver.legal_actions import (
    DrawActionMode,
    SolverAction,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)
from solver.strategy_index import (
    Strategy,
    StrategyIndex,
)
from solver.strategy_profile_evaluator import (
    StrategyProfileEvaluator,
)
from solver.terminal_utility import (
    terminal_utility,
)


GameFactory = Callable[
    [],
    SingleDrawGame,
]


PureResponsePolicy = dict[
    InformationState,
    SolverAction,
]


@dataclass(frozen=True)
class SampledBestResponseResult:
    responder_seat: int

    training_deals: int
    validation_deals: int
    sweeps: int

    baseline_value: float
    response_value: float

    information_states: int
    changed_actions: int

    opponent_strategy_hits: int
    opponent_strategy_misses: int

    @property
    def improvement(self) -> float:
        return (
            self.response_value
            - self.baseline_value
        )

    @property
    def opponent_strategy_coverage(
        self,
    ) -> float:
        total = (
            self.opponent_strategy_hits
            + self.opponent_strategy_misses
        )

        if total == 0:
            return 1.0

        return (
            self.opponent_strategy_hits
            / total
        )

    @property
    def deals(self) -> int:
        """
        Backward-compatible alias used by
        earlier tests/scripts.
        """
        return self.training_deals


class SampledBestResponse:
    """
    External-sampling information-set
    response optimizer.

    This is NOT exact exploitability.

    Training:
      - initial chance/private state is sampled
      - opponent actions are sampled from the
        fixed StrategyIndex
      - responder actions are enumerated
      - sampled action values are aggregated
        by InformationState

    Evaluation:
      - uses independent held-out games
      - opponent actions are sampled
      - responder follows the learned pure
        information-set policy

    The responder never conditions its action
    on the opponent's private hand.
    """

    def __init__(
        self,
        *,
        strategy_index: StrategyIndex,
        abstraction: AbstractionMode,
        responder_seat: int,
        max_draw: int = 3,
        raise_sizes: (
            tuple[float, ...]
            | None
        ) = None,
        bet_sizing_policy: (
            BetSizingPolicy
            | None
        ) = None,
        draw_action_mode: DrawActionMode = "full",
        random_seed: int | None = None,
    ) -> None:
        if responder_seat not in {
            0,
            1,
        }:
            raise ValueError(
                "Responder seat must be "
                "zero or one."
            )

        if not (
            0
            <= max_draw
            <= 5
        ):
            raise ValueError(
                "Maximum draw must be "
                "between zero and five."
            )

        self.strategy_index = (
            strategy_index
        )

        self.abstraction = (
            abstraction
        )

        self.responder_seat = (
            responder_seat
        )

        self.opponent_seat = (
            1
            - responder_seat
        )

        self._random = random.Random(
            random_seed
        )

        self._action_helper = (
            StrategyProfileEvaluator(
                strategy_index=(
                    strategy_index
                ),
                abstraction=(
                    abstraction
                ),
                max_draw=max_draw,
                raise_sizes=raise_sizes,
                bet_sizing_policy=(
                    bet_sizing_policy
                ),
                draw_action_mode=(
                    draw_action_mode
                ),
                random_seed=random_seed,
            )
        )

        self._opponent_hits = 0
        self._opponent_misses = 0

    def optimize(
        self,
        game_factory: GameFactory,
        *,
        deals: int,
        max_sweeps: int = 5,
        validation_game_factory: (
            GameFactory
            | None
        ) = None,
        validation_deals: int | None = None,
    ) -> SampledBestResponseResult:
        if deals <= 0:
            raise ValueError(
                "Deals must be positive."
            )

        if max_sweeps <= 0:
            raise ValueError(
                "Maximum sweeps must be "
                "positive."
            )

        if validation_game_factory is None:
            validation_game_factory = (
                game_factory
            )

        if validation_deals is None:
            validation_deals = deals

        if validation_deals <= 0:
            raise ValueError(
                "Validation deals must be "
                "positive."
            )

        self._opponent_hits = 0
        self._opponent_misses = 0

        policy: PureResponsePolicy = {}

        initial_policy: PureResponsePolicy = {}

        completed_sweeps = 0

        for _ in range(
            max_sweeps
        ):
            completed_sweeps += 1

            action_sums: dict[
                InformationState,
                dict[
                    SolverAction,
                    float,
                ],
            ] = {}

            action_counts: dict[
                InformationState,
                dict[
                    SolverAction,
                    int,
                ],
            ] = {}

            legal_actions_by_state: dict[
                InformationState,
                tuple[
                    SolverAction,
                    ...,
                ],
            ] = {}

            for _deal in range(
                deals
            ):
                game = deepcopy(
                    game_factory()
                )

                self._sampled_response_traversal(
                    game=game,
                    policy=policy,
                    action_sums=action_sums,
                    action_counts=action_counts,
                    legal_actions_by_state=(
                        legal_actions_by_state
                    ),
                )

            changed_this_sweep = 0

            for (
                state,
                actions,
            ) in legal_actions_by_state.items():
                if state not in policy:
                    strategy = (
                        self.strategy_index
                        .strategy_for_state(
                            state
                        )
                    )

                    initial_action = (
                        self._highest_probability_action(
                            actions=actions,
                            strategy=strategy,
                        )
                    )

                    policy[
                        state
                    ] = initial_action

                    initial_policy[
                        state
                    ] = initial_action

                best_action = (
                    policy[
                        state
                    ]
                )

                best_value = (
                    float("-inf")
                )

                for action in actions:
                    count = (
                        action_counts
                        .get(
                            state,
                            {},
                        )
                        .get(
                            action,
                            0,
                        )
                    )

                    if count <= 0:
                        continue

                    total = (
                        action_sums[
                            state
                        ][
                            action
                        ]
                    )

                    mean_value = (
                        total
                        / count
                    )

                    if (
                        mean_value
                        > best_value
                    ):
                        best_value = (
                            mean_value
                        )

                        best_action = (
                            action
                        )

                if (
                    policy[
                        state
                    ]
                    != best_action
                ):
                    policy[
                        state
                    ] = best_action

                    changed_this_sweep += 1

            if (
                changed_this_sweep
                == 0
            ):
                break

        # Evaluate CFR-vs-CFR and response-vs-CFR
        # on fresh held-out games.
        baseline_total = 0.0
        response_total = 0.0

        for _ in range(
            validation_deals
        ):
            base_game = deepcopy(
                validation_game_factory()
            )

            response_game = deepcopy(
                base_game
            )

            baseline_total += (
                self._sample_profile_rollout(
                    base_game
                )
            )

            response_total += (
                self._sample_response_rollout(
                    game=response_game,
                    policy=policy,
                )
            )

        baseline_value = (
            baseline_total
            / validation_deals
        )

        response_value = (
            response_total
            / validation_deals
        )

        changed_actions = sum(
            1
            for (
                state,
                action,
            )
            in policy.items()
            if (
                initial_policy.get(
                    state
                )
                != action
            )
        )

        return SampledBestResponseResult(
            responder_seat=(
                self.responder_seat
            ),
            training_deals=deals,
            validation_deals=(
                validation_deals
            ),
            sweeps=(
                completed_sweeps
            ),
            baseline_value=(
                baseline_value
            ),
            response_value=(
                response_value
            ),
            information_states=(
                len(
                    policy
                )
            ),
            changed_actions=(
                changed_actions
            ),
            opponent_strategy_hits=(
                self._opponent_hits
            ),
            opponent_strategy_misses=(
                self._opponent_misses
            ),
        )

    def _sampled_response_traversal(
        self,
        *,
        game: SingleDrawGame,
        policy: PureResponsePolicy,
        action_sums: dict[
            InformationState,
            dict[
                SolverAction,
                float,
            ],
        ],
        action_counts: dict[
            InformationState,
            dict[
                SolverAction,
                int,
            ],
        ],
        legal_actions_by_state: dict[
            InformationState,
            tuple[
                SolverAction,
                ...,
            ],
        ],
    ) -> float:
        if (
            game.phase
            == GamePhase.COMPLETE
        ):
            return terminal_utility(
                game,
                seat=(
                    self.responder_seat
                ),
            )

        acting_seat = (
            game.acting_seat
        )

        if acting_seat is None:
            raise RuntimeError(
                "Non-terminal game has "
                "no acting player."
            )

        actions = (
            self._solver_actions(
                game
            )
        )

        if not actions:
            raise RuntimeError(
                "Non-terminal game has "
                "no legal solver actions."
            )

        state = (
            InformationState.from_game(
                game,
                observer_seat=(
                    acting_seat
                ),
                abstraction=(
                    self.abstraction
                ),
            )
        )

        if (
            acting_seat
            != self.responder_seat
        ):
            strategy = (
                self._opponent_strategy(
                    state=state,
                    actions=actions,
                )
            )

            sampled_action = (
                self._sample_action(
                    actions=actions,
                    strategy=strategy,
                )
            )

            next_game = (
                self._apply_action(
                    game=game,
                    action=sampled_action,
                )
            )

            return (
                self._sampled_response_traversal(
                    game=next_game,
                    policy=policy,
                    action_sums=action_sums,
                    action_counts=(
                        action_counts
                    ),
                    legal_actions_by_state=(
                        legal_actions_by_state
                    ),
                )
            )

        existing_actions = (
            legal_actions_by_state.get(
                state
            )
        )

        if (
            existing_actions is not None
            and existing_actions
            != actions
        ):
            raise RuntimeError(
                "Same InformationState "
                "produced inconsistent "
                "legal actions."
            )

        legal_actions_by_state[
            state
        ] = actions

        state_sums = (
            action_sums.setdefault(
                state,
                {},
            )
        )

        state_counts = (
            action_counts.setdefault(
                state,
                {},
            )
        )

        action_values: dict[
            SolverAction,
            float,
        ] = {}

        for action in actions:
            next_game = (
                self._apply_action(
                    game=game,
                    action=action,
                )
            )

            action_value = (
                self._sampled_response_traversal(
                    game=next_game,
                    policy=policy,
                    action_sums=action_sums,
                    action_counts=(
                        action_counts
                    ),
                    legal_actions_by_state=(
                        legal_actions_by_state
                    ),
                )
            )

            action_values[
                action
            ] = action_value

            state_sums[
                action
            ] = (
                state_sums.get(
                    action,
                    0.0,
                )
                + action_value
            )

            state_counts[
                action
            ] = (
                state_counts.get(
                    action,
                    0,
                )
                + 1
            )

        chosen_action = (
            policy.get(
                state
            )
        )

        if (
            chosen_action
            not in actions
        ):
            strategy = (
                self.strategy_index
                .strategy_for_state(
                    state
                )
            )

            chosen_action = (
                self._highest_probability_action(
                    actions=actions,
                    strategy=strategy,
                )
            )

        return action_values[
            chosen_action
        ]

    def _sample_profile_rollout(
        self,
        game: SingleDrawGame,
    ) -> float:
        while (
            game.phase
            != GamePhase.COMPLETE
        ):
            acting_seat = (
                game.acting_seat
            )

            if acting_seat is None:
                raise RuntimeError(
                    "Non-terminal game has "
                    "no acting player."
                )

            actions = (
                self._solver_actions(
                    game
                )
            )

            state = (
                InformationState.from_game(
                    game,
                    observer_seat=(
                        acting_seat
                    ),
                    abstraction=(
                        self.abstraction
                    ),
                )
            )

            strategy = (
                self._normalized_strategy(
                    actions=actions,
                    strategy=(
                        self.strategy_index
                        .strategy_for_state(
                            state
                        )
                    ),
                )
            )

            action = (
                self._sample_action(
                    actions=actions,
                    strategy=strategy,
                )
            )

            game = (
                self._apply_action(
                    game=game,
                    action=action,
                )
            )

        return terminal_utility(
            game,
            seat=(
                self.responder_seat
            ),
        )

    def _sample_response_rollout(
        self,
        *,
        game: SingleDrawGame,
        policy: PureResponsePolicy,
    ) -> float:
        while (
            game.phase
            != GamePhase.COMPLETE
        ):
            acting_seat = (
                game.acting_seat
            )

            if acting_seat is None:
                raise RuntimeError(
                    "Non-terminal game has "
                    "no acting player."
                )

            actions = (
                self._solver_actions(
                    game
                )
            )

            state = (
                InformationState.from_game(
                    game,
                    observer_seat=(
                        acting_seat
                    ),
                    abstraction=(
                        self.abstraction
                    ),
                )
            )

            if (
                acting_seat
                == self.responder_seat
            ):
                action = (
                    policy.get(
                        state
                    )
                )

                if (
                    action
                    not in actions
                ):
                    strategy = (
                        self.strategy_index
                        .strategy_for_state(
                            state
                        )
                    )

                    action = (
                        self._highest_probability_action(
                            actions=actions,
                            strategy=strategy,
                        )
                    )

            else:
                strategy = (
                    self._opponent_strategy(
                        state=state,
                        actions=actions,
                    )
                )

                action = (
                    self._sample_action(
                        actions=actions,
                        strategy=strategy,
                    )
                )

            game = (
                self._apply_action(
                    game=game,
                    action=action,
                )
            )

        return terminal_utility(
            game,
            seat=(
                self.responder_seat
            ),
        )

    def _opponent_strategy(
        self,
        *,
        state: InformationState,
        actions: tuple[
            SolverAction,
            ...,
        ],
    ) -> Strategy:
        strategy = (
            self.strategy_index
            .strategy_for_state(
                state
            )
        )

        if strategy is None:
            self._opponent_misses += 1
        else:
            self._opponent_hits += 1

        return (
            self._normalized_strategy(
                actions=actions,
                strategy=strategy,
            )
        )

    @staticmethod
    def _normalized_strategy(
        *,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: Strategy | None,
    ) -> Strategy:
        if strategy is None:
            probability = (
                1.0
                / len(
                    actions
                )
            )

            return {
                action: probability
                for action in actions
            }

        probabilities = {
            action: max(
                0.0,
                float(
                    strategy.get(
                        action,
                        0.0,
                    )
                ),
            )
            for action in actions
        }

        total = sum(
            probabilities.values()
        )

        if total <= 0.0:
            probability = (
                1.0
                / len(
                    actions
                )
            )

            return {
                action: probability
                for action in actions
            }

        return {
            action: (
                probability
                / total
            )
            for (
                action,
                probability,
            ) in probabilities.items()
        }

    @staticmethod
    def _highest_probability_action(
        *,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: Strategy | None,
    ) -> SolverAction:
        normalized = (
            SampledBestResponse
            ._normalized_strategy(
                actions=actions,
                strategy=strategy,
            )
        )

        return max(
            actions,
            key=lambda action: (
                normalized[
                    action
                ]
            ),
        )

    def _sample_action(
        self,
        *,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: Strategy,
    ) -> SolverAction:
        threshold = (
            self._random.random()
        )

        cumulative = 0.0

        for action in actions:
            cumulative += (
                strategy[
                    action
                ]
            )

            if threshold <= cumulative:
                return action

        return actions[-1]

    def _solver_actions(
        self,
        game: SingleDrawGame,
    ) -> tuple[
        SolverAction,
        ...,
    ]:
        return (
            self._action_helper
            ._solver_actions(
                game
            )
        )

    def _apply_action(
        self,
        *,
        game: SingleDrawGame,
        action: SolverAction,
    ) -> SingleDrawGame:
        return (
            self._action_helper
            ._apply_action(
                game=game,
                action=action,
            )
        )