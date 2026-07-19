import pytest

from solver.chips import (
    bb_to_units,
    split_units,
    units_to_bb,
)


def test_convert_bb_to_units() -> None:
    assert bb_to_units(0.5) == 5
    assert bb_to_units(1.0) == 10
    assert bb_to_units(1.5) == 15
    assert bb_to_units(25.0) == 250
    assert bb_to_units(100.0) == 1000


def test_convert_units_to_bb() -> None:
    assert units_to_bb(5) == 0.5
    assert units_to_bb(10) == 1.0
    assert units_to_bb(15) == 1.5
    assert units_to_bb(250) == 25.0
    assert units_to_bb(1000) == 100.0


def test_bb_amount_is_rounded_to_one_decimal_place() -> None:
    assert bb_to_units(2.34) == 23
    assert bb_to_units(2.36) == 24


def test_zero_bb_is_allowed() -> None:
    assert bb_to_units(0.0) == 0


def test_negative_bb_amount_is_rejected() -> None:
    with pytest.raises(ValueError):
        bb_to_units(-0.1)


def test_units_must_be_integer() -> None:
    with pytest.raises(TypeError):
        units_to_bb(10.5)


def test_split_units_evenly() -> None:
    payouts = split_units(
        total_units=100,
        winner_seats=(0, 1),
    )

    assert payouts == {
        0: 50,
        1: 50,
    }


def test_split_units_with_remainder() -> None:
    payouts = split_units(
        total_units=101,
        winner_seats=(0, 1),
    )

    assert payouts == {
        0: 51,
        1: 50,
    }


def test_split_units_between_three_winners() -> None:
    payouts = split_units(
        total_units=100,
        winner_seats=(0, 1, 2),
    )

    assert payouts == {
        0: 34,
        1: 33,
        2: 33,
    }


def test_split_is_independent_of_winner_input_order() -> None:
    payouts = split_units(
        total_units=101,
        winner_seats=(3, 1),
    )

    assert payouts == {
        1: 51,
        3: 50,
    }


def test_split_requires_at_least_one_winner() -> None:
    with pytest.raises(ValueError):
        split_units(
            total_units=100,
            winner_seats=(),
        )


def test_split_rejects_duplicate_winners() -> None:
    with pytest.raises(ValueError):
        split_units(
            total_units=100,
            winner_seats=(0, 0),
        )


def test_split_rejects_negative_total() -> None:
    with pytest.raises(ValueError):
        split_units(
            total_units=-1,
            winner_seats=(0,),
        )