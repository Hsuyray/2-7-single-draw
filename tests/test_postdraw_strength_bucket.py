from solver.hand import Hand
from solver.postdraw_strength_bucket import (
    CATEGORY_BUCKET_ALLOCATION,
    POSTDRAW_BUCKET_COUNT,
    PostdrawStrengthBucket,
    postdraw_bucket_count,
    postdraw_bucket_mapping_size,
    postdraw_strength_bucket,
)


def test_category_allocations_sum_to_128() -> None:
    assert (
        sum(
            CATEGORY_BUCKET_ALLOCATION
            .values()
        )
        == POSTDRAW_BUCKET_COUNT
    )


def test_complete_mapping_has_all_scores() -> None:
    assert (
        postdraw_bucket_mapping_size()
        == 7462
    )


def test_complete_mapping_uses_128_buckets() -> None:
    assert (
        postdraw_bucket_count()
        == 128
    )


def test_same_hand_is_deterministic() -> None:
    hand = Hand.from_strings(
        "2s",
        "3h",
        "4d",
        "5c",
        "7s",
    )

    first = (
        postdraw_strength_bucket(
            hand
        )
    )

    second = (
        postdraw_strength_bucket(
            hand
        )
    )

    assert first == second


def test_suit_isomorphic_hands_share_bucket() -> None:
    first = Hand.from_strings(
        "2s",
        "3h",
        "4d",
        "5c",
        "7s",
    )

    second = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    assert (
        postdraw_strength_bucket(
            first
        )
        == postdraw_strength_bucket(
            second
        )
    )


def test_bucket_id_is_valid() -> None:
    hand = Hand.from_strings(
        "2s",
        "3h",
        "4d",
        "5c",
        "7s",
    )

    bucket = (
        postdraw_strength_bucket(
            hand
        )
    )

    assert isinstance(
        bucket,
        PostdrawStrengthBucket,
    )

    assert (
        0
        <= bucket.bucket_id
        < POSTDRAW_BUCKET_COUNT
    )


def test_different_categories_do_not_share_bucket() -> None:
    high_card = Hand.from_strings(
        "2s",
        "3h",
        "4d",
        "5c",
        "7s",
    )

    pair = Hand.from_strings(
        "2s",
        "2h",
        "4d",
        "5c",
        "7s",
    )

    high_card_bucket = (
        postdraw_strength_bucket(
            high_card
        )
    )

    pair_bucket = (
        postdraw_strength_bucket(
            pair
        )
    )

    assert (
        high_card_bucket.category
        != pair_bucket.category
    )

    assert (
        high_card_bucket.bucket_id
        != pair_bucket.bucket_id
    )