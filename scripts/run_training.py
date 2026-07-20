from time import perf_counter

from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.single_draw_game import SingleDrawGame


def main() -> None:
    iterations = 100

    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    fixed_game = SingleDrawGame(
        config=config,
        button_seat=0,
        shuffle_deck=True,
        deck_seed=42,
    )

    def factory() -> SingleDrawGame:
        return fixed_game

    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
    )

    start_time = perf_counter()

    trainer.train(
        factory,
        iterations=iterations,
    )

    elapsed_seconds = perf_counter() - start_time

    print()
    print("Training complete")
    print("-----------------")
    print(f"Iterations: {trainer.completed_iterations}")
    print(f"Information states: {len(trainer.node_store)}")
    print(f"Elapsed seconds: {elapsed_seconds:.4f}")

    print()
    print("Sample strategies")
    print("-----------------")

    for index, (state, strategy) in enumerate(
        trainer.average_strategies().items()
    ):
        if index >= 10:
            break

        print(
            f"State {index + 1}: "
            f"phase={state.phase}, "
            f"observer={state.observer_seat}, "
            f"acting={state.acting_seat}, "
            f"hand_key={state.own_hand_key}"
        )

        for action, probability in strategy.items():
            print(
                f"  {action}: "
                f"{probability:.4f}"
            )

        print()


if __name__ == "__main__":
    main()