from dataclasses import dataclass, field, replace

from solver.cfr_node import CFRNode
from solver.information_state import InformationState
from solver.legal_actions import SolverAction


@dataclass
class NodeStore:
    """
    Maps information states to CFR nodes.

    With intern=True (the default), when a new node is created the
    information state and action tuple that get stored are rebuilt
    from shared, equal-valued sub-objects. Equal values then occupy
    memory once instead of once per node. Every key component is an
    immutable value object and dict lookup uses ==/hash, so lookups,
    iteration order, regrets and strategies are unchanged. Set
    intern=False to store the objects exactly as given.
    """

    nodes: dict[InformationState, CFRNode] = field(
        default_factory=dict,
    )

    intern: bool = field(
        default=True,
        compare=False,
    )

    _pools: dict[str, dict] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
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

        if self.intern:
            information_state = self._intern_state(
                information_state
            )

            actions = self._intern_actions(
                actions
            )

        node = CFRNode(
            actions=actions,
        )

        self.nodes[information_state] = node

        return node

    def _canonical(
        self,
        kind: str,
        value,
    ):
        pool = self._pools.setdefault(
            kind,
            {},
        )

        return pool.setdefault(
            value,
            value,
        )

    def _intern_state(
        self,
        information_state: InformationState,
    ) -> InformationState:
        public_node = information_state.public_node

        pool = self._pools.setdefault(
            "public_node",
            {},
        )

        canonical_public = pool.get(
            public_node
        )

        if canonical_public is None:
            canonical_public = replace(
                public_node,
                players=tuple(
                    self._canonical(
                        "player",
                        player,
                    )
                    for player
                    in public_node.players
                ),
                action_history=tuple(
                    self._canonical(
                        "public_action",
                        action,
                    )
                    for action
                    in public_node.action_history
                ),
            )

            pool[canonical_public] = canonical_public

        own_hand_key = self._canonical(
            "hand_key",
            information_state.own_hand_key,
        )

        if (
            canonical_public is public_node
            and own_hand_key
            is information_state.own_hand_key
        ):
            return information_state

        return replace(
            information_state,
            public_node=canonical_public,
            own_hand_key=own_hand_key,
        )

    def _intern_actions(
        self,
        actions: tuple[SolverAction, ...],
    ) -> tuple[SolverAction, ...]:
        return self._canonical(
            "actions",
            tuple(
                self._canonical(
                    "action",
                    action,
                )
                for action in actions
            ),
        )

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
        self._pools.clear()

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