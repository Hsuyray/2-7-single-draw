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

    assert (
        made_hand_bucket(first_hand)
        == made_hand_bucket(second_hand)
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

    assert (
        made_hand_bucket(first_hand)
        == made_hand_bucket(second_hand)
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

    assert (
        made_hand_bucket(seven_low)
        != made_hand_bucket(eight_low)
    )


def test_same_primary_strength_can_share_secondary_bucket() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "6s",
        "9c",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "6s",
        "9c",
    )

    first_bucket = made_hand_bucket(
        first_hand
    )
    second_bucket = made_hand_bucket(
        second_hand
    )

    assert (
        first_bucket.category
        == second_bucket.category
    )

    assert (
        first_bucket.primary_strength
        == second_bucket.primary_strength
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

    assert (
        made_hand_bucket(pair_hand)
        != made_hand_bucket(unpaired_hand)
    )


def test_two_different_pair_strengths_differ() -> None:
    low_pair = Hand.from_strings(
        "2c",
        "2d",
        "4h",
        "5s",
        "7c",
    )

    higher_pair = Hand.from_strings(
        "4c",
        "4d",
        "5h",
        "6s",
        "8c",
    )

    assert (
        made_hand_bucket(low_pair)
        != made_hand_bucket(higher_pair)
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

    assert (
        made_hand_bucket(straight)
        != made_hand_bucket(non_straight)
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

    assert (
        made_hand_bucket(flush)
        != made_hand_bucket(non_flush)
    )


def test_bucket_fields_match_hand_score_structure() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    bucket = made_hand_bucket(hand)

    assert bucket.category == hand.score[0]
    assert (
        bucket.primary_strength
        == hand.score[1]
    )


def test_secondary_strength_is_bucketed() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "6s",
        "9c",
    )

    bucket = made_hand_bucket(hand)

    assert 0 <= bucket.secondary_strength <= 4


def test_made_hand_bucket_returns_same_result_repeatedly() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "9c",
    )

    first = made_hand_bucket(hand)
    second = made_hand_bucket(hand)

    assert first == second