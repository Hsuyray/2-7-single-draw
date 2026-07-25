from solver.actions import DiscardAction
from solver.discard_actions import (
    candidate_discard_actions,
    generate_discard_actions,
)
from solver.hand import Hand


def test_full_action_space_has_26_actions() -> None:
    actions = generate_discard_actions(
        hand_size=5,
        max_draw=3,
    )

    assert len(actions) == 26


def test_candidate_action_space_is_reduced() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "7s",
        "Kc",
    )

    actions = candidate_discard_actions(
        hand,
        max_draw=3,
    )

    assert len(actions) == 12
    assert len(actions) < 26


def test_candidate_actions_include_stand_pat() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "7c",
    )

    actions = candidate_discard_actions(
        hand
    )

    assert DiscardAction(()) in actions


def test_all_single_discards_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "Kc",
    )

    actions = candidate_discard_actions(
        hand
    )

    for index in range(5):
        assert (
            DiscardAction((index,))
            in actions
        )


def test_four_card_wheel_can_discard_king() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "Kc",
    )

    actions = candidate_discard_actions(
        hand
    )

    assert DiscardAction((4,)) in actions


def test_three_card_low_can_discard_two_high_cards() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "Qs",
        "Kc",
    )

    actions = candidate_discard_actions(
        hand
    )

    assert (
        DiscardAction((3, 4))
        in actions
    )


def test_two_card_low_can_discard_three_high_cards() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "Jh",
        "Qs",
        "Kc",
    )

    actions = candidate_discard_actions(
        hand
    )

    assert (
        DiscardAction((2, 3, 4))
        in actions
    )


def test_both_pair_breaking_discards_are_preserved() -> None:
    hand = Hand.from_strings(
        "2c",
        "2d",
        "4h",
        "5s",
        "7c",
    )

    actions = candidate_discard_actions(
        hand
    )

    assert DiscardAction((0,)) in actions
    assert DiscardAction((1,)) in actions


def test_max_draw_one_has_six_actions() -> None:
    hand = Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "Kc",
    )

    actions = candidate_discard_actions(
        hand,
        max_draw=1,
    )

    assert len(actions) == 6


def test_candidate_actions_are_deterministic() -> None:
    hand = Hand.from_strings(
        "2c",
        "5d",
        "8h",
        "Js",
        "Kc",
    )

    first = candidate_discard_actions(
        hand
    )
    second = candidate_discard_actions(
        hand
    )

    assert first == second


def test_same_bucket_has_same_candidate_actions() -> None:
    first_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Qc",
    )

    second_hand = Hand.from_strings(
        "2c",
        "4d",
        "6h",
        "8s",
        "Ac",
    )

    first_actions = (
        candidate_discard_actions(
            first_hand
        )
    )

    second_actions = (
        candidate_discard_actions(
            second_hand
        )
    )

    assert first_actions == second_actions