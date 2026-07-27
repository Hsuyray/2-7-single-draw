import pytest

from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand import Hand


def test_rank_classes_use_v4_bands() -> None:
    hand = Hand.from_strings(
        "2c",
        "6d",
        "8h",
        "9s",
        "Ac",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.rank_classes == (
        0,
        2,
        3,
        3,
        5,
    )


def test_two_and_three_share_class() -> None:
    two_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    three_hand = Hand.from_strings(
        "3c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    assert (
        draw_hand_bucket(two_hand).rank_classes
        == draw_hand_bucket(
            three_hand
        ).rank_classes
    )


def test_four_and_five_share_class() -> None:
    four_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    five_hand = Hand.from_strings(
        "2c",
        "5d",
        "6h",
        "8s",
        "Qc",
    )

    assert (
        draw_hand_bucket(four_hand).rank_classes
        == draw_hand_bucket(
            five_hand
        ).rank_classes
    )


def test_six_and_seven_share_class() -> None:
    six_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    seven_hand = Hand.from_strings(
        "2c",
        "4d",
        "7h",
        "8s",
        "Qc",
    )

    assert (
        draw_hand_bucket(six_hand).rank_classes
        == draw_hand_bucket(
            seven_hand
        ).rank_classes
    )


def test_eight_and_nine_share_class() -> None:
    eight_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    nine_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "9s",
        "Qc",
    )

    assert (
        draw_hand_bucket(eight_hand).rank_classes
        == draw_hand_bucket(
            nine_hand
        ).rank_classes
    )


def test_ten_and_jack_share_class() -> None:
    ten_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Tc",
    )

    jack_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Jc",
    )

    assert (
        draw_hand_bucket(ten_hand).rank_classes
        == draw_hand_bucket(
            jack_hand
        ).rank_classes
    )


def test_queen_king_and_ace_share_class() -> None:
    queen_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    king_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Kc",
    )

    ace_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Ac",
    )

    queen_bucket = draw_hand_bucket(
        queen_hand
    )

    assert (
        queen_bucket.rank_classes
        == draw_hand_bucket(
            king_hand
        ).rank_classes
    )

    assert (
        queen_bucket.rank_classes
        == draw_hand_bucket(
            ace_hand
        ).rank_classes
    )


def test_different_rank_bands_differ() -> None:
    low_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    high_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "Tc",
        "Qs",
    )

    assert (
        draw_hand_bucket(low_hand).rank_classes
        != draw_hand_bucket(
            high_hand
        ).rank_classes
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

    assert bucket.pair_classes == (0,)
    assert bucket.trip_classes == ()
    assert bucket.quad_classes == ()
    assert bucket.unique_rank_count == 4


def test_unpaired_hand_has_no_duplicate_classes() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
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

    assert bucket.pair_classes == ()
    assert bucket.trip_classes == ()
    assert bucket.quad_classes == ()
    assert bucket.unique_rank_count == 5


def test_two_pair_classes_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "5h",
        "5s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.pair_classes == (
        0,
        1,
    )

    assert bucket.trip_classes == ()
    assert bucket.quad_classes == ()
    assert bucket.unique_rank_count == 3


def test_trip_class_is_preserved() -> None:
    hand = Hand.from_strings(
        "4c",
        "4d",
        "4h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.pair_classes == ()
    assert bucket.trip_classes == (1,)
    assert bucket.quad_classes == ()
    assert bucket.unique_rank_count == 3


def test_quad_class_is_preserved() -> None:
    hand = Hand.from_strings(
        "9c",
        "9d",
        "9h",
        "9s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.pair_classes == ()
    assert bucket.trip_classes == ()
    assert bucket.quad_classes == (3,)
    assert bucket.unique_rank_count == 2


def test_three_card_flush_structure_is_ignored() -> None:
    first = Hand.from_strings(
        "2c",
        "4c",
        "6c",
        "8d",
        "Ks",
    )

    second = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Kc",
    )

    first_bucket = draw_hand_bucket(
        first
    )
    second_bucket = draw_hand_bucket(
        second
    )

    assert (
        first_bucket.flush_risk_positions
        == (
            False,
            False,
            False,
            False,
            False,
        )
    )

    assert (
        second_bucket.flush_risk_positions
        == (
            False,
            False,
            False,
            False,
            False,
        )
    )


def test_four_card_flush_risk_positions_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "4c",
        "6c",
        "8c",
        "Ks",
    )

    bucket = draw_hand_bucket(hand)

    assert (
        bucket.flush_risk_positions
        == (
            True,
            True,
            True,
            True,
            False,
        )
    )

    assert not bucket.is_flush


def test_four_card_flush_differs_from_rainbow() -> None:
    flush_draw = Hand.from_strings(
        "2c",
        "4c",
        "6c",
        "8c",
        "Ks",
    )

    rainbow = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Kc",
    )

    assert (
        draw_hand_bucket(
            flush_draw
        ).flush_risk_positions
        != draw_hand_bucket(
            rainbow
        ).flush_risk_positions
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

    assert bucket.is_flush

    assert (
        bucket.flush_risk_positions
        == (
            True,
            True,
            True,
            True,
            True,
        )
    )


def test_non_flush_has_no_flush_risk() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert not bucket.is_flush

    assert (
        bucket.flush_risk_positions
        == (
            False,
            False,
            False,
            False,
            False,
        )
    )


def test_straight_is_detected() -> None:
    hand = Hand.from_strings(
        "5c",
        "6d",
        "7h",
        "8s",
        "9c",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_straight


def test_non_straight_is_not_detected() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "9c",
    )

    bucket = draw_hand_bucket(hand)

    assert not bucket.is_straight


def test_wheel_is_not_straight_in_deuce_to_seven() -> None:
    hand = Hand.from_strings(
        "Ac",
        "2d",
        "3h",
        "4s",
        "5c",
    )

    bucket = draw_hand_bucket(hand)

    assert not bucket.is_straight


def test_broadway_is_straight() -> None:
    hand = Hand.from_strings(
        "Tc",
        "Jd",
        "Qh",
        "Ks",
        "Ac",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_straight


def test_hand_requires_exactly_five_cards() -> None:
    with pytest.raises(ValueError):
        Hand.from_strings(
            "2c",
            "3d",
            "4h",
            "5s",
        )


def test_draw_hand_bucket_returns_bucket_type() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert isinstance(
        bucket,
        DrawHandBucket,
    )