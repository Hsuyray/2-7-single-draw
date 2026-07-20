from dataclasses import dataclass, field

from solver.cfr_node import CFRNode
from solver.information_state import InformationState
from solver.legal_actions import SolverAction


@dataclass
class NodeStore:
    nodes: dict[InformationState, CFRNode] = field(
        default_factory=dict,
    )

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(
        self,
        information_state: InformationState,
    ) -> bool:
        return information_state in self.nodes

    def get(
        self,
        information_state: InformationState,
    ) -> CFRNode | None:
        return self.nodes.get(information_state)

    def get_or_create(
        self,
        information_state: InformationState,
        actions: tuple[SolverAction, ...],
    ) -> CFRNode:
        if not actions:
            raise ValueError(
                "Cannot create a CFR node without actions."
            )

        existing_node = self.nodes.get(
            information_state
        )

        if existing_node is not None:
            if existing_node.actions != actions:
                raise ValueError(
                    "Information state already exists "
                    "with a different action set."
                )

            return existing_node

        node = CFRNode(
            actions=actions,
        )

        self.nodes[information_state] = node

        return node

    def remove(
        self,
        information_state: InformationState,
    ) -> None:
        if information_state not in self.nodes:
            raise KeyError(
                "Information state does not exist."
            )

        del self.nodes[information_state]

    def clear(self) -> None:
        self.nodes.clear()

    def average_strategies(
        self,
    ) -> dict[
        InformationState,
        dict[SolverAction, float],
    ]:
        return {
            information_state: node.average_strategy()
            for information_state, node
            in self.nodes.items()
        }