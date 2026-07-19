import pytest

from solver.action_history import PublicAction


def test_betting_action_is_hashable() -> None:
    action = PublicAction(
        phase="predraw_betting",
        seat=0,
        action_type="call",
    )

    assert isinstance(hash(action), int)


def test_raise_action_can_store_amount() -> None:
    action = PublicAction(
        phase="predraw_betting",
        seat=1,
        action_type="raise",
        amount=6.0,
    )

    assert action.amount == 6.0
    assert action.draw_count is None


def test_draw_action_stores_public_draw_count() -> None:
    action = PublicAction(
        phase="draw",
        seat=2,
        action_type="draw",
        draw_count=2,
    )

    assert action.draw_count == 2


def test_stand_pat_is_draw_zero() -> None:
    action = PublicAction(
        phase="draw",
        seat=0,
        action_type="draw",
        draw_count=0,
    )

    assert action.draw_count == 0


def test_negative_seat_is_rejected() -> None:
    with pytest.raises(ValueError):
        PublicAction(
            phase="draw",
            seat=-1,
            action_type="draw",
            draw_count=1,
        )


def test_empty_phase_is_rejected() -> None:
    with pytest.raises(ValueError):
        PublicAction(
            phase="",
            seat=0,
            action_type="call",
        )


def test_empty_action_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="",
        )


def test_negative_amount_is_rejected() -> None:
    with pytest.raises(ValueError):
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="raise",
            amount=-1.0,
        )


def test_negative_draw_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        PublicAction(
            phase="draw",
            seat=0,
            action_type="draw",
            draw_count=-1,
        )


def test_draw_action_requires_draw_count() -> None:
    with pytest.raises(ValueError):
        PublicAction(
            phase="draw",
            seat=0,
            action_type="draw",
        )


def test_betting_action_cannot_have_draw_count() -> None:
    with pytest.raises(ValueError):
        PublicAction(
            phase="predraw_betting",
            seat=0,
            action_type="call",
            draw_count=1,
        )