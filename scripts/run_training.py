from time import perf_counter

from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.training_factory import TrainingGameFactory


def main() -> None:
    iterations = 100

    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    factory = TrainingGameFactory(
        config=config,
        initial_seed=42,
        alternate_button=True,
    )

    trainer = CFRTrainer(
        max_draw=1,
        raise_sizes=(),
        abstraction="bucket",
    )

    start_time = perf_counter()

    trainer.train(
        factory,
        iterations=iterations,
    )

    elapsed_seconds = perf_counter() - start_time
    strategies = trainer.average_strategies()

    print()
    print("Training complete")
    print("-----------------")
    print(f"Iterations: {trainer.completed_iterations}")
    print(f"Games created: {factory.games_created}")
    print(f"Information states: {len(trainer.node_store)}")
    print(f"Elapsed seconds: {elapsed_seconds:.4f}")

    phase_counts: dict[str, int] = {}

    for state in trainer.node_store.nodes:
        phase_counts[state.phase] = (
            phase_counts.get(state.phase, 0)
            + 1
        )

    print()
    print("Information states by phase")
    print("---------------------------")

    for phase, count in sorted(
        phase_counts.items()
    ):
        print(f"{phase}: {count}")

    unique_hand_keys = {
        state.own_hand_key
        for state in trainer.node_store.nodes
    }

    print()
    print(
        "Unique private hand keys: "
        f"{len(unique_hand_keys)}"
    )

    if elapsed_seconds > 0:
        print(
            "Iterations per second: "
            f"{iterations / elapsed_seconds:.2f}"
        )

    print()
    print("Sample strategies")
    print("-----------------")

    for index, (state, strategy) in enumerate(
        strategies.items()
    ):
        if index >= 5:
            break

        print(
            f"State {index + 1}: "
            f"phase={state.phase}, "
            f"observer={state.observer_seat}, "
            f"acting={state.acting_seat}"
        )
        print(
            f"  hand_key={state.own_hand_key}"
        )

        for action, probability in strategy.items():
            print(
                f"  {action}: "
                f"{probability:.4f}"
            )

        print()


if __name__ == "__main__":
    main()