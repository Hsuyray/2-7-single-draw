import pytest

from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand import Hand


def test_low_ranks_are_preserved_exactly() -> None:
    hand = Hand.from_strings(
        "2c",
        "6d",
        "8h",
        "9s",
        "Ac",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.rank_classes == (
        2,
        6,
        8,
        9,
        11,
    )


def test_ten_and_jack_share_rank_class() -> None:
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

    assert draw_hand_bucket(
        ten_hand
    ) == draw_hand_bucket(
        jack_hand
    )


def test_queen_king_and_ace_share_rank_class() -> None:
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
    king_bucket = draw_hand_bucket(
        king_hand
    )
    ace_bucket = draw_hand_bucket(
        ace_hand
    )

    assert queen_bucket == king_bucket
    assert king_bucket == ace_bucket


def test_strategically_different_low_ranks_do_not_share_bucket() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "Ts",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2c",
        "4d",
        "5h",
        "Ts",
        "Kc",
    )

    assert draw_hand_bucket(
        first_hand
    ) != draw_hand_bucket(
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

    assert bucket.pair_classes == (2,)
    assert bucket.trip_classes == ()
    assert bucket.quad_classes == ()
    assert bucket.unique_rank_count == 4


def test_unpaired_hand_has_no_duplicate_classes() -> None:
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
    assert bucket.trip_classes == (4,)
    assert bucket.quad_classes == ()

    assert bucket.rank_multiplicities == (
        3,
        3,
        3,
        1,
        1,
    )


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
    assert bucket.quad_classes == (9,)

    assert bucket.rank_multiplicities == (
        4,
        4,
        4,
        4,
        1,
    )


def test_three_card_flush_structure_is_ignored() -> None:
    three_clubs = Hand.from_strings(
        "2c",
        "3d",
        "5c",
        "7h",
        "Kc",
    )

    rainbow_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    assert draw_hand_bucket(
        three_clubs
    ) == draw_hand_bucket(
        rainbow_hand
    )


def test_four_card_flush_risk_is_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "3c",
        "5c",
        "7c",
        "Kd",
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

    assert bucket.is_flush is False


def test_four_card_flush_and_rainbow_do_not_share_bucket() -> None:
    four_clubs = Hand.from_strings(
        "2c",
        "3c",
        "5c",
        "7c",
        "Kd",
    )

    rainbow_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    assert draw_hand_bucket(
        four_clubs
    ) != draw_hand_bucket(
        rainbow_hand
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


def test_non_flush_has_no_flush_risk_positions() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.is_flush is False

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