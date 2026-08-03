from solver.bet_sizing import (
    BetSizingPolicy,
)


FAST_BET_SIZING = BetSizingPolicy(
    pot_fractions=(
        0.33,
        0.66,
        1.00,
    ),
    include_all_in=True,
    all_in_threshold=0.90,
    chip_increment=0.1,
)


FULL_BET_SIZING = BetSizingPolicy(
    pot_fractions=(
        0.20,
        0.33,
        0.50,
        0.66,
        0.90,
        1.00,
        1.25,
    ),
    include_all_in=True,
    all_in_threshold=0.90,
    chip_increment=0.1,
)