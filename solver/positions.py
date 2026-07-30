from enum import Enum


class Position(str, Enum):
    BUTTON_SMALL_BLIND = "BTN/SB"
    BUTTON = "BTN"
    SMALL_BLIND = "SB"
    BIG_BLIND = "BB"
    UNDER_THE_GUN = "UTG"
    HIJACK = "HJ"
    CUTOFF = "CO"


POSITION_LAYOUTS: dict[
    int,
    tuple[Position, ...],
] = {
    2: (
        Position.BUTTON_SMALL_BLIND,
        Position.BIG_BLIND,
    ),
    3: (
        Position.BUTTON,
        Position.SMALL_BLIND,
        Position.BIG_BLIND,
    ),
    4: (
        Position.BUTTON,
        Position.SMALL_BLIND,
        Position.BIG_BLIND,
        Position.CUTOFF,
    ),
    5: (
        Position.BUTTON,
        Position.SMALL_BLIND,
        Position.BIG_BLIND,
        Position.HIJACK,
        Position.CUTOFF,
    ),
    6: (
        Position.BUTTON,
        Position.SMALL_BLIND,
        Position.BIG_BLIND,
        Position.UNDER_THE_GUN,
        Position.HIJACK,
        Position.CUTOFF,
    ),
}


def position_for_seat(
    *,
    player_count: int,
    button_seat: int,
    seat: int,
) -> Position:
    _validate_table(
        player_count=player_count,
        button_seat=button_seat,
    )

    if not 0 <= seat < player_count:
        raise ValueError(
            "Seat is outside the table."
        )

    layout = POSITION_LAYOUTS[
        player_count
    ]

    offset = (
        seat - button_seat
    ) % player_count

    return layout[offset]


def seat_for_position(
    *,
    player_count: int,
    button_seat: int,
    position: Position,
) -> int:
    _validate_table(
        player_count=player_count,
        button_seat=button_seat,
    )

    layout = POSITION_LAYOUTS[
        player_count
    ]

    if position not in layout:
        raise ValueError(
            f"{position.value} is not used "
            f"at a {player_count}-player table."
        )

    offset = layout.index(position)

    return (
        button_seat + offset
    ) % player_count


def positions_by_seat(
    *,
    player_count: int,
    button_seat: int,
) -> tuple[Position, ...]:
    _validate_table(
        player_count=player_count,
        button_seat=button_seat,
    )

    return tuple(
        position_for_seat(
            player_count=player_count,
            button_seat=button_seat,
            seat=seat,
        )
        for seat in range(player_count)
    )


def _validate_table(
    *,
    player_count: int,
    button_seat: int,
) -> None:
    if player_count not in POSITION_LAYOUTS:
        raise ValueError(
            "Player count must be between "
            "2 and 6."
        )

    if not (
        0 <= button_seat < player_count
    ):
        raise ValueError(
            "Button seat is outside "
            "the table."
        )