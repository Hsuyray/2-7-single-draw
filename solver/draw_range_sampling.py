from dataclasses import dataclass
import random

from solver.actions import (
    DiscardAction,
)
from solver.cards import (
    Card,
    RANKS,
    SUITS,
)
from solver.exact_hand_codec import (
    exact_hand_from_key,
)
from solver.hand_abstraction import (
    ExactHandKey,
    exact_hand_key,
)
from solver.information_state import (
    PrivateHandKey,
)
from solver.strategy_index import (
    Strategy,
)


FULL_DECK = tuple(
    Card(
        rank=rank,
        suit=suit,
    )
    for rank in RANKS
    for suit in SUITS
)


@dataclass(frozen=True)
class DrawSamplingConfig:
    """
    Monte Carlo configuration for
    approximate draw-range transitions.
    """

    samples_per_hand_action: int = 1_000
    seed: int | None = None

    def __post_init__(self) -> None:
        if (
            self.samples_per_hand_action
            < 1
        ):
            raise ValueError(
                "Samples per hand-action "
                "must be positive."
            )


def sample_exact_draw_range(
    *,
    pre_draw_weights: dict[
        ExactHandKey,
        float,
    ],
    strategies: dict[
        PrivateHandKey,
        Strategy,
    ],
    public_draw_count: int,
    config: DrawSamplingConfig = (
        DrawSamplingConfig()
    ),
    normalize: bool = True,
) -> dict[
    ExactHandKey,
    float,
]:
    """
    Approximate an exact post-draw range
    using Monte Carlo replacement sampling.

    For each positive-probability private
    discard action:

        hand weight
        × action probability
        × sampled replacement frequency
    """
    if not (
        0
        <= public_draw_count
        <= 5
    ):
        raise ValueError(
            "Public draw count must be "
            "between zero and five."
        )

    if any(
        weight < 0
        for weight
        in pre_draw_weights.values()
    ):
        raise ValueError(
            "Pre-draw range weights cannot "
            "be negative."
        )

    random_generator = random.Random(
        config.seed
    )

    result: dict[
        ExactHandKey,
        float,
    ] = {}

    for (
        hand_key,
        hand_weight,
    ) in pre_draw_weights.items():
        if hand_weight <= 0:
            continue

        strategy = strategies.get(
            hand_key
        )

        if strategy is None:
            continue

        for (
            action,
            action_probability,
        ) in strategy.items():
            if action_probability < 0:
                raise ValueError(
                    "Strategy probabilities "
                    "cannot be negative."
                )

            if action_probability <= 0:
                continue

            if not isinstance(
                action,
                DiscardAction,
            ):
                continue

            if (
                action.draw_count
                != public_draw_count
            ):
                continue

            sampled_transition = (
                sample_exact_hand_transition(
                    hand_key=hand_key,
                    action=action,
                    sample_count=(
                        config
                        .samples_per_hand_action
                    ),
                    random_generator=(
                        random_generator
                    ),
                )
            )

            reach_weight = (
                hand_weight
                * action_probability
            )

            for (
                final_key,
                probability,
            ) in sampled_transition.items():
                result[final_key] = (
                    result.get(
                        final_key,
                        0.0,
                    )
                    + reach_weight
                    * probability
                )

    if normalize:
        return _normalize_weights(
            result
        )

    return result


def sample_exact_hand_transition(
    *,
    hand_key: ExactHandKey,
    action: DiscardAction,
    sample_count: int,
    random_generator: (
        random.Random
        | None
    ) = None,
) -> dict[
    ExactHandKey,
    float,
]:
    """
    Approximate one hand/action transition.

    Sampling is performed without replacement
    inside each individual draw, matching the
    physical draw process.
    """
    if sample_count < 1:
        raise ValueError(
            "Sample count must be positive."
        )

    generator = (
        random_generator
        if random_generator is not None
        else random.Random()
    )

    hand = exact_hand_from_key(
        hand_key
    )

    action.validate_for_hand_size(
        len(hand.cards)
    )

    partial_hand, _ = hand.discard(
        list(
            action.discard_indices
        )
    )

    available_cards = tuple(
        card
        for card in FULL_DECK
        if card not in hand.cards
    )

    draw_count = action.draw_count

    if draw_count == 0:
        return {
            hand_key: 1.0,
        }

    counts: dict[
        ExactHandKey,
        int,
    ] = {}

    for _ in range(
        sample_count
    ):
        replacement_cards = (
            generator.sample(
                available_cards,
                draw_count,
            )
        )

        final_hand = (
            partial_hand.complete(
                replacement_cards
            )
        )

        final_key = exact_hand_key(
            final_hand
        )

        counts[final_key] = (
            counts.get(
                final_key,
                0,
            )
            + 1
        )

    return {
        final_key: (
            count / sample_count
        )
        for final_key, count
        in counts.items()
    }


def _normalize_weights(
    weights: dict[
        ExactHandKey,
        float,
    ],
) -> dict[
    ExactHandKey,
    float,
]:
    total_weight = sum(
        weights.values()
    )

    if total_weight <= 0:
        return dict(
            weights
        )

    return {
        hand_key: (
            weight / total_weight
        )
        for hand_key, weight
        in weights.items()
    }