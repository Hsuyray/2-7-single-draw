from types import SimpleNamespace

import pytest

from solver.actions import DiscardAction
from solver.cards import Card
from solver.game_state import ActionType
from solver.hand import Hand
from solver.information_state import (
    InformationState,
)
from solver.legal_actions import (
    BettingAction,
)
from solver.node_store import (
    NodeStore,
)


def make_hand(
    *cards: str,
) -> Hand:
    return Hand(
        tuple(
            Card.from_string(card)
            for card in cards
        )
    )


def make_player(
    *,
    seat: int,
    stack: float,
    committed_total: float,
    committed_this_round: float,
    has_folded: bool = False,
    is_all_in: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        seat=seat,
        stack=stack,
        committed_total=committed_total,
        committed_this_round=(
            committed_this_round
        ),
        has_folded=has_folded,
        is_all_in=is_all_in,
    )


def make_information_state(
    *,
    acting_seat: int = 0,
    phase: str = "predraw_betting",
) -> InformationState:
    player_zero = make_player(
        seat=0,
        stack=99.0,
        committed_total=1.0,
        committed_this_round=1.0,
    )

    player_one = make_player(
        seat=1,
        stack=96.5,
        committed_total=3.5,
        committed_this_round=2.0,
    )

    game = SimpleNamespace(
        config=SimpleNamespace(
            player_count=2,
        ),
        hands=[
            make_hand(
                "7s",
                "5h",
                "4d",
                "3c",
                "2s",
            ),
            make_hand(
                "Ks",
                "Qh",
                "Jd",
                "9c",
                "8s",
            ),
        ],
        betting_state=SimpleNamespace(
            players=[
                player_zero,
                player_one,
            ],
            current_bet=2.0,
            minimum_raise_size=2.0,
        ),
        draw_results={},
        action_history=[],
        phase=SimpleNamespace(
            value=phase,
        ),
        acting_seat=acting_seat,
        button_seat=0,
        pot=4.5,
    )

    return InformationState.from_game(
        game,
        observer_seat=acting_seat,
    )


def betting_actions() -> tuple[
    BettingAction,
    ...,
]:
    return (
        BettingAction(
            ActionType.FOLD
        ),
        BettingAction(
            ActionType.CALL
        ),
    )


def test_empty_store_has_length_zero() -> None:
    store = NodeStore()

    assert len(store) == 0


def test_get_or_create_adds_node() -> None:
    store = NodeStore()

    state = make_information_state()

    actions = betting_actions()

    node = store.get_or_create(
        state,
        actions,
    )

    assert node is not None
    assert len(store) == 1

    assert (
        store.get(state)
        is node
    )


def test_get_or_create_returns_same_node() -> None:
    store = NodeStore()

    state = make_information_state()

    actions = betting_actions()

    first = store.get_or_create(
        state,
        actions,
    )

    second = store.get_or_create(
        state,
        actions,
    )

    assert first is second

    assert len(store) == 1


def test_existing_node_preserves_regrets() -> None:
    store = NodeStore()

    state = make_information_state()

    actions = betting_actions()

    node = store.get_or_create(
        state,
        actions,
    )

    node.add_regrets(
        {
            actions[0]: 2.0,
            actions[1]: -1.0,
        }
    )

    same_node = store.get_or_create(
        state,
        actions,
    )

    assert same_node is node

    assert (
        same_node.regret_sum[
            actions[0]
        ]
        == 2.0
    )

    assert (
        same_node.regret_sum[
            actions[1]
        ]
        == -1.0
    )


def test_same_state_with_different_actions_is_rejected() -> None:
    store = NodeStore()

    state = make_information_state()

    original_actions = (
        BettingAction(
            ActionType.FOLD
        ),
        BettingAction(
            ActionType.CALL
        ),
    )

    different_actions = (
        BettingAction(
            ActionType.CALL
        ),
        BettingAction(
            ActionType.RAISE,
            raise_to=6.0,
        ),
    )

    store.get_or_create(
        state,
        original_actions,
    )

    with pytest.raises(
        ValueError
    ):
        store.get_or_create(
            state,
            different_actions,
        )


def test_cannot_create_node_without_actions() -> None:
    store = NodeStore()

    state = make_information_state()

    with pytest.raises(
        ValueError
    ):
        store.get_or_create(
            state,
            (),
        )


def test_get_unknown_state_returns_none() -> None:
    store = NodeStore()

    state = make_information_state()

    assert (
        store.get(state)
        is None
    )


def test_different_states_create_different_nodes() -> None:
    store = NodeStore()

    state_zero = make_information_state(
        acting_seat=0,
    )

    state_one = make_information_state(
        acting_seat=1,
    )

    actions = betting_actions()

    first = store.get_or_create(
        state_zero,
        actions,
    )

    second = store.get_or_create(
        state_one,
        actions,
    )

    assert first is not second

    assert len(store) == 2


def test_store_supports_discard_nodes() -> None:
    store = NodeStore()

    state = make_information_state(
        phase="draw",
    )

    actions = (
        DiscardAction(
            discard_indices=(),
        ),
        DiscardAction(
            discard_indices=(4,),
        ),
    )

    node = store.get_or_create(
        state,
        actions,
    )

    assert node is not None

    assert len(store) == 1

    assert (
        store.get(state)
        is node
    )


def test_remove_existing_node() -> None:
    store = NodeStore()

    state = make_information_state()

    actions = betting_actions()

    store.get_or_create(
        state,
        actions,
    )

    store.remove(
        state
    )

    assert len(store) == 0

    assert (
        store.get(state)
        is None
    )


def test_remove_unknown_node_is_rejected() -> None:
    store = NodeStore()

    state = make_information_state()

    with pytest.raises(
        KeyError
    ):
        store.remove(
            state
        )


def test_clear_removes_all_nodes() -> None:
    store = NodeStore()

    first_state = make_information_state(
        acting_seat=0,
    )

    second_state = make_information_state(
        acting_seat=1,
    )

    actions = betting_actions()

    store.get_or_create(
        first_state,
        actions,
    )

    store.get_or_create(
        second_state,
        actions,
    )

    assert len(store) == 2

    store.clear()

    assert len(store) == 0


def test_average_strategies_returns_each_node() -> None:
    store = NodeStore()

    state = make_information_state()

    actions = betting_actions()

    node = store.get_or_create(
        state,
        actions,
    )

    node.accumulate_strategy(
        realization_weight=1.0,
    )

    strategies = (
        store.average_strategies()
    )

    assert state in strategies

    strategy = strategies[
        state
    ]

    assert (
        set(strategy)
        == set(actions)
    )

    assert abs(
        sum(
            strategy.values()
        )
        - 1.0
    ) < 1e-9