from dataclasses import dataclass


@dataclass(frozen=True)
class PublicAction:
    phase: str
    seat: int
    action_type: str
    amount: float | None = None
    draw_count: int | None = None

    def __post_init__(self) -> None:
        if self.seat < 0:
            raise ValueError(
                "Action seat cannot be negative."
            )

        if not self.phase:
            raise ValueError(
                "Action phase cannot be empty."
            )

        if not self.action_type:
            raise ValueError(
                "Action type cannot be empty."
            )

        if self.amount is not None and self.amount < 0:
            raise ValueError(
                "Action amount cannot be negative."
            )

        if (
            self.draw_count is not None
            and self.draw_count < 0
        ):
            raise ValueError(
                "Draw count cannot be negative."
            )

        if (
            self.action_type == "draw"
            and self.draw_count is None
        ):
            raise ValueError(
                "Draw actions must include draw count."
            )

        if (
            self.action_type != "draw"
            and self.draw_count is not None
        ):
            raise ValueError(
                "Only draw actions may include draw count."
            )