"""
2-7 Single Draw hand classes for the product's range grid
(workstream D3). DRAFT v0, awaiting review: see
docs/HAND_TAXONOMY.md. Pure functions; nothing here is used by
training.

Two taxonomies, each placing every 5-card hand in exactly one class:

  predraw_class(hand)   the starting hand, described the way players
                        describe it before the draw: a pat hand by its
                        top two cards, otherwise the draw it offers.
  postdraw_class(hand)  the final hand, by made-hand strength.

Rules follow solver/hand_evaluator.py (docs/game_rules.md is empty):
lowest hand wins, the ace is high only, straights and flushes count
against the hand, 7-5-4-3-2 unsuited is the best hand.

Both classifications depend only on the ranks and on whether the
hand is a flush, which makes exact combination counts cheap
(combination_counts).
"""

from collections import Counter
from dataclasses import dataclass
from itertools import combinations_with_replacement
from math import comb

from solver.hand import Hand
from solver.hand_evaluator import RANK_VALUES


# Highest rank still kept for a draw ("drawing to an 8").
DRAW_KEEP_MAX = 8

# Highest top card that still counts as a pat hand predraw.
PAT_TOP_MAX = 10


@dataclass(frozen=True)
class HandClass:
    key: str
    label: str
    group: str
    # Display order, best first.
    order: int


def _classes(
    rows: list[tuple[str, str, str]],
) -> tuple[HandClass, ...]:
    return tuple(
        HandClass(
            key=key,
            label=label,
            group=group,
            order=order,
        )
        for order, (key, label, group) in enumerate(rows)
    )


PREDRAW_CLASSES = _classes(
    [
        ("pat_75", "7-5 pat", "pat"),
        ("pat_76", "7-6 pat", "pat"),
        ("pat_85", "8-5 pat", "pat"),
        ("pat_86", "8-6 pat", "pat"),
        ("pat_87", "8-7 pat", "pat"),
        ("pat_96", "9-6 or better pat", "pat"),
        ("pat_97", "9-7 pat", "pat"),
        ("pat_98", "9-8 pat", "pat"),
        ("pat_t", "T pat", "pat"),
        ("draw1_6", "1-card draw to a 6 or better", "one_card_draw"),
        ("draw1_7s", "1-card draw to a smooth 7 (7-5 or better)", "one_card_draw"),
        ("draw1_7r", "1-card draw to a rough 7 (7-6)", "one_card_draw"),
        ("draw1_8s", "1-card draw to a smooth 8 (8-5 or better)", "one_card_draw"),
        ("draw1_8r", "1-card draw to a rough 8 (8-6 / 8-7)", "one_card_draw"),
        ("draw2_7", "2-card draw to a 7 or better", "two_card_draw"),
        ("draw2_8", "2-card draw to an 8", "two_card_draw"),
        ("draw3", "3-card draw or worse", "rough_draw"),
    ]
)

POSTDRAW_CLASSES = _classes(
    [
        ("made_75", "7-5", "seven"),
        ("made_76", "7-6", "seven"),
        ("made_85", "8-5", "eight"),
        ("made_86", "8-6", "eight"),
        ("made_87", "8-7", "eight"),
        ("made_96", "9-6 or better", "nine"),
        ("made_97", "9-7", "nine"),
        ("made_98", "9-8", "nine"),
        ("made_t", "T high", "high_card"),
        ("made_j", "J high", "high_card"),
        ("made_q", "Q high", "high_card"),
        ("made_k", "K high", "high_card"),
        ("made_a", "A high", "high_card"),
        ("pair", "One pair", "paired"),
        ("two_pair_trips", "Two pair or trips", "paired"),
        ("straight", "Straight", "straight_flush"),
        ("flush", "Flush", "straight_flush"),
        ("full_house_plus", "Full house or worse", "paired"),
    ]
)

_PREDRAW_BY_KEY = {
    hand_class.key: hand_class
    for hand_class in PREDRAW_CLASSES
}

_POSTDRAW_BY_KEY = {
    hand_class.key: hand_class
    for hand_class in POSTDRAW_CLASSES
}


# ----------------------------------------------------------------
# Rank-level classification
# ----------------------------------------------------------------


def _is_straight(ranks: tuple[int, ...]) -> bool:
    distinct = sorted(set(ranks))

    return (
        len(distinct) == 5
        and distinct[-1] - distinct[0] == 4
    )


def _no_pair_class_key(
    prefix: str,
    top: int,
    second: int,
) -> str:
    """
    Top-two-card cell of a no-pair, non-straight,
    non-flush hand with top card 9 or lower.
    """
    if top == 7:
        return f"{prefix}_75" if second <= 5 else f"{prefix}_76"

    if top == 8:
        if second <= 5:
            return f"{prefix}_85"

        return f"{prefix}_86" if second == 6 else f"{prefix}_87"

    # top == 9
    if second <= 6:
        return f"{prefix}_96"

    return f"{prefix}_97" if second == 7 else f"{prefix}_98"


