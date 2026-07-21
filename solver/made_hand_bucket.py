from dataclasses import dataclass

from solver.hand import Hand


@dataclass(frozen=True)
class MadeHandBucket:
    score_prefix: tuple[int, ...]


def made_hand_bucket(
    hand: Hand,
    *,
    score_depth: int = 3,
) -> MadeHandBucket:
    if score_depth <= 0:
        raise ValueError(
            "Score depth must be positive."
        )

    return MadeHandBucket(
        score_prefix=hand.score[:score_depth],
    )