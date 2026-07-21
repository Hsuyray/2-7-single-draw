from solver.hand import Hand
from solver.hand_bucket import (
    HandBucket,
    hand_bucket,
)


def test_hand_bucket_is_hashable() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "7s",
        "Kc",
    )

    bucket = hand_bucket(hand)

    assert isinstance(bucket, HandBucket)
    assert isinstance(hash(bucket), int)


def test_low_ranks_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "7s",
        "9c",
    )

    bucket = hand_bucket(hand)

    assert bucket.bucketed_ranks == (
        2,
        3,
        4,
        7,
        9,
    )


def test_ten_and_higher_share_high_card_bucket() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "Th",
        "Qs",
        "Ac",
    )

    bucket = hand_bucket(hand)

    assert bucket.bucketed_ranks == (
        2,
        3,
        10,
        10,
        10,
    )


def test_broadway_cards_can_share_bucket() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "Ts",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "Qs",
        "Ac",
    )

    assert hand_bucket(
        first_hand
    ) == hand_bucket(
        second_hand
    )


def test_different_low_cards_have_different_buckets() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "7s",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    assert hand_bucket(
        first_hand
    ) != hand_bucket(
        second_hand
    )


def test_pair_structure_is_preserved() -> None:
    pair_hand = Hand.from_strings(
        "2c",
        "2d",
        "4h",
        "7s",
        "Kc",
    )

    unpaired_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "7s",
        "Kc",
    )

    assert hand_bucket(
        pair_hand
    ).rank_multiplicities == (
        2,
        1,
        1,
        1,
    )

    assert hand_bucket(
        unpaired_hand
    ).rank_multiplicities == (
        1,
        1,
        1,
        1,
        1,
    )

    assert hand_bucket(
        pair_hand
    ) != hand_bucket(
        unpaired_hand
    )


def test_trips_structure_is_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "2h",
        "7s",
        "Kc",
    )

    bucket = hand_bucket(hand)

    assert bucket.rank_multiplicities == (
        3,
        1,
        1,
    )


def test_flush_structure_is_preserved() -> None:
    flush = Hand.from_strings(
        "2c",
        "3c",
        "4c",
        "7c",
        "Kc",
    )

    non_flush = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "7s",
        "Kc",
    )

    assert hand_bucket(
        flush
    ).max_suit_count == 5

    assert hand_bucket(
        non_flush
    ).max_suit_count == 2

    assert hand_bucket(
        flush
    ) != hand_bucket(
        non_flush
    )


def test_suit_names_do_not_matter() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "7s",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2h",
        "3s",
        "4c",
        "7d",
        "Kh",
    )

    assert hand_bucket(
        first_hand
    ) == hand_bucket(
        second_hand
    )


def test_different_suit_patterns_do_not_share_bucket() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3c",
        "4d",
        "7h",
        "Ks",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3d",
        "4d",
        "7h",
        "Ks",
    )

    assert hand_bucket(
        first_hand
    ) != hand_bucket(
        second_hand
    )


def test_low_card_mask_uses_canonical_positions() -> None:
    hand = Hand.from_strings(
        "2c",
        "4d",
        "7h",
        "Ts",
        "Kc",
    )

    bucket = hand_bucket(hand)

    assert bucket.low_card_mask == 0b00111
    assert bucket.unique_low_count == 3


def test_pair_does_not_increase_unique_low_count() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "4h",
        "7s",
        "Kc",
    )

    bucket = hand_bucket(hand)

    assert bucket.unique_low_count == 3