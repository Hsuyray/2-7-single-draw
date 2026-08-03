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
class BetSize:
    """
    One discrete betting abstraction size.

    raise_to:
        Absolute amount committed during
        the current betting round after
        taking this action.

    pot_fraction:
        Abstract pot fraction that produced
        this size.

        None means the action is a dedicated
        all-in size rather than a normal
        pot-fraction size.

    is_all_in:
        Whether this size commits the
        player's entire remaining stack.
    """

    raise_to: float
    pot_fraction: float | None
    is_all_in: bool

    def __post_init__(self) -> None:
        if self.raise_to < 0:
            raise ValueError(
                "Raise-to amount cannot "
                "be negative."
            )

        if (
            self.pot_fraction is not None
            and self.pot_fraction <= 0
        ):
            raise ValueError(
                "Pot fraction must be "
                "positive."
            )

        if (
            self.is_all_in
            and self.pot_fraction is not None
        ):
            raise ValueError(
                "Dedicated all-in sizes cannot "
                "also have a pot fraction."
            )

    @property
    def label(self) -> str:
        if self.is_all_in:
            return "All-in"

        if self.pot_fraction is None:
            return (
                f"Raise to {self.raise_to:g}"
            )

        percentage = (
            self.pot_fraction
            * 100
        )

        if percentage.is_integer():
            formatted_percentage = str(
                int(percentage)
            )
        else:
            formatted_percentage = (
                f"{percentage:g}"
            )

        return (
            f"{formatted_percentage}% Pot"
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

    def bet_size_candidates(
        self,
        *,
        pot: float,
        committed_this_round: float,
        stack: float,
        amount_to_call: float,
        minimum_raise_to: float,
        maximum_raise_to: float,
    ) -> tuple[BetSize, ...]:
        """
        Generate discrete betting sizes with
        metadata for solver and UI use.

        Returned sizes contain:

            raise_to
            pot_fraction
            is_all_in
            label

        Sizes are sorted by raise_to.
        """
        self._validate_candidate_inputs(
            pot=pot,
            committed_this_round=(
                committed_this_round
            ),
            stack=stack,
            amount_to_call=(
                amount_to_call
            ),
            maximum_raise_to=(
                maximum_raise_to
            ),
        )

        if stack <= 0:
            return ()

        call_total = (
            committed_this_round
            + amount_to_call
        )

        if maximum_raise_to <= call_total:
            return ()

        all_in_raise_to = self._round_chip(
            maximum_raise_to
        )

        candidates_by_raise_to: dict[
            float,
            BetSize,
        ] = {}

        for fraction in self.pot_fractions:
            raw_raise_to = (
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

            raise_to = self._round_chip(
                raw_raise_to
            )

            if raise_to < minimum_raise_to:
                continue

            if raise_to > maximum_raise_to:
                continue

            additional_chips = (
                raise_to
                - committed_this_round
            )

            reaches_all_in_threshold = (
                self.include_all_in
                and stack > 0
                and (
                    additional_chips
                    / stack
                )
                >= self.all_in_threshold
            )

            if reaches_all_in_threshold:
                candidates_by_raise_to[
                    all_in_raise_to
                ] = BetSize(
                    raise_to=(
                        all_in_raise_to
                    ),
                    pot_fraction=None,
                    is_all_in=True,
                )

                continue

            if (
                raise_to
                not in candidates_by_raise_to
            ):
                candidates_by_raise_to[
                    raise_to
                ] = BetSize(
                    raise_to=raise_to,
                    pot_fraction=fraction,
                    is_all_in=False,
                )

        if (
            self.include_all_in
            and maximum_raise_to
            >= minimum_raise_to
        ):
            candidates_by_raise_to[
                all_in_raise_to
            ] = BetSize(
                raise_to=all_in_raise_to,
                pot_fraction=None,
                is_all_in=True,
            )

        return tuple(
            sorted(
                candidates_by_raise_to.values(),
                key=lambda size: size.raise_to,
            )
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
        Backward-compatible API.

        Return only absolute raise-to values.

        Existing CFR and legal-action code can
        continue using this method while UI
        and strategy presentation code can use
        bet_size_candidates().
        """
        sizes = self.bet_size_candidates(
            pot=pot,
            committed_this_round=(
                committed_this_round
            ),
            stack=stack,
            amount_to_call=(
                amount_to_call
            ),
            minimum_raise_to=(
                minimum_raise_to
            ),
            maximum_raise_to=(
                maximum_raise_to
            ),
        )

        return tuple(
            size.raise_to
            for size in sizes
        )

    def _validate_candidate_inputs(
        self,
        *,
        pot: float,
        committed_this_round: float,
        stack: float,
        amount_to_call: float,
        maximum_raise_to: float,
    ) -> None:
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

            pot_after_call
            =
            pot + amount_to_call

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