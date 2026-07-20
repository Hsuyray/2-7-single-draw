from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from math import prod

from solver.action_executor import apply_solver_action
from solver.information_state import InformationState
from solver.legal_actions import legal_actions
from solver.node_store import NodeStore
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)
from solver.terminal_utility import terminal_utility


GameFactory = Callable[[], SingleDrawGame]


@dataclass
class CFRTrainer:
    max_draw: int = 3
    raise_sizes: tuple[float, ...] = ()
    node_store: NodeStore = field(
        default_factory=NodeStore,
    )
    completed_iterations: int = 0

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
                game_copy = deepcopy(sampled_game)

                self._cfr(
                    game=game_copy,
                    traversing_seat=traversing_seat,
                    reach_probabilities=(1.0, 1.0),
                )

            self.completed_iterations += 1

    def _cfr(
        self,
        *,
        game: SingleDrawGame,
        traversing_seat: int,
        reach_probabilities: tuple[float, float],
    ) -> float:
        if game.phase == GamePhase.COMPLETE:
            return terminal_utility(
                game,
                seat=traversing_seat,
            )

        acting_seat = game.acting_seat

        if acting_seat is None:
            raise RuntimeError(
                "Non-terminal game has no acting player."
            )

        actions = legal_actions(
            game,
            max_draw=self.max_draw,
            raise_sizes=self.raise_sizes,
        )

        if not actions:
            raise RuntimeError(
                "Non-terminal game has no legal actions."
            )

        information_state = InformationState.from_game(
            game,
            observer_seat=acting_seat,
        )

        node = self.node_store.get_or_create(
            information_state,
            actions,
        )

        strategy = node.current_strategy()

        if acting_seat == traversing_seat:
            node.accumulate_strategy(
                realization_weight=(
                    reach_probabilities[acting_seat]
                )
            )

        action_utilities: dict[
            object,
            float,
        ] = {}

        node_utility = 0.0

        for action in actions:
            next_game = apply_solver_action(
                game,
                action,
            )

            next_reach = list(reach_probabilities)
            next_reach[acting_seat] *= strategy[action]

            action_utility = self._cfr(
                game=next_game,
                traversing_seat=traversing_seat,
                reach_probabilities=(
                    next_reach[0],
                    next_reach[1],
                ),
            )

            action_utilities[action] = action_utility

            node_utility += (
                strategy[action]
                * action_utility
            )

        if acting_seat == traversing_seat:
            counterfactual_reach = prod(
                probability
                for seat, probability
                in enumerate(reach_probabilities)
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

    def average_strategies(
        self,
    ) -> dict:
        return self.node_store.average_strategies()

    def _validate_game(
        self,
        game: SingleDrawGame,
    ) -> None:
        if game.config.player_count != 2:
            raise ValueError(
                "This CFR prototype currently supports "
                "heads-up games only."
            )

        if game.phase != GamePhase.PREDRAW_BETTING:
            raise ValueError(
                "Training games must begin during "
                "pre-draw betting."
            )