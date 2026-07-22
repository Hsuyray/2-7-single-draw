from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand import Hand


def test_draw_hand_bucket_is_hashable() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert isinstance(
        bucket,
        DrawHandBucket,
    )
    assert isinstance(hash(bucket), int)


def test_rank_bands_are_created() -> None:
    hand = Hand.from_strings(
        "2c",
        "6d",
        "8h",
        "Ts",
        "Ac",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.rank_bands == (
        0,
        1,
        2,
        3,
        3,
    )


def test_similar_rank_structures_share_bucket() -> None:
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
    ) == draw_hand_bucket(
        second_hand
    )


def test_different_rank_bands_differ() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "8s",
        "Kc",
    )

    assert draw_hand_bucket(
        first_hand
    ) != draw_hand_bucket(
        second_hand
    )


def test_pair_positions_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "5h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.duplicate_flags == (
        True,
        True,
        False,
        False,
        False,
    )


def test_unpaired_hand_has_no_duplicate_flags() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.duplicate_flags == (
        False,
        False,
        False,
        False,
        False,
    )


def test_three_card_suit_is_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5c",
        "7h",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.dominant_suit_flags == (
        True,
        False,
        True,
        False,
        True,
    )


def test_two_card_suit_is_ignored() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.dominant_suit_flags == (
        False,
        False,
        False,
        False,
        False,
    )


def test_suit_names_do_not_matter() -> None:
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
        "7c",
        "Kh",
    )

    assert draw_hand_bucket(
        first_hand
    ) == draw_hand_bucket(
        second_hand
    )


def test_different_dominant_suit_positions_differ() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "5c",
        "7h",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3c",
        "5h",
        "7c",
        "Kd",
    )

    assert draw_hand_bucket(
        first_hand
    ) != draw_hand_bucket(
        second_hand
    )