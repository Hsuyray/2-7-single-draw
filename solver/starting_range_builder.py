from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from solver.draw_hand_bucket import (
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.hand import Hand
from solver.hand_abstraction import (
    ExactHandKey,
    exact_hand_key,
)
from solver.hand_universe import (
    iter_starting_hands,
)
from solver.information_state import (
    AbstractionMode,
)
from solver.starting_range import (
    StartingRange,
)


@dataclass(frozen=True)
class StartingRangeBuilder:
    """
    Build starting private-hand ranges
    from raw five-card combinations.

    Supported abstractions:

    exact:
        ExactHandKey

    bucket:
        DrawHandBucket
    """

    abstraction: AbstractionMode

    def build(
        self,
    ) -> StartingRange:
        """
        Build the complete 52-card starting
        range.

        This iterates all 2,598,960 raw
        five-card combinations, so this is
        intended for offline/precompute use.
        """
        return self.build_from_hands(
            iter_starting_hands()
        )

    def build_from_hands(
        self,
        hands: Iterable[Hand],
    ) -> StartingRange:
        """
        Build a starting range from an
        arbitrary collection of raw hands.

        Useful for:

        - unit tests
        - small experiments
        - full-universe precompute
        """
        if self.abstraction == "exact":
            counts: Counter[
                ExactHandKey
            ] = Counter()

            for hand in hands:
                hand_key = exact_hand_key(
                    hand
                )

                counts[
                    hand_key
                ] += 1

            return StartingRange.from_counts(
                dict(counts)
            )

        if self.abstraction == "bucket":
            counts: Counter[
                DrawHandBucket
            ] = Counter()

            for hand in hands:
                hand_key = draw_hand_bucket(
                    hand
                )

                counts[
                    hand_key
                ] += 1

            return StartingRange.from_counts(
                dict(counts)
            )

        raise ValueError(
            "Unknown starting-range abstraction."
        )