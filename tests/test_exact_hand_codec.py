import pytest

from solver.actions import (
    DiscardAction,
)
from solver.exact_hand_codec import (
    actual_discard_action_for_hand,
    canonical_discard_action_for_hand,
    exact_hand_from_key,
    exact_hand_index_encoding,
)
from solver.hand import (
    Hand,
)
from solver.hand_abstraction import (
    ExactHandEncoding,
    ExactHandKey,
    exact_hand_encoding,
    exact_hand_key,
)


def test_exact_hand_key_remains_backward_compatible() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    encoding = exact_hand_encoding(
        hand
    )

    assert (
        exact_hand_key(hand)
        == encoding.key
    )


def test_exact_hand_encoding_returns_mapping() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    encoding = exact_hand_encoding(
        hand
    )

    assert isinstance(
        encoding,
        ExactHandEncoding,
    )

    assert isinstance(
        encoding.key,
        ExactHandKey,
    )

    assert len(
        encoding.original_to_canonical
    ) == 5

    assert len(
        encoding.canonical_to_original
    ) == 5


def test_exact_hand_mappings_are_inverses() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    encoding = exact_hand_encoding(
        hand
    )

    for original_index in range(
        5
    ):
        canonical_index = (
            encoding
            .original_to_canonical[
                original_index
            ]
        )

        assert (
            encoding
            .canonical_to_original[
                canonical_index
            ]
            == original_index
        )


def test_suit_canonicalization_can_swap_pair_indices() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    encoding = exact_hand_encoding(
        hand
    )

    # Original Hand.cards:
    #
    # 0: 2s
    # 1: 4s
    # 2: 6s
    # 3: 7d
    # 4: 7s
    #
    # The spade suit becomes canonical suit 0
    # because it contains the low-card
    # structure. The canonical pair ordering
    # therefore becomes:
    #
    # canonical index 3 -> original 7s
    # canonical index 4 -> original 7d
    assert (
        encoding.canonical_to_original[
            3
        ]
        == 4
    )

    assert (
        encoding.canonical_to_original[
            4
        ]
        == 3
    )


def test_actual_discard_action_maps_canonical_index() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    canonical_action = DiscardAction(
        (3,)
    )

    actual_action = (
        actual_discard_action_for_hand(
            hand=hand,
            action=canonical_action,
        )
    )

    # Canonical index 3 is the original 7s,
    # which is original Hand.cards index 4.
    assert actual_action == (
        DiscardAction(
            (4,)
        )
    )


def test_canonical_discard_action_maps_actual_index() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    actual_action = DiscardAction(
        (4,)
    )

    canonical_action = (
        canonical_discard_action_for_hand(
            hand=hand,
            action=actual_action,
        )
    )

    assert canonical_action == (
        DiscardAction(
            (3,)
        )
    )


def test_discard_action_mapping_round_trip() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    original_action = DiscardAction(
        (
            0,
            3,
        )
    )

    canonical_action = (
        canonical_discard_action_for_hand(
            hand=hand,
            action=original_action,
        )
    )

    restored_action = (
        actual_discard_action_for_hand(
            hand=hand,
            action=canonical_action,
        )
    )

    assert (
        restored_action
        == original_action
    )


def test_multiple_discard_indices_are_sorted() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    canonical_action = DiscardAction(
        (
            0,
            4,
        )
    )

    actual_action = (
        actual_discard_action_for_hand(
            hand=hand,
            action=canonical_action,
        )
    )

    assert (
        actual_action.discard_indices
        == tuple(
            sorted(
                actual_action.discard_indices
            )
        )
    )


def test_exact_hand_from_key_round_trip() -> None:
    hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    hand_key = exact_hand_key(
        hand
    )

    restored_hand = exact_hand_from_key(
        hand_key
    )

    assert (
        exact_hand_key(
            restored_hand
        )
        == hand_key
    )


def test_suit_isomorphic_hands_share_key() -> None:
    first = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    second = Hand.from_strings(
        "2c",
        "4c",
        "6c",
        "7c",
        "7h",
    )

    assert (
        exact_hand_key(first)
        == exact_hand_key(second)
    )


def test_codec_alias_returns_encoding() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    result = exact_hand_index_encoding(
        hand
    )

    assert isinstance(
        result,
        ExactHandEncoding,
    )

    assert (
        result.key
        == exact_hand_key(hand)
    )


def test_actual_mapping_rejects_out_of_range_index() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Discard index is outside "
            "the hand"
        ),
    ):
        actual_discard_action_for_hand(
            hand=hand,
            action=DiscardAction(
                (99,)
            ),
        )


def test_canonical_mapping_rejects_out_of_range_index() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "5h",
        "7s",
        "Kc",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Discard index is outside "
            "the hand"
        ),
    ):
        canonical_discard_action_for_hand(
            hand=hand,
            action=DiscardAction(
                (99,)
            ),
        )