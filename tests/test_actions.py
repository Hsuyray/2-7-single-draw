import pytest

from solver.actions import DiscardAction


def test_stand_pat_action() -> None:
    action = DiscardAction(())

    assert action.draw_count == 0
    assert action.is_stand_pat is True
    assert action.keep_indices() == (0, 1, 2, 3, 4)


def test_draw_one_action() -> None:
    action = DiscardAction((4,))

    assert action.draw_count == 1
    assert action.is_stand_pat is False
    assert action.keep_indices() == (0, 1, 2, 3)


def test_draw_three_action() -> None:
    action = DiscardAction((2, 3, 4))

    assert action.draw_count == 3
    assert action.keep_indices() == (0, 1)


def test_action_converts_to_mask() -> None:
    action = DiscardAction((1, 3))

    assert action.to_mask() == 0b01010


def test_action_can_be_created_from_mask() -> None:
    action = DiscardAction.from_mask(
        0b10101,
    )

    assert action.discard_indices == (0, 2, 4)


def test_mask_round_trip() -> None:
    original = DiscardAction((0, 2, 4))

    restored = DiscardAction.from_mask(
        original.to_mask()
    )

    assert restored == original


def test_duplicate_indices_are_rejected() -> None:
    with pytest.raises(ValueError):
        DiscardAction((2, 2))


def test_negative_index_is_rejected() -> None:
    with pytest.raises(ValueError):
        DiscardAction((-1,))


def test_unsorted_indices_are_rejected() -> None:
    with pytest.raises(ValueError):
        DiscardAction((3, 1))


def test_index_outside_hand_is_rejected() -> None:
    action = DiscardAction((5,))

    with pytest.raises(ValueError):
        action.validate_for_hand_size(5)


def test_keep_indices_validates_hand_size() -> None:
    action = DiscardAction((3,))

    with pytest.raises(ValueError):
        action.keep_indices(
            hand_size=3,
        )


def test_negative_hand_size_is_rejected() -> None:
    action = DiscardAction(())

    with pytest.raises(ValueError):
        action.validate_for_hand_size(-1)


def test_negative_mask_is_rejected() -> None:
    with pytest.raises(ValueError):
        DiscardAction.from_mask(-1)


def test_mask_outside_hand_is_rejected() -> None:
    with pytest.raises(ValueError):
        DiscardAction.from_mask(
            0b100000,
            hand_size=5,
        )


def test_custom_hand_size() -> None:
    action = DiscardAction((1, 2))

    assert action.keep_indices(
        hand_size=4,
    ) == (0, 3)

    assert action.to_mask(
        hand_size=4,
    ) == 0b0110