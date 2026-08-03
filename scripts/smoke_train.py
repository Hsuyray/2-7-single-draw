from solver.bet_sizing_profiles import (
    FAST_BET_SIZING,
)
from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.legal_actions import (
    BettingAction,
)
from solver.training_factory import (
    TrainingGameFactory,
)


def main() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=10.0,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    game_factory = TrainingGameFactory(
        config=config,
        button_seat=0,
        initial_seed=42,
        alternate_button=True,
    )

    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=None,
        bet_sizing_policy=(
            FAST_BET_SIZING
        ),
        traversal_mode=(
            "external_sampling"
        ),
        abstraction="bucket",
        draw_action_mode="candidate",
        random_seed=42,
    )

    trainer.train(
        game_factory,
        iterations=1,
    )

    strategies = (
        trainer.average_strategies()
    )

    raise_sizes: set[float] = set()

    for strategy in strategies.values():
        for action in strategy:
            if (
                isinstance(
                    action,
                    BettingAction,
                )
                and action.raise_to
                is not None
            ):
                raise_sizes.add(
                    action.raise_to
                )

    print(
        "Smoke training completed."
    )
    print(
        "Iterations:",
        trainer.completed_iterations,
    )
    print(
        "Games created:",
        game_factory.games_created,
    )
    print(
        "Information states:",
        len(strategies),
    )
    print(
        "Observed raise-to sizes:",
        sorted(raise_sizes),
    )


if __name__ == "__main__":
    main()