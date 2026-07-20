from solver.hand import Hand
from solver.hand_abstraction import (
    ExactHandKey,
    exact_hand_key,
)


def test_exact_hand_key_is_hashable() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    key = exact_hand_key(hand)

    assert isinstance(key, ExactHandKey)
    assert isinstance(hash(key), int)


def test_same_hand_order_produces_same_key() -> None:
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

    assert exact_hand_key(
        first_hand
    ) == exact_hand_key(
        second_hand
    )


def test_suit_isomorphic_hands_share_key() -> None:
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

    assert exact_hand_key(
        first_hand
    ) == exact_hand_key(
        second_hand
    )


def test_different_rank_structures_have_different_keys() -> None:
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

    assert exact_hand_key(
        seven_low
    ) != exact_hand_key(
        eight_low
    )


def test_flush_and_non_flush_have_different_keys() -> None:
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

    assert exact_hand_key(
        flush
    ) != exact_hand_key(
        non_flush
    )


def test_same_rank_pattern_with_different_suit_pattern_differs() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "3c",
        "4d",
        "5h",
        "7s",
    )

    second_hand = Hand.from_strings(
        "2c",
        "3d",
        "4d",
        "5h",
        "7s",
    )

    assert exact_hand_key(
        first_hand
    ) != exact_hand_key(
        second_hand
    )


def test_pairs_are_preserved() -> None:
    pair_of_twos = Hand.from_strings(
        "2c",
        "2d",
        "4h",
        "5s",
        "7c",
    )

    pair_of_threes = Hand.from_strings(
        "3c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    assert exact_hand_key(
        pair_of_twos
    ) != exact_hand_key(
        pair_of_threes
    )


def test_suit_names_do_not_matter_for_pair_hand() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "2d",
        "4h",
        "5s",
        "7c",
    )

    second_hand = Hand.from_strings(
        "2h",
        "2s",
        "4c",
        "5d",
        "7h",
    )

    assert exact_hand_key(
        first_hand
    ) == exact_hand_key(
        second_hand
    )


def test_straight_structure_is_preserved() -> None:
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

    assert exact_hand_key(
        straight
    ) != exact_hand_key(
        non_straight
    )