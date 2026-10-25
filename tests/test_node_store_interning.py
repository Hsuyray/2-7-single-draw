"""
NodeStore interning: equal-valued key components and action tuples
are stored once, and nothing observable changes.
"""

from copy import deepcopy

import pytest

from scripts.fingerprint_node_store import fingerprint_trainer
from solver.action_executor import apply_solver_action
from solver.bet_sizing import FAST_BET_SIZING
from solver.cfr_trainer import CFRTrainer
from solver.game_state import ActionType, GameConfig
from solver.information_state import InformationState
from solver.legal_actions import BettingAction, legal_actions
from solver.node_store import NodeStore
from solver.single_draw_game import SingleDrawGame


CONFIG = GameConfig(
    player_count=2,
    starting_stack=20.0,
    small_blind=1.0,
    big_blind=2.0,
    big_blind_ante=1.5,
)


def make_game(seed: int) -> SingleDrawGame:
    return SingleDrawGame(
        config=CONFIG,
        button_seat=0,
        deck_seed=seed,
    )


def after_call_and_raise(seed: int) -> SingleDrawGame:
    """Predraw: button calls, big blind raises. Fresh objects each call."""
    game = make_game(seed)

    game = apply_solver_action(
        game,
        BettingAction(ActionType.CALL),
    )

    return apply_solver_action(
        game,
        BettingAction(ActionType.RAISE, raise_to=6.0),
    )


def state_and_actions(game: SingleDrawGame):
    seat = game.acting_seat

    state = InformationState.from_game(
        game,
        observer_seat=seat,
        abstraction="bucket",
    )

    actions = legal_actions(
        game,
        max_draw=5,
        raise_sizes=None,
        bet_sizing_policy=FAST_BET_SIZING,
        draw_action_mode="full",
    )

    return state, actions


def test_equal_public_nodes_share_subobjects() -> None:
    state_a, actions_a = state_and_actions(after_call_and_raise(1))
    state_b, actions_b = state_and_actions(after_call_and_raise(2))

    # Same public path, different cards: equal public nodes that are
    # separate objects before interning.
    assert state_a.public_node == state_b.public_node
    assert state_a.public_node is not state_b.public_node
    assert (
        state_a.public_node.action_history[0]
        is not state_b.public_node.action_history[0]
    )
    assert state_a.own_hand_key != state_b.own_hand_key
    assert actions_a == actions_b
    assert actions_a[0] is not actions_b[0]

    store = NodeStore()

    node_a = store.get_or_create(state_a, actions_a)
    node_b = store.get_or_create(state_b, actions_b)

    stored = list(store.nodes)

    assert len(stored) == 2

    key_a, key_b = stored

    assert key_a.public_node is key_b.public_node

    for left, right in zip(
        key_a.public_node.action_history,
        key_b.public_node.action_history,
    ):
        assert left is right

    for left, right in zip(
        key_a.public_node.players,
        key_b.public_node.players,
    ):
        assert left is right

    assert node_a.actions is node_b.actions

    for left, right in zip(node_a.actions, node_b.actions):
        assert left is right


def test_lookups_work_with_the_original_state_objects() -> None:
    state, actions = state_and_actions(after_call_and_raise(1))
    twin, _ = state_and_actions(after_call_and_raise(1))

    store = NodeStore()

    node = store.get_or_create(state, actions)

    assert state in store
    assert twin in store
    assert store.get(state) is node
    assert store.get(twin) is node
    assert store.get_or_create(twin, actions) is node
    assert len(store) == 1


def test_stored_state_equals_original() -> None:
    state, actions = state_and_actions(after_call_and_raise(1))

    store = NodeStore()

    store.get_or_create(state, actions)

    (stored,) = store.nodes

    assert stored == state
    assert hash(stored) == hash(state)
    assert repr(stored) == repr(state)


