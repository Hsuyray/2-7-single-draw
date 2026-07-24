import pytest

from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand import Hand


def test_rank_values_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "6d",
        "8h",
        "Ts",
        "Ac",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.rank_values == (
        2,
        6,
        8,
        10,
        14,
    )


def test_different_exact_rank_structures_do_not_share_bucket() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "Ts",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2h",
        "4s",
        "5c",
        "Qd",
        "Ah",
    )

    assert draw_hand_bucket(
        first_hand
    ) != draw_hand_bucket(
        second_hand
    )


def test_same_rank_and_suit_structure_share_bucket() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    second_hand = Hand.from_strings(
        "2h",
        "3s",
        "4c",
        "5d",
        "7h",
    )

    assert draw_hand_bucket(
        first_hand
    ) == draw_hand_bucket(
        second_hand
    )


def test_pair_multiplicity_is_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "5h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.rank_multiplicities == (
        2,
        2,
        1,
        1,
        1,
    )

    assert bucket.pair_ranks == (2,)
    assert bucket.trip_ranks == ()
    assert bucket.quad_ranks == ()
    assert bucket.unique_rank_count == 4


def test_unpaired_hand_has_single_multiplicities() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.rank_multiplicities == (
        1,
        1,
        1,
        1,
        1,
    )

    assert bucket.pair_ranks == ()
    assert bucket.trip_ranks == ()
    assert bucket.quad_ranks == ()
    assert bucket.unique_rank_count == 5


def test_two_pair_ranks_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "5h",
        "5s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.pair_ranks == (
        2,
        5,
    )

    assert bucket.rank_multiplicities == (
        2,
        2,
        2,
        2,
        1,
    )

    assert bucket.unique_rank_count == 3


def test_trip_rank_is_preserved() -> None:
    hand = Hand.from_strings(
        "4c",
        "4d",
        "4h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.pair_ranks == ()
    assert bucket.trip_ranks == (4,)
    assert bucket.quad_ranks == ()

    assert bucket.rank_multiplicities == (
        3,
        3,
        3,
        1,
        1,
    )


def test_quad_rank_is_preserved() -> None:
    hand = Hand.from_strings(
        "9c",
        "9d",
        "9h",
        "9s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.pair_ranks == ()
    assert bucket.trip_ranks == ()
    assert bucket.quad_ranks == (9,)

    assert bucket.rank_multiplicities == (
        4,
        4,
        4,
        4,
        1,
    )


def test_suit_pattern_is_canonicalized() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "5c",
        "7h",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2h",
        "3s",
        "5h",
        "7d",
        "Kh",
    )

    first_bucket = draw_hand_bucket(
        first_hand
    )
    second_bucket = draw_hand_bucket(
        second_hand
    )

    assert first_bucket.suit_pattern == (
        0,
        1,
        0,
        2,
        0,
    )

    assert second_bucket.suit_pattern == (
        0,
        1,
        0,
        2,
        0,
    )

    assert first_bucket == second_bucket


def test_different_suit_structures_do_not_share_bucket() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "5c",
        "7h",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    assert (
        draw_hand_bucket(first_hand)
        != draw_hand_bucket(second_hand)
    )


def test_flush_is_detected() -> None:
    hand = Hand.from_strings(
        "2c",
        "4c",
        "6c",
        "8c",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_flush is True


def test_non_flush_is_detected() -> None:
    hand = Hand.from_strings(
        "2c",
        "4c",
        "6c",
        "8c",
        "Kd",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_flush is False


def test_straight_is_detected() -> None:
    hand = Hand.from_strings(
        "3c",
        "4d",
        "5h",
        "6s",
        "7c",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_straight is True


def test_non_straight_is_detected() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_straight is False


def test_ace_is_high_in_straight_detection() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "Ac",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_straight is False


def test_broadway_is_detected_as_straight() -> None:
    hand = Hand.from_strings(
        "Tc",
        "Jd",
        "Qh",
        "Ks",
        "Ac",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_straight is True


def test_hand_requires_five_cards() -> None:
    with pytest.raises(ValueError):
        Hand.from_strings(
            "2c",
            "3d",
            "4h",
            "5s",
        )


def test_return_type_is_draw_hand_bucket() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    bucket = draw_hand_bucket(hand)

    assert isinstance(
        bucket,
        DrawHandBucket,
    )