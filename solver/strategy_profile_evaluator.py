import random
from copy import deepcopy
from dataclasses import dataclass

from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.cfr_trainer import (
    CFRTrainer,
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
from solver.terminal_utility import (
    terminal_utility,
)


@dataclass(frozen=True)
class StrategyProfileEvaluation:
    deals: int

    seat_0_utility: float
    seat_1_utility: float

    strategy_decisions: int
    missing_strategy_decisions: int

    @property
    def total_decisions(self) -> int:
        return (
            self.strategy_decisions
            + self.missing_strategy_decisions
        )

    @property
    def strategy_coverage(self) -> float:
        if self.total_decisions == 0:
            return 1.0

        return (
            self.strategy_decisions
            / self.total_decisions
        )

    @property
    def zero_sum_error(self) -> float:
        return abs(
            self.seat_0_utility
            + self.seat_1_utility
        )


class StrategyProfileEvaluator:
    """
    Monte Carlo evaluation of one solved
    heads-up strategy profile.

    Both players follow the supplied
    StrategyIndex.

    Missing information states fall back to
    uniform play and are counted explicitly.

    This evaluator is NOT an exploitability
    estimator.
    """

    def __init__(
        self,
        *,
        strategy_index: StrategyIndex,
        abstraction: AbstractionMode,
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

        self.abstraction = abstraction
        self.max_draw = max_draw
        self.raise_sizes = raise_sizes

        self.bet_sizing_policy = (
            bet_sizing_policy
        )

        self.draw_action_mode = (
            draw_action_mode
        )

        self._random = random.Random(
            random_seed
        )

        # Reuse the exact same solver-action
        # generation and execution path used
        # by CFR training.
        #
        # This deliberately avoids duplicating
        # exact/bucket codec logic inside the
        # evaluator.
        self._action_helper = CFRTrainer(
            max_draw=max_draw,
            raise_sizes=raise_sizes,
            bet_sizing_policy=(
                bet_sizing_policy
            ),
            abstraction=abstraction,
            traversal_mode=(
                "external_sampling"
            ),
            draw_action_mode=(
                draw_action_mode
            ),
            random_seed=random_seed,
        )

    def evaluate(
        self,
        game_factory,
        *,
        deals: int,
    ) -> StrategyProfileEvaluation:
        if deals <= 0:
            raise ValueError(
                "Deals must be positive."
            )

        seat_0_total = 0.0
        seat_1_total = 0.0

        strategy_decisions = 0
        missing_strategy_decisions = 0

        for _ in range(
            deals
        ):
            game = deepcopy(
                game_factory()
            )

            (
                seat_0_utility,
                seat_1_utility,
                used,
                missing,
            ) = self._play_one_game(
                game
            )

            seat_0_total += (
                seat_0_utility
            )

            seat_1_total += (
                seat_1_utility
            )

            strategy_decisions += used

            missing_strategy_decisions += (
                missing
            )

        return StrategyProfileEvaluation(
            deals=deals,
            seat_0_utility=(
                seat_0_total
                / deals
            ),
            seat_1_utility=(
                seat_1_total
                / deals
            ),
            strategy_decisions=(
                strategy_decisions
            ),
            missing_strategy_decisions=(
                missing_strategy_decisions
            ),
        )

    def _play_one_game(
        self,
        game: SingleDrawGame,
    ) -> tuple[
        float,
        float,
        int,
        int,
    ]:
        strategy_decisions = 0
        missing_strategy_decisions = 0

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

            actions = self._solver_actions(
                game
            )

            if not actions:
                raise RuntimeError(
                    "Non-terminal game has "
                    "no legal solver actions."
                )

            information_state = (
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
                self.strategy_index
                .strategy_for_hand(
                    public_node=(
                        information_state
                        .public_node
                    ),
                    observer_seat=(
                        acting_seat
                    ),
                    hand_key=(
                        information_state
                        .own_hand_key
                    ),
                )
            )

            if strategy is None:
                missing_strategy_decisions += 1

                normalized_strategy = (
                    self._uniform_strategy(
                        actions
                    )
                )

            else:
                strategy_decisions += 1

                normalized_strategy = (
                    self._normalized_strategy(
                        actions=actions,
                        strategy=strategy,
                    )
                )

            action = self._sample_action(
                actions=actions,
                strategy=(
                    normalized_strategy
                ),
            )

            game = self._apply_action(
                game=game,
                action=action,
            )

        return (
            terminal_utility(
                game,
                seat=0,
            ),
            terminal_utility(
                game,
                seat=1,
            ),
            strategy_decisions,
            missing_strategy_decisions,
        )

    def _solver_actions(
        self,
        game: SingleDrawGame,
    ) -> tuple[
        SolverAction,
        ...,
    ]:
        """
        Use CFRTrainer's action-space logic.

        This guarantees evaluation uses the
        same canonical/bucket representation
        that produced the StrategyIndex.
        """
        return (
            self._action_helper
            ._legal_actions(
                game
            )
        )

    def _apply_action(
        self,
        *,
        game: SingleDrawGame,
        action: SolverAction,
    ) -> SingleDrawGame:
        """
        Use CFRTrainer's solver-action
        execution path.

        In particular, this preserves any
        exact-hand or bucket-hand mapping
        required for draw actions.
        """
        return (
            self._action_helper
            ._apply_node_action(
                game=game,
                action=action,
            )
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

        cumulative_probability = 0.0

        for action in actions:
            cumulative_probability += (
                strategy[
                    action
                ]
            )

            if (
                threshold
                <= cumulative_probability
            ):
                return action

        return actions[-1]

    @staticmethod
    def _uniform_strategy(
        actions: tuple[
            SolverAction,
            ...,
        ],
    ) -> Strategy:
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

    @staticmethod
    def _normalized_strategy(
        *,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: Strategy,
    ) -> Strategy:
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

        total_probability = sum(
            probabilities.values()
        )

        if (
            total_probability
            <= 0.0
        ):
            return (
                StrategyProfileEvaluator
                ._uniform_strategy(
                    actions
                )
            )

        return {
            action: (
                probability
                / total_probability
            )
            for (
                action,
                probability,
            ) in probabilities.items()
        }