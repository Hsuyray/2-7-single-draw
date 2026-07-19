from itertools import combinations

from solver.actions import DiscardAction


def generate_discard_actions(
    *,
    hand_size: int = 5,
    max_draw: int = 3,
) -> tuple[DiscardAction, ...]:
    if hand_size < 0:
        raise ValueError(
            "Hand size cannot be negative."
        )

    if max_draw < 0:
        raise ValueError(
            "Maximum draw cannot be negative."
        )

    if max_draw > hand_size:
        raise ValueError(
            "Maximum draw cannot exceed hand size."
        )

    actions: list[DiscardAction] = []

    for draw_count in range(max_draw + 1):
        for discard_indices in combinations(
            range(hand_size),
            draw_count,
        ):
            actions.append(
                DiscardAction(discard_indices)
            )

    return tuple(actions)