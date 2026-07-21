import pytest

from solver.hand import Hand
from solver.made_hand_bucket import (
    MadeHandBucket,
    made_hand_bucket,
)


def test_made_hand_bucket_is_hashable() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    bucket = made_hand_bucket(hand)

    assert isinstance(bucket, MadeHandBucket)
    assert isinstance(hash(bucket), int)


def test_same_hand_with_different_suits_shares_bucket() -> None:
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

    assert made_hand_bucket(
        first_hand
    ) == made_hand_bucket(
        second_hand
    )


def test_same_hand_order_does_not_matter() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    second_hand = Hand.from_strings(
        "7c",
        "5s",
        "4h",
        "3d",
        "2c",
    )

    assert made_hand_bucket(
        first_hand
    ) == made_hand_bucket(
        second_hand
    )


def test_seven_low_and_eight_low_differ() -> None:
    seven_low = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    eight_low = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "8c",
    )

    assert made_hand_bucket(
        seven_low
    ) != made_hand_bucket(
        eight_low
    )


def test_pair_and_unpaired_hand_differ() -> None:
    pair_hand = Hand.from_strings(
        "2c",
        "2d",
        "4h",
        "5s",
        "7c",
    )

    unpaired_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    assert made_hand_bucket(
        pair_hand
    ) != made_hand_bucket(
        unpaired_hand
    )


def test_straight_and_non_straight_differ() -> None:
    straight = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "6c",
    )

    non_straight = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    assert made_hand_bucket(
        straight
    ) != made_hand_bucket(
        non_straight
    )


def test_flush_and_non_flush_differ() -> None:
    flush = Hand.from_strings(
        "2c",
        "3c",
        "4c",
        "5c",
        "7c",
    )

    non_flush = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    assert made_hand_bucket(
        flush
    ) != made_hand_bucket(
        non_flush
    )


def test_custom_score_depth() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    bucket = made_hand_bucket(
        hand,
        score_depth=2,
    )

    assert bucket.score_prefix == hand.score[:2]


def test_non_positive_score_depth_is_rejected() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    with pytest.raises(ValueError):
        made_hand_bucket(
            hand,
            score_depth=0,
        )