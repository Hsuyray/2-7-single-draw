"""
B2: sanity tests for scripts/inspect_draw_equity.py.
"""

import random

import pytest

from scripts.inspect_draw_equity import (
    DECK,
    OPTIONS,
    assign_suits,
    card_text,
    equity,
    option_equities,
    score,
)
from solver.actions import (
    DiscardAction,
)
from solver.hand import (
    Hand,
)
from solver.made_hand_bucket import (
    made_hand_bucket,
)


def test_cached_score_matches_evaluator() -> None:
    rng = random.Random(5)

    for _ in range(3000):
        cards = rng.sample(DECK, 5)

        assert score(cards) == made_hand_bucket(
            Hand.from_strings(
                *(card_text(card) for card in cards)
            )
        ).score

    # Flushes and straights explicitly.
    flush = [(7, 0), (5, 0), (4, 0), (3, 0), (2, 0)]
    rainbow = assign_suits((7, 5, 4, 3, 2))

    assert score(flush) > score(rainbow)

    straight = assign_suits((6, 5, 4, 3, 2))
    assert score(straight) > score(
        assign_suits((13, 9, 8, 7, 6))
    )


def test_pat_against_pat_is_exact() -> None:
    hero = assign_suits((7, 5, 4, 3, 2))
    opponent = assign_suits(
        (9, 7, 6, 4, 2),
        avoid=frozenset(hero),
    )

    dead = set(hero) | set(opponent)

    assert equity(
        hero,
        0,
        ("pat", opponent),
        dead,
        random.Random(0),
    ) == 1.0

    same = assign_suits(
        (7, 5, 4, 3, 2),
        avoid=frozenset(hero),
    )

    assert equity(
        hero,
        0,
        ("pat", same),
        set(hero) | set(same),
        random.Random(0),
    ) == 0.5


def test_made_eight_should_pat_against_a_one_card_draw() -> None:
    # The example from the B2 discussion (day57): 8-6-5-4-3
    # stands pat against an opponent drawing one to 7-5-3-2.
    hero = assign_suits((3, 4, 5, 6, 8))

    equities = option_equities(
        hero,
        "opp_draw1_7532",
        random.Random(1),
    )

    best = max(
        OPTIONS,
        key=lambda option: equities[option],
    )

    assert best == DiscardAction(())
    assert equities[DiscardAction(())] == pytest.approx(
        0.860,
        abs=0.002,
    )


def test_option_equities_are_deterministic() -> None:
    hero = assign_suits((2, 4, 5, 9, 13))

    first = option_equities(
        hero,
        "opp_draw1_8642",
        random.Random("x"),
    )

    second = option_equities(
        hero,
        "opp_draw1_8642",
        random.Random("x"),
    )

    assert first == second
    assert len(first) == 16
