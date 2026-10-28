import math
import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.actions import (
    DiscardAction,
)
from solver.cfr_trainer import (
    CFRTrainer,
)
from solver.game_state import (
    ActionType,
)
from solver.information_state import (
    AbstractionMode,
    InformationState,
)
from solver.legal_actions import (
    BettingAction,
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

    # Per-deal sums of squared utilities, for
    # standard errors. Default 0.0 keeps older
    # constructors valid.
    seat_0_sum_squares: float = 0.0
    seat_1_sum_squares: float = 0.0

    max_zero_sum_error: float = 0.0

    @property
    def seat_0_standard_error(
        self,
    ) -> float:
        return standard_error(
            mean=self.seat_0_utility,
            sum_squares=(
                self.seat_0_sum_squares
            ),
            count=self.deals,
        )

    @property
    def seat_1_standard_error(
        self,
    ) -> float:
        return standard_error(
            mean=self.seat_1_utility,
            sum_squares=(
                self.seat_1_sum_squares
            ),
            count=self.deals,
        )

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


def standard_error(
    *,
    mean: float,
    sum_squares: float,
    count: int,
) -> float:
    """
    Standard error of a sample mean from its
    mean and sum of squares (sample variance,
    n - 1 denominator).
    """
    if count <= 1:
        return 0.0

    variance = (
        (
            sum_squares
            - count
            * mean
            * mean
        )
        / (
            count
            - 1
        )
    )

    return math.sqrt(
        max(
            0.0,
            variance,
        )
        / count
    )


class EvaluationObserver(Protocol):
    """
    Optional read-only hooks for
    StrategyProfileEvaluator.evaluate.

    Observers never touch the evaluator's RNG,
    so attaching one does not change results.
    """

    def on_deal_start(
        self,
        deal_index: int,
    ) -> None: ...

    def on_decision(
        self,
        *,
        game: SingleDrawGame,
        information_state: InformationState,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: Strategy | None,
    ) -> None: ...

    def on_deal_end(
        self,
        *,
        seat_0_utility: float,
        seat_1_utility: float,
    ) -> None: ...


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
        observer: (
            EvaluationObserver
            | None
        ) = None,
    ) -> StrategyProfileEvaluation:
        if deals <= 0:
            raise ValueError(
                "Deals must be positive."
            )

        seat_0_total = 0.0
        seat_1_total = 0.0

        seat_0_sum_squares = 0.0
        seat_1_sum_squares = 0.0

        max_zero_sum_error = 0.0

        strategy_decisions = 0
        missing_strategy_decisions = 0

        for deal_index in range(
            deals
        ):
            game = deepcopy(
                game_factory()
            )

            if observer is not None:
                observer.on_deal_start(
                    deal_index
                )

            (
                seat_0_utility,
                seat_1_utility,
                used,
                missing,
            ) = self._play_one_game(
                game,
                observer=observer,
            )

            if observer is not None:
                observer.on_deal_end(
                    seat_0_utility=(
                        seat_0_utility
                    ),
                    seat_1_utility=(
                        seat_1_utility
                    ),
                )

            seat_0_total += (
                seat_0_utility
            )

            seat_1_total += (
                seat_1_utility
            )

            seat_0_sum_squares += (
                seat_0_utility
                * seat_0_utility
            )

            seat_1_sum_squares += (
                seat_1_utility
                * seat_1_utility
            )

            max_zero_sum_error = max(
                max_zero_sum_error,
                abs(
                    seat_0_utility
                    + seat_1_utility
                ),
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
            seat_0_sum_squares=(
                seat_0_sum_squares
            ),
            seat_1_sum_squares=(
                seat_1_sum_squares
            ),
            max_zero_sum_error=(
                max_zero_sum_error
            ),
        )

    def _play_one_game(
        self,
        game: SingleDrawGame,
        observer: (
            EvaluationObserver
            | None
        ) = None,
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

            if observer is not None:
                observer.on_decision(
                    game=game,
                    information_state=(
                        information_state
                    ),
                    actions=actions,
                    strategy=strategy,
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

class DecisionPolicy(Protocol):
    """
    One player's policy for HeadToHeadEvaluator.

    Returning None means "no strategy for this
    information state"; the evaluator then plays
    uniformly and counts a missing decision.
    """

    def strategy(
        self,
        *,
        information_state: InformationState,
        actions: tuple[
            SolverAction,
            ...,
        ],
    ) -> Strategy | None: ...


@dataclass(frozen=True)
class StrategyIndexPolicy:
    strategy_index: StrategyIndex

    def strategy(
        self,
        *,
        information_state: InformationState,
        actions: tuple[
            SolverAction,
            ...,
        ],
    ) -> Strategy | None:
        return (
            self.strategy_index
            .strategy_for_hand(
                public_node=(
                    information_state
                    .public_node
                ),
                observer_seat=(
                    information_state
                    .observer_seat
                ),
                hand_key=(
                    information_state
                    .own_hand_key
                ),
            )
        )


@dataclass(frozen=True)
class UniformPolicy:
    def strategy(
        self,
        *,
        information_state: InformationState,
        actions: tuple[
            SolverAction,
            ...,
        ],
    ) -> Strategy | None:
        return (
            StrategyProfileEvaluator
            ._uniform_strategy(
                actions
            )
        )


@dataclass(frozen=True)
class CallStationPolicy:
    """
    Check when possible, otherwise call; never
    raise or fold while a call is legal. Stands
    pat on the draw.
    """

    def strategy(
        self,
        *,
        information_state: InformationState,
        actions: tuple[
            SolverAction,
            ...,
        ],
    ) -> Strategy | None:
        preferences = (
            BettingAction(
                ActionType.CHECK
            ),
            BettingAction(
                ActionType.CALL
            ),
            DiscardAction(()),
        )

        for preferred in preferences:
            if preferred in actions:
                return {
                    preferred: 1.0,
                }

        return {
            actions[0]: 1.0,
        }


@dataclass(frozen=True)
class HeadToHeadEvaluation:
    deal_pairs: int

    # Mean utility of the first policy per deal
    # pair: the average of its two results on
    # the same deck, once in each seat.
    first_utility: float
    first_sum_squares: float

    first_decisions: int
    first_missing_decisions: int
    second_decisions: int
    second_missing_decisions: int

    max_zero_sum_error: float

    @property
    def first_standard_error(
        self,
    ) -> float:
        return standard_error(
            mean=self.first_utility,
            sum_squares=(
                self.first_sum_squares
            ),
            count=self.deal_pairs,
        )

    @property
    def first_coverage(self) -> float:
        return _coverage(
            self.first_decisions,
            self.first_missing_decisions,
        )

    @property
    def second_coverage(self) -> float:
        return _coverage(
            self.second_decisions,
            self.second_missing_decisions,
        )


def _coverage(
    decisions: int,
    missing: int,
) -> float:
    if decisions == 0:
        return 1.0

    return (
        decisions
        - missing
    ) / decisions


class HeadToHeadEvaluator:
    """
    Duplicate-format match between two policies
    in one game abstraction.

    Every deal is played twice from the same
    deck, with the seats swapped, which removes
    most of the card luck from the difference.

    Both policies must belong to the action
    abstraction given here; this class does not
    translate between abstractions.
    """

    def __init__(
        self,
        *,
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
        self.abstraction = abstraction

        # Reuse the profile evaluator's action
        # generation, execution and sampling (and
        # its RNG) instead of duplicating them.
        self._helper = StrategyProfileEvaluator(
            strategy_index=StrategyIndex(),
            abstraction=abstraction,
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

    def evaluate(
        self,
        game_factory,
        *,
        first: DecisionPolicy,
        second: DecisionPolicy,
        deal_pairs: int,
    ) -> HeadToHeadEvaluation:
        if deal_pairs <= 0:
            raise ValueError(
                "Deal pairs must be positive."
            )

        total = 0.0
        sum_squares = 0.0
        max_zero_sum_error = 0.0

        # [decisions, missing] per policy.
        counts = {
            "first": [0, 0],
            "second": [0, 0],
        }

        for _ in range(
            deal_pairs
        ):
            game = game_factory()

            pair_value = 0.0

            for first_seat in (
                0,
                1,
            ):
                seat_policies = {
                    first_seat: (
                        "first",
                        first,
                    ),
                    1 - first_seat: (
                        "second",
                        second,
                    ),
                }

                utilities = self._play_one_game(
                    deepcopy(
                        game
                    ),
                    seat_policies=(
                        seat_policies
                    ),
                    counts=counts,
                )

                pair_value += utilities[
                    first_seat
                ]

                max_zero_sum_error = max(
                    max_zero_sum_error,
                    abs(
                        utilities[0]
                        + utilities[1]
                    ),
                )

            pair_value /= 2.0

            total += pair_value
            sum_squares += (
                pair_value
                * pair_value
            )

        return HeadToHeadEvaluation(
            deal_pairs=deal_pairs,
            first_utility=(
                total
                / deal_pairs
            ),
            first_sum_squares=(
                sum_squares
            ),
            first_decisions=(
                counts["first"][0]
            ),
            first_missing_decisions=(
                counts["first"][1]
            ),
            second_decisions=(
                counts["second"][0]
            ),
            second_missing_decisions=(
                counts["second"][1]
            ),
            max_zero_sum_error=(
                max_zero_sum_error
            ),
        )

    def _play_one_game(
        self,
        game: SingleDrawGame,
        *,
        seat_policies: dict[
            int,
            tuple[
                str,
                DecisionPolicy,
            ],
        ],
        counts: dict[
            str,
            list[int],
        ],
    ) -> tuple[
        float,
        float,
    ]:
        helper = self._helper

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

            actions = helper._solver_actions(
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

            (
                name,
                policy,
            ) = seat_policies[
                acting_seat
            ]

            strategy = policy.strategy(
                information_state=(
                    information_state
                ),
                actions=actions,
            )

            counts[name][0] += 1

            if strategy is None:
                counts[name][1] += 1

                normalized_strategy = (
                    helper._uniform_strategy(
                        actions
                    )
                )

            else:
                normalized_strategy = (
                    helper._normalized_strategy(
                        actions=actions,
                        strategy=strategy,
                    )
                )

            action = helper._sample_action(
                actions=actions,
                strategy=(
                    normalized_strategy
                ),
            )

            game = helper._apply_action(
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
        )
