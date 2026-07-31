from dataclasses import dataclass


DEFAULT_POT_FRACTIONS = (
    0.20,
    0.33,
    0.50,
    0.66,
    0.90,
    1.00,
    1.25,
)


@dataclass(frozen=True)
class BetSizingPolicy:
    """
    Discrete bet/raise sizing abstraction.

    Fractions represent pot fractions.

    Examples when there is no bet to call:

        pot = 10
        50% pot -> bet 5
        100% pot -> bet 10

    When facing a bet, fractions are measured
    against the pot after calling.

    The resulting values are absolute
    raise-to amounts for the current betting
    round.
    """

    pot_fractions: tuple[
        float,
        ...,
    ] = DEFAULT_POT_FRACTIONS

    include_all_in: bool = True

    all_in_threshold: float = 0.90

    chip_increment: float = 0.1

    def __post_init__(self) -> None:
        if not self.pot_fractions:
            raise ValueError(
                "At least one pot fraction "
                "is required."
            )

        if any(
            fraction <= 0
            for fraction
            in self.pot_fractions
        ):
            raise ValueError(
                "Pot fractions must be "
                "positive."
            )

        if not (
            0 < self.all_in_threshold <= 1
        ):
            raise ValueError(
                "All-in threshold must be "
                "between 0 and 1."
            )

        if self.chip_increment <= 0:
            raise ValueError(
                "Chip increment must be "
                "positive."
            )

    def raise_to_candidates(
        self,
        *,
        pot: float,
        committed_this_round: float,
        stack: float,
        amount_to_call: float,
        minimum_raise_to: float,
        maximum_raise_to: float,
    ) -> tuple[float, ...]:
        """
        Generate legal discrete raise-to sizes.

        Parameters:

        pot:
            Current pot before this player acts.

        committed_this_round:
            Amount already committed by the
            acting player this betting round.

        stack:
            Remaining stack of acting player.

        amount_to_call:
            Amount required to call.

        minimum_raise_to:
            Minimum legal absolute raise-to.

        maximum_raise_to:
            Maximum legal absolute raise-to,
            normally committed_this_round
            plus remaining stack.

        Returns absolute raise-to amounts.
        """
        if pot < 0:
            raise ValueError(
                "Pot cannot be negative."
            )

        if committed_this_round < 0:
            raise ValueError(
                "Committed amount cannot "
                "be negative."
            )

        if stack < 0:
            raise ValueError(
                "Stack cannot be negative."
            )

        if amount_to_call < 0:
            raise ValueError(
                "Amount to call cannot "
                "be negative."
            )

        if (
            maximum_raise_to
            < committed_this_round
        ):
            raise ValueError(
                "Maximum raise-to cannot "
                "be below current commitment."
            )

        if stack <= 0:
            return ()

        if (
            maximum_raise_to
            <= committed_this_round
            + amount_to_call
        ):
            return ()

        raw_candidates: list[
            float
        ] = []

        for fraction in self.pot_fractions:
            raise_to = (
                self._fraction_to_raise_to(
                    fraction=fraction,
                    pot=pot,
                    committed_this_round=(
                        committed_this_round
                    ),
                    amount_to_call=(
                        amount_to_call
                    ),
                )
            )

            raw_candidates.append(
                raise_to
            )

        candidates: set[
            float
        ] = set()

        all_in_raise_to = self._round_chip(
            maximum_raise_to
        )

        for raw_raise_to in raw_candidates:
            raise_to = self._round_chip(
                raw_raise_to
            )

            if (
                raise_to
                < minimum_raise_to
            ):
                continue

            if (
                raise_to
                > maximum_raise_to
            ):
                continue

            additional_chips = (
                raise_to
                - committed_this_round
            )

            if (
                self.include_all_in
                and stack > 0
                and (
                    additional_chips
                    / stack
                )
                >= self.all_in_threshold
            ):
                candidates.add(
                    all_in_raise_to
                )

                continue

            candidates.add(
                raise_to
            )

        if (
            self.include_all_in
            and maximum_raise_to
            >= minimum_raise_to
        ):
            candidates.add(
                all_in_raise_to
            )

        return tuple(
            sorted(
                candidates
            )
        )

    def _fraction_to_raise_to(
        self,
        *,
        fraction: float,
        pot: float,
        committed_this_round: float,
        amount_to_call: float,
    ) -> float:
        """
        Convert a pot fraction into an
        absolute raise-to amount.

        No bet facing us:

            raise_to
            =
            committed
            + fraction * pot

        Facing a bet:

            first call

            pot_after_call
            =
            pot + amount_to_call

            raise amount beyond call
            =
            fraction * pot_after_call

            raise_to
            =
            committed
            + amount_to_call
            + fraction * pot_after_call
        """
        pot_after_call = (
            pot
            + amount_to_call
        )

        return (
            committed_this_round
            + amount_to_call
            + fraction
            * pot_after_call
        )

    def _round_chip(
        self,
        value: float,
    ) -> float:
        units = round(
            value
            / self.chip_increment
        )

        return round(
            units
            * self.chip_increment,
            10,
        )