BB_SCALE = 10


def bb_to_units(amount_bb: float) -> int:
    if amount_bb < 0:
        raise ValueError("BB amount cannot be negative.")

    return round(amount_bb * BB_SCALE)


def units_to_bb(units: int) -> float:
    if not isinstance(units, int):
        raise TypeError("Units must be an integer.")

    return units / BB_SCALE


def split_units(
    total_units: int,
    winner_seats: tuple[int, ...],
) -> dict[int, int]:
    if total_units < 0:
        raise ValueError("Total units cannot be negative.")

    if not winner_seats:
        raise ValueError("At least one winner is required.")

    if len(set(winner_seats)) != len(winner_seats):
        raise ValueError(
            "Winner seats cannot contain duplicates."
        )

    base_share, remainder = divmod(
        total_units,
        len(winner_seats),
    )

    payouts: dict[int, int] = {}

    for index, seat in enumerate(sorted(winner_seats)):
        payouts[seat] = base_share

        if index < remainder:
            payouts[seat] += 1

    return payouts