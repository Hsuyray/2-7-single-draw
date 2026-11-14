"""
D3 draft v0: every 5-card hand falls in exactly one class of each
taxonomy, and the postdraw classes are ordered strength bands that
agree with solver/hand_evaluator.py.
"""

import random

import pytest

from solver.hand import Hand
from solver.hand_classes import (
    POSTDRAW_CLASSES,
    PREDRAW_CLASSES,
    combination_counts,
    postdraw_class,
    postdraw_class_key,
    predraw_class,
    predraw_class_key,
    rank_patterns,
)


RANKS = "23456789TJQKA"
SUITS = "shdc"


def cards_for(
    ranks: tuple[int, ...],
    flush: bool,
) -> Hand:
    """A hand with the given ranks, a flush or not."""
    if flush:
        suits = "sssss"
    elif len(set(ranks)) == 5:
        suits = "shdcs"
    else:
        # The j-th card of a rank gets the j-th suit, so
        # paired ranks never repeat a card (and a paired
        # hand cannot be a flush).
        seen: dict[int, int] = {}
        suits = ""

        for rank in ranks:
            suits += SUITS[seen.get(rank, 0)]
            seen[rank] = seen.get(rank, 0) + 1

    return Hand.from_strings(
        *(
            RANKS[rank - 2] + suit
            for rank, suit in zip(ranks, suits)
        )
    )


def test_counts_cover_every_hand_exactly_once() -> None:
    for kind in ("predraw", "postdraw"):
        counts = combination_counts(kind)

        assert sum(counts.values()) == 2_598_960
        assert all(count > 0 for count in counts.values())


def test_postdraw_counts_match_known_poker_totals() -> None:
    counts = combination_counts("postdraw")

    assert counts["pair"] == 1_098_240
    assert counts["two_pair_trips"] == 123_552 + 54_912
    # 2-7: the ace is high only, so A-2-3-4-5 is no
    # straight: 9 rank sequences.
    assert counts["straight"] == 9 * 1_020
    assert counts["flush"] == 4 * (1_287 - 9)
    assert counts["full_house_plus"] == 3_744 + 624 + 9 * 4


def test_class_keys_are_known_for_every_rank_pattern() -> None:
    predraw_keys = {hand_class.key for hand_class in PREDRAW_CLASSES}
    postdraw_keys = {hand_class.key for hand_class in POSTDRAW_CLASSES}

    for ranks, flush_combos, plain_combos in rank_patterns():
        for flush, combos in ((True, flush_combos), (False, plain_combos)):
            if combos:
                assert predraw_class_key(ranks, flush) in predraw_keys
                assert postdraw_class_key(ranks, flush) in postdraw_keys


def test_postdraw_classes_are_ordered_strength_bands() -> None:
    """
    Every class is a contiguous band of evaluator scores
    (lower = stronger), and the bands follow display order.
    """
    bands: dict[str, list] = {}

    for ranks, flush_combos, plain_combos in rank_patterns():
        for flush, combos in ((True, flush_combos), (False, plain_combos)):
            if not combos:
                continue

            hand = cards_for(ranks, flush)
            key = postdraw_class_key(ranks, flush)

            assert postdraw_class(hand).key == key

            band = bands.setdefault(key, [hand.score, hand.score])
            band[0] = min(band[0], hand.score)
            band[1] = max(band[1], hand.score)

    ordered = [
        bands[hand_class.key]
        for hand_class in POSTDRAW_CLASSES
    ]

    for better, worse in zip(ordered, ordered[1:]):
        assert better[1] < worse[0]


@pytest.mark.parametrize(
    "cards, predraw_key, postdraw_key",
    [
        (("7s", "5h", "4d", "3c", "2s"), "pat_75", "made_75"),
        (("8s", "6h", "4d", "3c", "2s"), "pat_86", "made_86"),
        (("Ts", "8h", "5d", "3c", "2s"), "pat_t", "made_t"),
        # A pair is a one-card draw.
        (("2s", "2h", "3d", "4c", "7s"), "draw1_7s", "pair"),
        (("Ks", "7h", "5d", "3c", "2s"), "draw1_7s", "made_k"),
        (("Ks", "7h", "6d", "3c", "2s"), "draw1_7r", "made_k"),
        (("Ks", "8h", "6d", "3c", "2s"), "draw1_8r", "made_k"),
        # Wheel draw; a flush is not a pat hand.
        (("7s", "5s", "4s", "3s", "2s"), "draw1_6", "flush"),
        (("6s", "5h", "4d", "3c", "2s"), "draw1_6", "straight"),
        (("Qs", "Jh", "7d", "3c", "2s"), "draw2_7", "made_q"),
        (("Qs", "Jh", "8d", "3c", "2s"), "draw2_8", "made_q"),
        (("As", "Kh", "Qd", "Jc", "9s"), "draw3", "made_a"),
        # The ace is high only: A-5-4-3-2 is no straight.
        (("As", "5h", "4d", "3c", "2s"), "draw1_6", "made_a"),
        (("Ks", "Kh", "Kd", "2c", "2s"), "draw3", "full_house_plus"),
    ],
)
def test_examples(cards, predraw_key, postdraw_key) -> None:
    hand = Hand.from_strings(*cards)

    assert predraw_class(hand).key == predraw_key
    assert postdraw_class(hand).key == postdraw_key


def test_random_hands_match_rank_level_classification() -> None:
    rng = random.Random(3)
    deck = [rank + suit for rank in RANKS for suit in SUITS]

    for _ in range(5000):
        hand = Hand.from_strings(*rng.sample(deck, 5))

        ranks = tuple(
            sorted(RANKS.index(card.rank) + 2 for card in hand.cards)
        )
        flush = len({card.suit for card in hand.cards}) == 1

        assert predraw_class(hand).key == predraw_class_key(ranks, flush)
        assert postdraw_class(hand).key == postdraw_class_key(ranks, flush)
