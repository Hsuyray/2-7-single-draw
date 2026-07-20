from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def terminal_utilities(
    game: SingleDrawGame,
) -> tuple[float, ...]:
    if game.phase != GamePhase.COMPLETE:
        raise ValueError(
            "Terminal utilities are only available "
            "after the game is complete."
        )

    utilities = tuple(
        player.stack
        - _starting_stack_for_seat(
            game,
            player.seat,
        )
        for player in game.betting_state.players
    )

    if abs(sum(utilities)) > 1e-9:
        raise RuntimeError(
            "Terminal utilities do not sum to zero."
        )

    return utilities


def terminal_utility(
    game: SingleDrawGame,
    *,
    seat: int,
) -> float:
    if not (
        0 <= seat < game.config.player_count
    ):
        raise ValueError(
            "Seat is outside the game."
        )

    return terminal_utilities(game)[seat]


def _starting_stack_for_seat(
    game: SingleDrawGame,
    seat: int,
) -> float:
    starting_stacks = game.config.starting_stacks

    if starting_stacks is not None:
        return starting_stacks[seat]

    return game.config.starting_stack