def postdraw_class_key(
    ranks: tuple[int, ...],
    flush: bool,
) -> str:
    counts = sorted(
        Counter(ranks).values(),
        reverse=True,
    )

    straight = _is_straight(ranks)

    if counts in ([4, 1], [3, 2]) or (straight and flush):
        return "full_house_plus"

    if flush:
        return "flush"

    if straight:
        return "straight"

    if counts in ([3, 1, 1], [2, 2, 1]):
        return "two_pair_trips"

    if counts == [2, 1, 1, 1]:
        return "pair"

    descending = sorted(ranks, reverse=True)
    top, second = descending[0], descending[1]

    # A no-pair hand's top card is at least 7
    # (6-5-4-3-2 is a straight).
    if top <= 9:
        return _no_pair_class_key("made", top, second)

    return {
        10: "made_t",
        11: "made_j",
        12: "made_q",
        13: "made_k",
        14: "made_a",
    }[top]


def predraw_class_key(
    ranks: tuple[int, ...],
    flush: bool,
) -> str:
    distinct = sorted(set(ranks))

    pat = (
        len(distinct) == 5
        and not flush
        and not _is_straight(ranks)
        and distinct[-1] <= PAT_TOP_MAX
    )

    if pat:
        if distinct[-1] == PAT_TOP_MAX:
            return "pat_t"

        return _no_pair_class_key(
            "pat",
            distinct[-1],
            distinct[-2],
        )

    # Not a pat hand: classify by the draw it offers,
    # keeping one card of each rank up to DRAW_KEEP_MAX.
    keep = [
        rank
        for rank in distinct
        if rank <= DRAW_KEEP_MAX
    ]

    if len(keep) >= 4:
        # A 5th low rank only happens for a straight or
        # a flush; the draw keeps the four lowest.
        four = keep[:4]
        top, second = four[-1], four[-2]

        if top <= 6:
            return "draw1_6"

        if top == 7:
            return "draw1_7s" if second <= 5 else "draw1_7r"

        return "draw1_8s" if second <= 5 else "draw1_8r"

    if len(keep) == 3:
        return "draw2_7" if keep[-1] <= 7 else "draw2_8"

    return "draw3"


# ----------------------------------------------------------------
# Hand-level API
# ----------------------------------------------------------------


def _ranks_and_flush(
    hand: Hand,
) -> tuple[tuple[int, ...], bool]:
    if len(hand.cards) != 5:
        raise ValueError(
            "Hand classes need exactly five cards."
        )

    ranks = tuple(
        sorted(
            RANK_VALUES[card.rank]
            for card in hand.cards
        )
    )

    flush = len({card.suit for card in hand.cards}) == 1

    return ranks, flush


def predraw_class(hand: Hand) -> HandClass:
    return _PREDRAW_BY_KEY[
        predraw_class_key(*_ranks_and_flush(hand))
    ]


def postdraw_class(hand: Hand) -> HandClass:
    return _POSTDRAW_BY_KEY[
        postdraw_class_key(*_ranks_and_flush(hand))
    ]


# ----------------------------------------------------------------
# Exact combination counts
# ----------------------------------------------------------------


def rank_patterns():
    """
    Every 5-card rank multiset with its number of suit
    combinations, split into (flush, non-flush).

    Yields (ranks, flush_combos, non_flush_combos).
    """
    for ranks in combinations_with_replacement(range(2, 15), 5):
        counts = Counter(ranks)

        if max(counts.values()) > 4:
            continue

        total = 1

        for count in counts.values():
            total *= comb(4, count)

        flush_combos = 4 if len(counts) == 5 else 0

        yield ranks, flush_combos, total - flush_combos


def combination_counts(kind: str) -> dict[str, int]:
    """
    Exact number of 5-card combinations in each class,
    in display order. kind: "predraw" or "postdraw".
    """
    if kind == "predraw":
        classes, classify = PREDRAW_CLASSES, predraw_class_key
    elif kind == "postdraw":
        classes, classify = POSTDRAW_CLASSES, postdraw_class_key
    else:
        raise ValueError(f"Unknown taxonomy {kind!r}.")

    counts = {
        hand_class.key: 0
        for hand_class in classes
    }

    for ranks, flush_combos, plain_combos in rank_patterns():
        if flush_combos:
            counts[classify(ranks, True)] += flush_combos

        counts[classify(ranks, False)] += plain_combos

    return counts
