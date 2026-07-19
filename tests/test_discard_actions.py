import pytest

from solver.actions import DiscardAction
from solver.discard_actions import generate_discard_actions


def test_default_generates_draw_zero_to_three() -> None:
    actions = generate_discard_actions()

    assert len(actions) == 26


def test_default_includes_stand_pat() -> None:
    actions = generate_discard_actions()

    assert DiscardAction(()) in actions


def test_default_includes_draw_one() -> None:
    actions = generate_discard_actions()

    assert DiscardAction((4,)) in actions


def test_default_includes_draw_two() -> None:
    actions = generate_discard_actions()

    assert DiscardAction((3, 4)) in actions


def test_default_includes_draw_three() -> None:
    actions = generate_discard_actions()

    assert DiscardAction((2, 3, 4)) in actions


def test_default_excludes_draw_four() -> None:
    actions = generate_discard_actions()

    assert DiscardAction((1, 2, 3, 4)) not in actions


def test_default_excludes_draw_five() -> None:
    actions = generate_discard_actions()

    assert DiscardAction((0, 1, 2, 3, 4)) not in actions


def test_full_rules_generate_all_32_actions() -> None:
    actions = generate_discard_actions(
        max_draw=5,
    )

    assert len(actions) == 32
    assert DiscardAction(
        (0, 1, 2, 3, 4)
    ) in actions


def test_actions_are_grouped_by_draw_count() -> None:
    actions = generate_discard_actions()

    draw_counts = [
        action.draw_count
        for action in actions
    ]

    assert draw_counts == sorted(draw_counts)


def test_each_action_has_unique_indices() -> None:
    actions = generate_discard_actions(
        max_draw=5,
    )

    for action in actions:
        assert len(action.discard_indices) == len(
            set(action.discard_indices)
        )


def test_each_action_uses_valid_indices() -> None:
    actions = generate_discard_actions(
        hand_size=5,
        max_draw=5,
    )

    for action in actions:
        action.validate_for_hand_size(5)


def test_custom_max_draw_one() -> None:
    actions = generate_discard_actions(
        hand_size=5,
        max_draw=1,
    )

    assert actions == (
        DiscardAction(()),
        DiscardAction((0,)),
        DiscardAction((1,)),
        DiscardAction((2,)),
        DiscardAction((3,)),
        DiscardAction((4,)),
    )


def test_custom_hand_size() -> None:
    actions = generate_discard_actions(
        hand_size=3,
        max_draw=2,
    )

    assert actions == (
        DiscardAction(()),
        DiscardAction((0,)),
        DiscardAction((1,)),
        DiscardAction((2,)),
        DiscardAction((0, 1)),
        DiscardAction((0, 2)),
        DiscardAction((1, 2)),
    )


def test_zero_card_hand_has_only_stand_pat() -> None:
    actions = generate_discard_actions(
        hand_size=0,
        max_draw=0,
    )

    assert actions == (
        DiscardAction(()),
    )


def test_negative_hand_size_is_rejected() -> None:
    with pytest.raises(ValueError):
        generate_discard_actions(
            hand_size=-1,
            max_draw=0,
        )


def test_negative_max_draw_is_rejected() -> None:
    with pytest.raises(ValueError):
        generate_discard_actions(
            max_draw=-1,
        )


def test_max_draw_cannot_exceed_hand_size() -> None:
    with pytest.raises(ValueError):
        generate_discard_actions(
            hand_size=5,
            max_draw=6,
        )
        