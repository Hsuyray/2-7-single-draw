from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class DiscardAction:
    discard_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(set(self.discard_indices)) != len(
            self.discard_indices
        ):
            raise ValueError(
                "Discard indices cannot contain duplicates."
            )

        if any(
            index < 0
            for index in self.discard_indices
        ):
            raise ValueError(
                "Discard indices cannot be negative."
            )

        if tuple(sorted(self.discard_indices)) != (
            self.discard_indices
        ):
            raise ValueError(
                "Discard indices must be sorted."
            )

    @property
    def draw_count(self) -> int:
        return len(self.discard_indices)

    @property
    def is_stand_pat(self) -> bool:
        return self.draw_count == 0

    def keep_indices(
        self,
        *,
        hand_size: int = 5,
    ) -> tuple[int, ...]:
        self.validate_for_hand_size(hand_size)

        discarded = set(self.discard_indices)

        return tuple(
            index
            for index in range(hand_size)
            if index not in discarded
        )

    def to_mask(
        self,
        *,
        hand_size: int = 5,
    ) -> int:
        self.validate_for_hand_size(hand_size)

        mask = 0

        for index in self.discard_indices:
            mask |= 1 << index

        return mask

    def validate_for_hand_size(
        self,
        hand_size: int,
    ) -> None:
        if hand_size < 0:
            raise ValueError(
                "Hand size cannot be negative."
            )

        if any(
            index >= hand_size
            for index in self.discard_indices
        ):
            raise ValueError(
                "Discard index is outside the hand."
            )

    @classmethod
    def from_mask(
        cls,
        mask: int,
        *,
        hand_size: int = 5,
    ) -> "DiscardAction":
        if hand_size < 0:
            raise ValueError(
                "Hand size cannot be negative."
            )

        if mask < 0:
            raise ValueError(
                "Discard mask cannot be negative."
            )

        if mask >= (1 << hand_size):
            raise ValueError(
                "Discard mask contains an index "
                "outside the hand."
            )

        discard_indices = tuple(
            index
            for index in range(hand_size)
            if mask & (1 << index)
        )

        return cls(discard_indices)