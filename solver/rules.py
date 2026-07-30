from solver.game_state import GameConfig


SMALL_BLIND = 1.0
BIG_BLIND = 2.0
BIG_BLIND_ANTE = 1.5

MIN_PLAYER_COUNT = 2
MAX_PLAYER_COUNT = 6


def make_game_config(
    *,
    player_count: int,
    effective_stack: float,
) -> GameConfig:
    """
    Build the standard 2-7 Single Draw
    configuration used by the solver.

    The blind structure is fixed:

    SB  = 1
    BB  = 2
    BBA = 1.5

    The solver user controls only:
    - player count
    - effective stack
    """
    if not (
        MIN_PLAYER_COUNT
        <= player_count
        <= MAX_PLAYER_COUNT
    ):
        raise ValueError(
            "Player count must be between "
            "2 and 6."
        )

    if effective_stack <= 0:
        raise ValueError(
            "Effective stack must be positive."
        )

    return GameConfig(
        player_count=player_count,
        starting_stack=effective_stack,
        small_blind=SMALL_BLIND,
        big_blind=BIG_BLIND,
        big_blind_ante=BIG_BLIND_ANTE,
    )