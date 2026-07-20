from dataclasses import dataclass, field

from solver.legal_actions import SolverAction


@dataclass
class CFRNode:
    actions: tuple[SolverAction, ...]
    regret_sum: dict[SolverAction, float] = field(
        init=False,
    )
    strategy_sum: dict[SolverAction, float] = field(
        init=False,
    )

    def __post_init__(self) -> None:
        if not self.actions:
            raise ValueError(
                "A CFR node must contain at least one action."
            )

        if len(set(self.actions)) != len(self.actions):
            raise ValueError(
                "CFR node actions must be unique."
            )

        self.regret_sum = {
            action: 0.0
            for action in self.actions
        }

        self.strategy_sum = {
            action: 0.0
            for action in self.actions
        }

    def current_strategy(
        self,
    ) -> dict[SolverAction, float]:
        positive_regrets = {
            action: max(
                self.regret_sum[action],
                0.0,
            )
            for action in self.actions
        }

        normalizing_sum = sum(
            positive_regrets.values()
        )

        if normalizing_sum > 0:
            return {
                action: (
                    positive_regrets[action]
                    / normalizing_sum
                )
                for action in self.actions
            }

        uniform_probability = (
            1.0 / len(self.actions)
        )

        return {
            action: uniform_probability
            for action in self.actions
        }

    def accumulate_strategy(
        self,
        realization_weight: float,
    ) -> dict[SolverAction, float]:
        if realization_weight < 0:
            raise ValueError(
                "Realization weight cannot be negative."
            )

        strategy = self.current_strategy()

        for action in self.actions:
            self.strategy_sum[action] += (
                realization_weight
                * strategy[action]
            )

        return strategy

    def add_regret(
        self,
        action: SolverAction,
        regret: float,
    ) -> None:
        self._validate_action(action)

        self.regret_sum[action] += regret

    def add_regrets(
        self,
        regrets: dict[SolverAction, float],
    ) -> None:
        unknown_actions = (
            set(regrets) - set(self.actions)
        )

        if unknown_actions:
            raise ValueError(
                "Regret update contains an unknown action."
            )

        for action, regret in regrets.items():
            self.regret_sum[action] += regret

    def average_strategy(
        self,
    ) -> dict[SolverAction, float]:
        normalizing_sum = sum(
            self.strategy_sum.values()
        )

        if normalizing_sum > 0:
            return {
                action: (
                    self.strategy_sum[action]
                    / normalizing_sum
                )
                for action in self.actions
            }

        uniform_probability = (
            1.0 / len(self.actions)
        )

        return {
            action: uniform_probability
            for action in self.actions
        }

    def _validate_action(
        self,
        action: SolverAction,
    ) -> None:
        if action not in self.regret_sum:
            raise ValueError(
                "Action does not belong to this CFR node."
            )