from types import SimpleNamespace

import pytest

from solver.actions import DiscardAction
from solver.game_state import ActionType
from solver.information_state import InformationState
from solver.legal_actions import BettingAction
from solver.node_store import NodeStore
from solver.hand import Hand


def make_information_state(
    *,
    acting_seat: int = 0,
    phase: str = "predraw_betting",
) -> InformationState:
    player_zero = SimpleNamespace(
        seat=0,
        stack=99.0,
        committed_total=1.0,
        has_folded=False,
        is_all_in=False,
    )

    player_one = SimpleNamespace(
        seat=1,
        stack=98.0,
        committed_total=2.0,
        has_folded=False,
        is_all_in=False,
    )

    hand_zero = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "Ks",
    )

    hand_one = Hand.from_strings(
        "8s",
        "6h",
        "4c",
        "2d",
        "Qh",
    )

    game = SimpleNamespace(
        config=SimpleNamespace(
            player_count=2,
        ),
        hands=[
            hand_zero,
            hand_one,
        ],
        betting_state=SimpleNamespace(
            players=[
                player_zero,
                player_one,
            ],
        ),
        draw_results={},
        action_history=[],
        phase=SimpleNamespace(
            value=phase,
        ),
        acting_seat=acting_seat,
        button_seat=0,
        pot=3.0,
    )

    return InformationState.from_game(
        game,
        observer_seat=0,
    )


def make_betting_actions() -> tuple[
    BettingAction,
    ...,
]:
    return (
        BettingAction(ActionType.FOLD),
        BettingAction(ActionType.CALL),
    )


def test_new_store_is_empty() -> None:
    store = NodeStore()

    assert len(store) == 0


def test_get_or_create_adds_node() -> None:
    store = NodeStore()
    state = make_information_state()
    actions = make_betting_actions()

    node = store.get_or_create(
        state,
        actions,
    )

    assert len(store) == 1
    assert state in store
    assert store.get(state) is node


def test_get_or_create_returns_same_node() -> None:
    store = NodeStore()
    state = make_information_state()
    actions = make_betting_actions()

    first_node = store.get_or_create(
        state,
        actions,
    )

    second_node = store.get_or_create(
        state,
        actions,
    )

    assert first_node is second_node
    assert len(store) == 1


def test_existing_node_preserves_regrets() -> None:
    store = NodeStore()
    state = make_information_state()
    actions = make_betting_actions()

    node = store.get_or_create(
        state,
        actions,
    )

    node.add_regret(
        actions[1],
        5.0,
    )

    same_node = store.get_or_create(
        state,
        actions,
    )

    assert same_node.regret_sum[
        actions[1]
    ] == 5.0


def test_same_state_with_different_actions_is_rejected() -> None:
    store = NodeStore()
    state = make_information_state()

    store.get_or_create(
        state,
        make_betting_actions(),
    )

    different_actions = (
        BettingAction(ActionType.CHECK),
    )

    with pytest.raises(ValueError):
        store.get_or_create(
            state,
            different_actions,
        )


def test_cannot_create_node_without_actions() -> None:
    store = NodeStore()
    state = make_information_state()

    with pytest.raises(ValueError):
        store.get_or_create(
            state,
            (),
        )


def test_get_unknown_state_returns_none() -> None:
    store = NodeStore()
    state = make_information_state()

    assert store.get(state) is None


def test_different_states_create_different_nodes() -> None:
    store = NodeStore()

    state_zero = make_information_state(
        acting_seat=0,
    )

    state_one = make_information_state(
        acting_seat=1,
    )

    store.get_or_create(
        state_zero,
        make_betting_actions(),
    )

    store.get_or_create(
        state_one,
        make_betting_actions(),
    )

    assert len(store) == 2


def test_store_supports_discard_nodes() -> None:
    store = NodeStore()

    state = make_information_state(
        phase="draw",
    )

    actions = (
        DiscardAction(()),
        DiscardAction((4,)),
    )

    node = store.get_or_create(
        state,
        actions,
    )

    assert node.actions == actions


def test_remove_existing_node() -> None:
    store = NodeStore()
    state = make_information_state()

    store.get_or_create(
        state,
        make_betting_actions(),
    )

    store.remove(state)

    assert len(store) == 0
    assert state not in store


def test_remove_unknown_node_is_rejected() -> None:
    store = NodeStore()
    state = make_information_state()

    with pytest.raises(KeyError):
        store.remove(state)


def test_clear_removes_all_nodes() -> None:
    store = NodeStore()

    first_state = make_information_state(
        acting_seat=0,
    )

    second_state = make_information_state(
        acting_seat=1,
    )

    store.get_or_create(
        first_state,
        make_betting_actions(),
    )

    store.get_or_create(
        second_state,
        make_betting_actions(),
    )

    store.clear()

    assert len(store) == 0


def test_average_strategies_returns_each_node() -> None:
    store = NodeStore()
    state = make_information_state()
    actions = make_betting_actions()

    node = store.get_or_create(
        state,
        actions,
    )

    node.strategy_sum[actions[0]] = 1.0
    node.strategy_sum[actions[1]] = 3.0

    strategies = store.average_strategies()

    assert strategies[state][
        actions[0]
    ] == pytest.approx(0.25)

    assert strategies[state][
        actions[1]
    ] == pytest.approx(0.75)