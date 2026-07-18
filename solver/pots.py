from dataclasses import dataclass


@dataclass(frozen=True)
class Pot:
    amount: float
    eligible_seats: tuple[int, ...]


def build_pots(
    commitments: list[float],
    folded_seats: set[int] | None = None,
) -> list[Pot]:
    """
    Build the main pot and side pots from each player's total commitment.

    Folded players' chips remain in the pots, but folded players are not
    eligible to win.
    """

    if not commitments:
        raise ValueError("At least one commitment is required.")

    if any(amount < 0 for amount in commitments):
        raise ValueError("Commitments cannot be negative.")

    folded = folded_seats or set()
    player_count = len(commitments)

    if any(seat < 0 or seat >= player_count for seat in folded):
        raise ValueError("Folded seat is outside the table.")

    contribution_levels = sorted(
        {
            amount
            for amount in commitments
            if amount > 0
        }
    )

    pots: list[Pot] = []
    previous_level = 0.0

    for level in contribution_levels:
        contributing_seats = [
            seat
            for seat, commitment in enumerate(commitments)
            if commitment >= level
        ]

        layer_size = level - previous_level
        amount = layer_size * len(contributing_seats)

        eligible_seats = tuple(
            seat
            for seat in contributing_seats
            if seat not in folded
        )

        if amount > 0:
            pots.append(
                Pot(
                    amount=amount,
                    eligible_seats=eligible_seats,
                )
            )

        previous_level = level

    return pots