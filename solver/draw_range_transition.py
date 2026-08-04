from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from math import comb

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
from solver.hand import (
    Hand,
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


TransitionItems = tuple[
    tuple[
        ExactHandKey,
        float,
    ],
    ...,
]


@dataclass(frozen=True)
class DrawTransitionBudget:
    """
    Protect exact draw enumeration from
    unexpectedly large workloads.

    max_replacement_combinations:
        Maximum replacement combinations
        allowed for one hand/action pair.

    max_hand_action_pairs:
        Maximum number of positive-probability
        hand/action pairs processed by one
        range transition.
    """

    max_replacement_combinations: int = (
        20_000
    )

    max_hand_action_pairs: int = (
        10_000
    )

    def __post_init__(self) -> None:
        if (
            self.max_replacement_combinations
            < 1
        ):
            raise ValueError(
                "Maximum replacement "
                "combinations must be "
                "positive."
            )

        if (
            self.max_hand_action_pairs
            < 1
        ):
            raise ValueError(
                "Maximum hand-action pairs "
                "must be positive."
            )


DEFAULT_DRAW_TRANSITION_BUDGET = (
    DrawTransitionBudget()
)


def transition_exact_draw_range(
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
    normalize: bool = True,
    budget: DrawTransitionBudget = (
        DEFAULT_DRAW_TRANSITION_BUDGET
    ),
) -> dict[
    ExactHandKey,
    float,
]:
    """
    Transition an exact pre-draw range into
    an exact post-draw range.

    For every pre-draw hand:

        pre-draw weight
        × private discard probability
        × replacement-card probability

    Private discard patterns with the same
    public draw count are combined.
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

    post_draw_weights: dict[
        ExactHandKey,
        float,
    ] = {}

    hand_action_pairs = 0

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

        matching_actions = (
            _matching_discard_actions(
                strategy,
                draw_count=(
                    public_draw_count
                ),
            )
        )

        for (
            discard_action,
            action_probability,
        ) in matching_actions:
            if action_probability <= 0:
                continue

            hand_action_pairs += 1

            if (
                hand_action_pairs
                > budget.max_hand_action_pairs
            ):
                raise RuntimeError(
                    "Exact draw transition "
                    "exceeded the configured "
                    "hand-action pair budget."
                )

            action_transition = (
                transition_exact_key(
                    hand_key=hand_key,
                    action=discard_action,
                    budget=budget,
                )
            )

            reach_weight = (
                hand_weight
                * action_probability
            )

            for (
                final_hand_key,
                replacement_probability,
            ) in action_transition.items():
                post_draw_weights[
                    final_hand_key
                ] = (
                    post_draw_weights.get(
                        final_hand_key,
                        0.0,
                    )
                    + reach_weight
                    * replacement_probability
                )

    if normalize:
        return _normalize_weights(
            post_draw_weights
        )

    return post_draw_weights


def transition_exact_key(
    *,
    hand_key: ExactHandKey,
    action: DiscardAction,
    budget: DrawTransitionBudget = (
        DEFAULT_DRAW_TRANSITION_BUDGET
    ),
) -> dict[
    ExactHandKey,
    float,
]:
    """
    Return the cached transition
    distribution for one canonical hand and
    one discard action.

    A dictionary copy is returned so callers
    cannot mutate the cached value.
    """
    replacement_count = (
        replacement_combination_count(
            hand_key=hand_key,
            action=action,
        )
    )

    if (
        replacement_count
        > budget.max_replacement_combinations
    ):
        raise RuntimeError(
            "Exact draw transition requires "
            f"{replacement_count} replacement "
            "combinations, exceeding the "
            "configured budget of "
            f"{budget.max_replacement_combinations}."
        )

    return dict(
        _cached_transition_exact_key(
            hand_key,
            action,
        )
    )


def transition_exact_hand(
    *,
    hand: Hand,
    action: DiscardAction,
    budget: DrawTransitionBudget = (
        DEFAULT_DRAW_TRANSITION_BUDGET
    ),
) -> dict[
    ExactHandKey,
    float,
]:
    """
    Return the probability distribution of
    exact post-draw hand keys for one hand
    and one private discard action.

    Suit-isomorphic hands share the same
    cached transition through ExactHandKey.
    """
    return transition_exact_key(
        hand_key=exact_hand_key(
            hand
        ),
        action=action,
        budget=budget,
    )


def replacement_combination_count(
    *,
    hand_key: ExactHandKey,
    action: DiscardAction,
) -> int:
    """
    Return the number of replacement-card
    combinations required by one exact draw.

    A five-card hand leaves 47 unknown cards:

        Draw 0: C(47, 0) = 1
        Draw 1: C(47, 1) = 47
        Draw 2: C(47, 2) = 1,081
        Draw 3: C(47, 3) = 16,215
    """
    hand = exact_hand_from_key(
        hand_key
    )

    action.validate_for_hand_size(
        len(hand.cards)
    )

    available_count = (
        len(FULL_DECK)
        - len(hand.cards)
    )

    return comb(
        available_count,
        action.draw_count,
    )


@lru_cache(
    maxsize=100_000
)
def _cached_transition_exact_key(
    hand_key: ExactHandKey,
    action: DiscardAction,
) -> TransitionItems:
    """
    Compute and cache one immutable exact
    draw transition.
    """
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

    draw_count = (
        action.draw_count
    )

    available_cards = tuple(
        card
        for card in FULL_DECK
        if card not in hand.cards
    )

    replacement_count = comb(
        len(available_cards),
        draw_count,
    )

    if replacement_count <= 0:
        raise RuntimeError(
            "No legal replacement-card "
            "combinations are available."
        )

    probability_per_combination = (
        1.0
        / replacement_count
    )

    result: dict[
        ExactHandKey,
        float,
    ] = {}

    for replacement_cards in combinations(
        available_cards,
        draw_count,
    ):
        final_hand = (
            partial_hand.complete(
                list(
                    replacement_cards
                )
            )
        )

        final_key = exact_hand_key(
            final_hand
        )

        result[final_key] = (
            result.get(
                final_key,
                0.0,
            )
            + probability_per_combination
        )

    return tuple(
        sorted(
            result.items(),
            key=lambda item: (
                item[0].cards
            ),
        )
    )


def draw_transition_cache_info():
    """
    Return cache hit, miss, size, and limit
    diagnostics.
    """
    return (
        _cached_transition_exact_key
        .cache_info()
    )


def clear_draw_transition_cache() -> None:
    """
    Clear every cached exact draw
    transition.
    """
    _cached_transition_exact_key.cache_clear()


def _matching_discard_actions(
    strategy: Strategy,
    *,
    draw_count: int,
) -> tuple[
    tuple[
        DiscardAction,
        float,
    ],
    ...,
]:
    matching: list[
        tuple[
            DiscardAction,
            float,
        ]
    ] = []

    for (
        action,
        probability,
    ) in strategy.items():
        if probability < 0:
            raise ValueError(
                "Strategy probabilities "
                "cannot be negative."
            )

        if not isinstance(
            action,
            DiscardAction,
        ):
            continue

        if (
            action.draw_count
            != draw_count
        ):
            continue

        matching.append(
            (
                action,
                probability,
            )
        )

    return tuple(
        matching
    )


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
            weight
            / total_weight
        )
        for hand_key, weight
        in weights.items()
    }