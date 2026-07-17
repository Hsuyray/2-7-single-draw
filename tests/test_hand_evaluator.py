import pytest

from solver.cards import Card
from solver.hand_evaluator import compare_hands, evaluate_hand


def make_hand(*values: str) -> list[Card]:
    return [Card.from_string(value) for value in values]


def test_seven_low_beats_eight_low() -> None:
    seven_low = make_hand("7s", "5h", "4d", "3c", "2s")
    eight_low = make_hand("8s", "6h", "4d", "3c", "2s")

    assert compare_hands(seven_low, eight_low) == -1


def test_lower_second_card_wins() -> None:
    first = make_hand("8s", "5h", "4d", "3c", "2s")
    second = make_hand("8h", "6d", "4c", "3s", "2h")

    assert compare_hands(first, second) == -1


def test_unpaired_hand_beats_pair() -> None:
    unpaired = make_hand("Ks", "9h", "7d", "4c", "2s")
    pair = make_hand("3s", "3h", "7d", "5c", "2h")

    assert compare_hands(unpaired, pair) == -1


def test_pair_beats_two_pair() -> None:
    pair = make_hand("4s", "4h", "8d", "6c", "2s")
    two_pair = make_hand("3s", "3h", "2d", "2c", "7s")

    assert compare_hands(pair, two_pair) == -1


def test_straight_is_worse_than_three_of_a_kind() -> None:
    straight = make_hand("6s", "5h", "4d", "3c", "2s")
    trips = make_hand("3s", "3h", "3d", "8c", "2s")

    assert compare_hands(trips, straight) == -1


def test_flush_is_worse_than_straight() -> None:
    flush = make_hand("7s", "5s", "4s", "3s", "2s")
    straight = make_hand("6s", "5h", "4d", "3c", "2s")

    assert compare_hands(straight, flush) == -1


def test_ace_is_always_high() -> None:
    ace_high = make_hand("As", "5h", "4d", "3c", "2s")
    king_high = make_hand("Ks", "Qh", "9d", "4c", "2s")

    assert compare_hands(king_high, ace_high) == -1


def test_wheel_is_not_a_straight() -> None:
    wheel = make_hand("As", "5h", "4d", "3c", "2s")

    assert evaluate_hand(wheel)[0] == 0


def test_identical_rank_hands_tie() -> None:
    first = make_hand("7s", "5h", "4d", "3c", "2s")
    second = make_hand("7h", "5d", "4c", "3s", "2h")

    assert compare_hands(first, second) == 0


def test_hand_must_have_exactly_five_cards() -> None:
    hand = make_hand("7s", "5h", "4d", "3c")

    with pytest.raises(ValueError):
        evaluate_hand(hand)


def test_hand_cannot_contain_duplicate_cards() -> None:
    hand = make_hand("7s", "7s", "4d", "3c", "2s")

    with pytest.raises(ValueError):
        evaluate_hand(hand)