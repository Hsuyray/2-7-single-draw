from dataclasses import dataclass

from solver.hand import Hand


@dataclass(frozen=True)
class MadeHandBucket:
    category: int
    primary_strength: int
    secondary_strength: int


def made_hand_bucket(
    hand: Hand,
) -> MadeHandBucket:
    """
    Post-draw hand abstraction for 2-7 Single Draw.

    Lower hand.score values are better.

    Instead of keeping an arbitrary score prefix,
    we compress the score into three strategically
    meaningful components:

    - category:
        made-hand class from the evaluator
    - primary_strength:
        the most important rank within that category
    - secondary_strength:
        a coarser secondary rank component
    """
    score = hand.score

    if not score:
        raise ValueError(
            "Hand score cannot be empty."
        )

    category = score[0]

    primary_strength = (
        score[1]
        if len(score) > 1
        else 0
    )

    secondary_raw = (
        score[2]
        if len(score) > 2
        else 0
    )

    secondary_strength = (
        _secondary_bucket(
            secondary_raw
        )
    )

    return MadeHandBucket(
        category=category,
        primary_strength=primary_strength,
        secondary_strength=secondary_strength,
    )


def _secondary_bucket(
    value: int,
) -> int:
    """
    Coarsen secondary kickers / ranks.

    2-4   -> 0
    5-7   -> 1
    8-9   -> 2
    T-J   -> 3
    Q-K-A -> 4
    """
    if value <= 4:
        return 0

    if value <= 7:
        return 1

    if value <= 9:
        return 2

    if value <= 11:
        return 3

    return 4