def test_intern_disabled_stores_objects_as_given() -> None:
    state, actions = state_and_actions(after_call_and_raise(1))

    store = NodeStore(intern=False)

    node = store.get_or_create(state, actions)

    (stored,) = store.nodes

    assert stored is state
    assert node.actions is actions


def test_different_action_set_is_still_rejected() -> None:
    state, actions = state_and_actions(after_call_and_raise(1))

    store = NodeStore()

    store.get_or_create(state, actions)

    with pytest.raises(ValueError):
        store.get_or_create(state, actions[:-1])


def test_clear_empties_the_intern_pools() -> None:
    state, actions = state_and_actions(after_call_and_raise(1))

    store = NodeStore()

    store.get_or_create(state, actions)
    store.clear()

    assert len(store) == 0
    assert store._pools == {}


def test_input_objects_are_not_mutated() -> None:
    state, actions = state_and_actions(after_call_and_raise(1))

    state_before = deepcopy(state)
    actions_before = deepcopy(actions)

    NodeStore().get_or_create(state, actions)

    assert state == state_before
    assert actions == actions_before


def make_trainer(
    *,
    intern: bool,
    max_draw: int,
    abstraction: str,
) -> CFRTrainer:
    return CFRTrainer(
        max_draw=max_draw,
        raise_sizes=None,
        bet_sizing_policy=FAST_BET_SIZING,
        abstraction=abstraction,
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=42,
        game_config=CONFIG,
        node_store=NodeStore(intern=intern),
    )


def train(trainer: CFRTrainer, iterations: int) -> None:
    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter

        game = make_game(42 + counter)

        counter += 1

        return game

    trainer.train(factory, iterations=iterations)


@pytest.mark.parametrize(
    ("max_draw", "abstraction", "iterations"),
    [
        (2, "bucket", 8),
        (1, "exact", 5),
    ],
)
def test_training_is_identical_with_and_without_interning(
    max_draw: int,
    abstraction: str,
    iterations: int,
) -> None:
    plain = make_trainer(
        intern=False,
        max_draw=max_draw,
        abstraction=abstraction,
    )
    shared = make_trainer(
        intern=True,
        max_draw=max_draw,
        abstraction=abstraction,
    )

    train(plain, iterations)
    train(shared, iterations)

    assert len(plain.node_store) == len(shared.node_store) > 0

    # Same keys in the same insertion order.
    assert list(plain.node_store.nodes) == list(shared.node_store.nodes)

    assert fingerprint_trainer(plain) == fingerprint_trainer(shared)

    for state, node in plain.node_store.nodes.items():
        other = shared.node_store.nodes[state]

        assert node.actions == other.actions
        assert node.regret_sum == other.regret_sum
        assert node.strategy_sum == other.strategy_sum
        assert node.visit_count == other.visit_count

    assert plain.average_strategies() == shared.average_strategies()


def test_interning_collapses_duplicate_objects_during_training() -> None:
    plain = make_trainer(intern=False, max_draw=2, abstraction="bucket")
    shared = make_trainer(intern=True, max_draw=2, abstraction="bucket")

    train(plain, 8)
    train(shared, 8)

    def distinct(trainer: CFRTrainer) -> tuple[int, int]:
        history = set()
        history_values = set()
        actions = set()
        action_values = set()

        for state, node in trainer.node_store.nodes.items():
            for entry in state.public_node.action_history:
                history.add(id(entry))
                history_values.add(entry)

            for action in node.actions:
                actions.add(id(action))
                action_values.add(action)

        return (
            len(history) - len(history_values),
            len(actions) - len(action_values),
        )

    plain_extra_history, plain_extra_actions = distinct(plain)
    shared_extra_history, shared_extra_actions = distinct(shared)

    # Without interning most objects are duplicates of an equal one.
    assert plain_extra_history > 0
    assert plain_extra_actions > 0

    # With interning every value is stored exactly once.
    assert shared_extra_history == 0
    assert shared_extra_actions == 0
