from dataclasses import dataclass

from solver.hand import Hand


@dataclass(frozen=True)
class MadeHandBucket:
    score: tuple[int, ...]


def made_hand_bucket(
    hand: Hand,
) -> MadeHandBucket:
    """
    Exact post-draw hand-strength representation.

    The evaluator already returns a canonical,
    comparable 2-7 lowball score where lower
    tuples represent stronger hands.

    For strategy-quality validation, keep the
    complete score rather than compressing
    kickers.
    """
    score = hand.score

    if not score:
        raise ValueError(
            "Hand score cannot be empty."
        )

    return MadeHandBucket(
        score=score,
    )