import pytest

from solver.pots import Pot, build_pots


def test_equal_commitments_create_one_pot() -> None:
    pots = build_pots([10.0, 10.0, 10.0])

    assert pots == [
        Pot(
            amount=30.0,
            eligible_seats=(0, 1, 2),
        )
    ]


def test_one_short_stack_creates_main_and_side_pot() -> None:
    pots = build_pots([5.0, 10.0, 10.0])

    assert pots == [
        Pot(
            amount=15.0,
            eligible_seats=(0, 1, 2),
        ),
        Pot(
            amount=10.0,
            eligible_seats=(1, 2),
        ),
    ]


def test_multiple_all_ins_create_multiple_side_pots() -> None:
    pots = build_pots([5.0, 10.0, 20.0, 20.0])

    assert pots == [
        Pot(
            amount=20.0,
            eligible_seats=(0, 1, 2, 3),
        ),
        Pot(
            amount=15.0,
            eligible_seats=(1, 2, 3),
        ),
        Pot(
            amount=20.0,
            eligible_seats=(2, 3),
        ),
    ]


def test_folded_player_chips_remain_in_pot() -> None:
    pots = build_pots(
        commitments=[10.0, 10.0, 10.0],
        folded_seats={1},
    )

    assert pots == [
        Pot(
            amount=30.0,
            eligible_seats=(0, 2),
        )
    ]


def test_folded_big_stack_still_funds_side_pot() -> None:
    pots = build_pots(
        commitments=[5.0, 20.0, 20.0],
        folded_seats={1},
    )

    assert pots == [
        Pot(
            amount=15.0,
            eligible_seats=(0, 2),
        ),
        Pot(
            amount=30.0,
            eligible_seats=(2,),
        ),
    ]


def test_zero_commitment_player_is_excluded() -> None:
    pots = build_pots([0.0, 10.0, 10.0])

    assert pots == [
        Pot(
            amount=20.0,
            eligible_seats=(1, 2),
        )
    ]


def test_all_zero_commitments_create_no_pots() -> None:
    pots = build_pots([0.0, 0.0, 0.0])

    assert pots == []


def test_total_pot_equals_total_commitments() -> None:
    commitments = [3.0, 7.0, 12.0, 12.0]

    pots = build_pots(commitments)

    assert sum(pot.amount for pot in pots) == sum(commitments)


def test_negative_commitment_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_pots([10.0, -1.0, 10.0])


def test_empty_commitments_are_rejected() -> None:
    with pytest.raises(ValueError):
        build_pots([])


def test_invalid_folded_seat_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_pots(
            commitments=[10.0, 10.0],
            folded_seats={2},
        )