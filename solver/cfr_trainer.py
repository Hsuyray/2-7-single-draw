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
from solver.bucket_action_codec import (
    bucket_solver_actions_for_game,
    executable_bucket_action_for_game,
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

from solver.game_state import (
    GameConfig,
)
from solver.postdraw_strength_bucket import (
    POSTDRAW_BUCKET_COUNT,
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


# How external sampling accumulates the average strategy
# (docs/proposals/CFR-average-weighting.md):
#
# "reach":  at the traverser's own nodes, weight = own reach.
#           Its expected weight also carries the opponent's reach.
#           The original behaviour and the default.
#
# "simple": at the opponent's (sampled) nodes, add the current
#           strategy with weight 1 (Lanctot et al. 2009 simple
#           averaging). Expected weight = own reach x chance, the
#           weighting CFR's average-strategy guarantee assumes.
#           Regrets, sampling and node creation are unchanged.
AverageMode = Literal[
    "reach",
    "simple",
]

AVERAGE_MODES: tuple[str, ...] = (
    "reach",
    "simple",
)


# How much each iteration counts (docs/proposals/
# CFR-linear-weighting.md):
#
# "uniform": every iteration's regrets and average-strategy
#            contributions count the same. The original behaviour
#            and the default.
#
# "linear":  iteration t (1-based) contributes t times its regrets
#            and t times its average-strategy weight (Linear CFR,
#            Brown & Sandholm 2019).
IterationWeighting = Literal[
    "uniform",
    "linear",
]

ITERATION_WEIGHTINGS: tuple[str, ...] = (
    "uniform",
    "linear",
)


# Draw-action sampling at the traverser's draw nodes
# (docs/proposals/CFR-draw-action-sampling.md):
#
# 0 (default): external sampling explores every draw action of the
#     traverser (32 with max_draw=5). The original behaviour.
#
# k > 0: each draw action a is explored independently with
#     probability q(a) = min(1, max(DRAW_SAMPLE_FLOOR, k * sigma(a))),
#     sigma = the current (regret-matching) strategy, so about k
#     actions are explored. Values and regrets are importance
#     weighted by 1 / q(a), which keeps every regret and
#     average-strategy increment unbiased.
DRAW_SAMPLE_FLOOR = 0.05


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

    average_mode: AverageMode = "reach"

    iteration_weighting: IterationWeighting = "uniform"

    draw_action_sampling: int = 0

    game_config: (
        GameConfig
        | None
    ) = None

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

        if self.average_mode not in AVERAGE_MODES:
            raise ValueError(
                "Average mode must be "
                "'reach' or 'simple'."
            )

        if (
            self.average_mode == "simple"
            and self.traversal_mode
            != "external_sampling"
        ):
            raise ValueError(
                "Simple averaging needs "
                "external sampling: full "
                "traversal has no sampled "
                "opponent nodes."
            )

        if (
            self.iteration_weighting
            not in ITERATION_WEIGHTINGS
        ):
            raise ValueError(
                "Iteration weighting must be "
                "'uniform' or 'linear'."
            )

        if (
            self.iteration_weighting == "linear"
            and self.traversal_mode
            != "external_sampling"
        ):
            raise ValueError(
                "Linear iteration weighting is "
                "only implemented for external "
                "sampling."
            )

        if (
            not isinstance(
                self.draw_action_sampling,
                int,
            )
            or self.draw_action_sampling < 0
        ):
            raise ValueError(
                "Draw action sampling must be "
                "a non-negative integer."
            )

        if (
            self.draw_action_sampling > 0
            and (
                self.traversal_mode
                != "external_sampling"
                or self.average_mode
                != "simple"
            )
        ):
            raise ValueError(
                "Draw action sampling needs "
                "external sampling with simple "
                "averaging."
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
        sample_weight: float = 1.0,
    ) -> float:
        """
        sample_weight is 1 / (probability that draw-action sampling
        kept this path); it is exactly 1.0 when sampling is off.
        """
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
            if self.average_mode == "simple":
                node.accumulate_strategy(
                    realization_weight=(
                        self._iteration_weight()
                        * sample_weight
                    )
                )

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
                    sample_weight=(
                        sample_weight
                    ),
                )
            )

        if (
            self.draw_action_sampling > 0
            and game.phase == GamePhase.DRAW
        ):
            return self._sampled_draw_node(
                game=game,
                node=node,
                actions=actions,
                strategy=strategy,
                traversing_seat=(
                    traversing_seat
                ),
                traverser_reach=(
                    traverser_reach
                ),
                sample_weight=(
                    sample_weight
                ),
            )

        if self.average_mode == "reach":
            node.accumulate_strategy(
                realization_weight=(
                    self._iteration_weight()
                    * traverser_reach
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
                    sample_weight=(
                        sample_weight
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

        weight = (
            self._iteration_weight()
            * sample_weight
        )

        regrets = {
            action: weight * (
                action_utilities[action]
                - node_utility
            )
            for action in actions
        }

        node.add_regrets(
            regrets
        )

        return node_utility

    def _sampled_draw_node(
        self,
        *,
        game: SingleDrawGame,
        node,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: dict[
            SolverAction,
            float,
        ],
        traversing_seat: int,
        traverser_reach: float,
        sample_weight: float,
    ) -> float:
        """
        Traverser draw node with draw-action sampling: explore each
        action independently with probability q(a) (draw_inclusion_
        probabilities) and return the importance-weighted estimates
        of sampled_draw_estimates. The subtree below a kept action
        carries sample_weight / q(a).
        """
        inclusion = draw_inclusion_probabilities(
            actions=actions,
            strategy=strategy,
            target=self.draw_action_sampling,
        )

        sampled_utilities: dict[
            SolverAction,
            float,
        ] = {}

        for action in actions:
            probability = inclusion[action]

            if (
                probability < 1.0
                and self._random.random()
                >= probability
            ):
                continue

            next_game = (
                self._apply_node_action(
                    game=game,
                    action=action,
                )
            )

            sampled_utilities[action] = (
                self._external_sampling_cfr(
                    game=next_game,
                    traversing_seat=(
                        traversing_seat
                    ),
                    traverser_reach=(
                        traverser_reach
                        * strategy[action]
                    ),
                    sample_weight=(
                        sample_weight
                        / probability
                    ),
                )
            )

        node_utility, raw_regrets = (
            sampled_draw_estimates(
                actions=actions,
                strategy=strategy,
                inclusion=inclusion,
                sampled_utilities=(
                    sampled_utilities
                ),
            )
        )

        weight = (
            self._iteration_weight()
            * sample_weight
        )

        node.add_regrets(
            {
                action: weight * regret
                for action, regret
                in raw_regrets.items()
            }
        )

        return node_utility

    def _iteration_weight(self) -> float:
        """
        Weight of the iteration in progress: 1.0 under uniform
        weighting (multiplying by 1.0 is exact, so the original
        results are unchanged), t = completed_iterations + 1 under
        linear weighting.
        """
        if self.iteration_weighting == "linear":
            return float(
                self.completed_iterations + 1
            )

        return 1.0

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

        if self.abstraction == "exact":
            return (
                canonical_solver_actions_for_game(
                    game=game,
                    actions=actual_actions,
                )
            )

        if self.abstraction == "bucket":
            return (
                bucket_solver_actions_for_game(
                    game=game,
                    actions=actual_actions,
                )
            )

        raise ValueError(
            "Unknown CFR abstraction."
        )

    def _apply_node_action(
        self,
        *,
        game: SingleDrawGame,
        action: SolverAction,
    ) -> SingleDrawGame:
        executable_action = action

        if self.abstraction == "exact":
            executable_action = (
                executable_solver_action_for_game(
                    game=game,
                    action=action,
                )
            )

        elif self.abstraction == "bucket":
            executable_action = (
                executable_bucket_action_for_game(
                    game=game,
                    action=action,
                )
            )

        else:
            raise ValueError(
                "Unknown CFR abstraction."
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
        player_count = None
        starting_stack = None
        starting_stacks = None
        small_blind = None
        big_blind = None
        big_blind_ante = None

        if self.game_config is not None:
            player_count = (
                self.game_config
                .player_count
            )

            starting_stack = (
                self.game_config
                .starting_stack
            )

            starting_stacks = (
                self.game_config
                .starting_stacks
            )

            small_blind = (
                self.game_config
                .small_blind
            )

            big_blind = (
                self.game_config
                .big_blind
            )

            big_blind_ante = (
                self.game_config
                .big_blind_ante
            )

        postdraw_bucket_count = None

        if self.abstraction == "bucket":
            postdraw_bucket_count = (
                POSTDRAW_BUCKET_COUNT
            )

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
            bet_sizing_policy=(
                self.bet_sizing_policy
            ),
            traversal_mode=(
                self.traversal_mode
            ),
            player_count=player_count,
            starting_stack=(
                starting_stack
            ),
            starting_stacks=(
                starting_stacks
            ),
            small_blind=small_blind,
            big_blind=big_blind,
            big_blind_ante=(
                big_blind_ante
            ),
            postdraw_bucket_count=(
                postdraw_bucket_count
            ),
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

def draw_inclusion_probabilities(
    *,
    actions: tuple[SolverAction, ...],
    strategy: dict[SolverAction, float],
    target: int,
) -> dict[SolverAction, float]:
    """
    q(a) = min(1, max(DRAW_SAMPLE_FLOOR, target * sigma(a))).
    Every action keeps a positive probability, so the estimates of
    sampled_draw_estimates stay unbiased.
    """
    return {
        action: min(
            1.0,
            max(
                DRAW_SAMPLE_FLOOR,
                target * strategy[action],
            ),
        )
        for action in actions
    }


def sampled_draw_estimates(
    *,
    actions: tuple[SolverAction, ...],
    strategy: dict[SolverAction, float],
    inclusion: dict[SolverAction, float],
    sampled_utilities: dict[SolverAction, float],
) -> tuple[float, dict[SolverAction, float]]:
    """
    Importance-weighted estimates for one traverser draw node whose
    actions were kept independently with probability inclusion[a]:

        v_hat(a) = v(a) / q(a) if a was kept, else 0
        u_hat    = sum_a sigma(a) * v_hat(a)
        r_hat(a) = v_hat(a) - u_hat

    E[v_hat(a)] = v(a), so u_hat and r_hat are unbiased estimates of
    the node value and the instantaneous regrets.
    """
    action_values = {
        action: (
            sampled_utilities[action]
            / inclusion[action]
            if action in sampled_utilities
            else 0.0
        )
        for action in actions
    }

    node_utility = sum(
        strategy[action]
        * action_values[action]
        for action in actions
    )

    return node_utility, {
        action: (
            action_values[action]
            - node_utility
        )
        for action in actions
    }
