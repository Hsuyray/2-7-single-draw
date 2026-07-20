from dataclasses import dataclass

from solver.game_state import GameConfig
from solver.single_draw_game import SingleDrawGame


@dataclass
class TrainingGameFactory:
    config: GameConfig
    button_seat: int = 0
    initial_seed: int = 0
    alternate_button: bool = False
    games_created: int = 0

    def __call__(self) -> SingleDrawGame:
        seed = self.initial_seed + self.games_created

        button_seat = self.button_seat

        if self.alternate_button:
            button_seat = (
                self.button_seat
                + self.games_created
            ) % self.config.player_count

        game = SingleDrawGame(
            config=self.config,
            button_seat=button_seat,
            shuffle_deck=True,
            deck_seed=seed,
        )

        self.games_created += 1

        return game