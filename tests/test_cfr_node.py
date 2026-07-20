import pytest

from solver.actions import DiscardAction
from solver.cfr_node import CFRNode
from solver.game_state import ActionType
from solver.legal_actions import BettingAction


def make_betting_actions() -> tuple[
    BettingAction,
    ...,
]:
    return (
        BettingAction(ActionType.FOLD),
        BettingAction(ActionType.CALL),
        BettingAction(
            ActionType.RAISE,
            raise_to=6.0,
        ),
    )


def test_node_requires_at_least_one_action() -> None:
    with pytest.raises(ValueError):
        CFRNode(actions=())


def test_node_rejects_duplicate_actions() -> None:
    action = DiscardAction(())

    with pytest.raises(ValueError):
        CFRNode(
            actions=(
                action,
                action,
            )
        )


def test_new_node_initializes_zero_regrets() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    assert node.regret_sum == {
        action: 0.0
        for action in actions
    }


def test_new_node_initializes_zero_strategy_sum() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    assert node.strategy_sum == {
        action: 0.0
        for action in actions
    }


def test_zero_regrets_produce_uniform_strategy() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    strategy = node.current_strategy()

    for action in actions:
        assert strategy[action] == pytest.approx(
            1.0 / 3.0
        )

    assert sum(strategy.values()) == pytest.approx(
        1.0
    )


def test_only_positive_regrets_are_used() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    node.regret_sum[actions[0]] = -5.0
    node.regret_sum[actions[1]] = 2.0
    node.regret_sum[actions[2]] = 6.0

    strategy = node.current_strategy()

    assert strategy[actions[0]] == 0.0
    assert strategy[actions[1]] == pytest.approx(
        0.25
    )
    assert strategy[actions[2]] == pytest.approx(
        0.75
    )


def test_all_non_positive_regrets_produce_uniform_strategy() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    node.regret_sum[actions[0]] = -1.0
    node.regret_sum[actions[1]] = 0.0
    node.regret_sum[actions[2]] = -3.0

    strategy = node.current_strategy()

    for action in actions:
        assert strategy[action] == pytest.approx(
            1.0 / 3.0
        )


def test_add_regret_updates_one_action() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    node.add_regret(
        actions[1],
        2.5,
    )
    node.add_regret(
        actions[1],
        -0.5,
    )

    assert node.regret_sum[actions[1]] == 2.0


def test_add_regret_rejects_unknown_action() -> None:
    node = CFRNode(
        actions=make_betting_actions()
    )

    unknown_action = BettingAction(
        ActionType.CHECK
    )

    with pytest.raises(ValueError):
        node.add_regret(
            unknown_action,
            1.0,
        )


def test_add_multiple_regrets() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    node.add_regrets(
        {
            actions[0]: -1.0,
            actions[1]: 2.0,
            actions[2]: 4.0,
        }
    )

    assert node.regret_sum == {
        actions[0]: -1.0,
        actions[1]: 2.0,
        actions[2]: 4.0,
    }


def test_add_multiple_regrets_rejects_unknown_action() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    unknown_action = BettingAction(
        ActionType.CHECK
    )

    with pytest.raises(ValueError):
        node.add_regrets(
            {
                unknown_action: 1.0,
            }
        )


def test_accumulate_strategy_uses_realization_weight() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    strategy = node.accumulate_strategy(
        realization_weight=3.0,
    )

    assert strategy[actions[0]] == pytest.approx(
        1.0 / 3.0
    )

    for action in actions:
        assert node.strategy_sum[action] == (
            pytest.approx(1.0)
        )


def test_negative_realization_weight_is_rejected() -> None:
    node = CFRNode(
        actions=make_betting_actions()
    )

    with pytest.raises(ValueError):
        node.accumulate_strategy(
            realization_weight=-1.0,
        )


def test_average_strategy_uses_accumulated_values() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    node.strategy_sum[actions[0]] = 1.0
    node.strategy_sum[actions[1]] = 3.0
    node.strategy_sum[actions[2]] = 6.0

    average = node.average_strategy()

    assert average[actions[0]] == pytest.approx(
        0.1
    )
    assert average[actions[1]] == pytest.approx(
        0.3
    )
    assert average[actions[2]] == pytest.approx(
        0.6
    )
    assert sum(average.values()) == pytest.approx(
        1.0
    )


def test_empty_strategy_sum_produces_uniform_average() -> None:
    actions = make_betting_actions()
    node = CFRNode(actions=actions)

    average = node.average_strategy()

    for action in actions:
        assert average[action] == pytest.approx(
            1.0 / 3.0
        )


def test_node_supports_discard_actions() -> None:
    actions = (
        DiscardAction(()),
        DiscardAction((4,)),
        DiscardAction((3, 4)),
    )
    node = CFRNode(actions=actions)

    node.add_regret(
        DiscardAction((4,)),
        5.0,
    )

    strategy = node.current_strategy()

    assert strategy[DiscardAction((4,))] == 1.0
    assert strategy[DiscardAction(())] == 0.0
    assert strategy[DiscardAction((3, 4))] == 0.0