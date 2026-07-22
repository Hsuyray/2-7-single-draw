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


def test_similar_high_cards_share_bucket() -> None:
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
        "Qs",
        "Ac",
    )

    assert draw_hand_bucket(
        first_hand
    ) == draw_hand_bucket(
        second_hand
    )


def test_different_rank_bands_do_not_share_bucket() -> None:
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
    assert bucket.unique_rank_count == 4


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


def test_suit_names_do_not_matter() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3d",
        "5c",
        "7h",
        "Ks",
    )

    second_hand = Hand.from_strings(
        "2h",
        "3s",
        "5h",
        "7c",
        "Kd",
    )

    assert draw_hand_bucket(
        first_hand
    ) == draw_hand_bucket(
        second_hand
    )


def test_suit_multiplicity_is_position_specific() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5c",
        "7h",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.suit_multiplicities == (
        3,
        1,
        3,
        1,
        3,
    )


def test_different_suit_structures_differ() -> None:
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

    assert draw_hand_bucket(
        first_hand
    ) != draw_hand_bucket(
        second_hand
    )


def test_unique_low_count_ignores_pairs() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "5h",
        "7s",
        "Kc",
    )

    bucket = draw_hand_bucket(hand)

    assert bucket.unique_low_count == 3
    assert bucket.high_card_count == 1


def test_straight_pressure_detects_connected_cards() -> None:
    connected = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "Kc",
    )

    disconnected = Hand.from_strings(
        "2c",
        "4d",
        "7h",
        "9s",
        "Kc",
    )

    assert (
        draw_hand_bucket(
            connected
        ).straight_pressure
        >
        draw_hand_bucket(
            disconnected
        ).straight_pressure
    )