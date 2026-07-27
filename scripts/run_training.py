from time import perf_counter

from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.single_draw_game import GamePhase
from solver.training_factory import (
    TrainingGameFactory,
)


def main() -> None:
    iterations = 1000
    abstraction = "bucket"

    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    factory = TrainingGameFactory(
        config=config,
        button_seat=0,
        initial_seed=42,
        alternate_button=True,
    )

    trainer = CFRTrainer(
        max_draw=3,
        raise_sizes=(),
        abstraction="bucket",
        traversal_mode="external_sampling",
        random_seed=42,
    )

    print("Random training")
    print("---------------")
    print(f"Iterations: {iterations}")
    print(f"Abstraction: {abstraction}")
    print("Traversal: external_sampling")
    print("Deck seeds: 42, 43, 44, ...")
    print("Button alternates: 0, 1, 0, 1, ...")
    print()

    start_time = perf_counter()

    trainer.train(
        factory,
        iterations=iterations,
    )

    elapsed_seconds = (
        perf_counter() - start_time
    )

    strategies = trainer.average_strategies()

    print()
    print("Training complete")
    print("-----------------")
    print(
        "Iterations: "
        f"{trainer.completed_iterations}"
    )
    print(
        "Games created: "
        f"{factory.games_created}"
    )
    print(
        "Information states: "
        f"{len(trainer.node_store)}"
    )
    print(
        "Elapsed seconds: "
        f"{elapsed_seconds:.4f}"
    )

    phase_counts: dict[str, int] = {}

    for state in trainer.node_store.nodes:
        phase_counts[state.phase] = (
            phase_counts.get(
                state.phase,
                0,
            )
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
        iterations_per_second = (
            iterations / elapsed_seconds
        )

        print(
            "Iterations per second: "
            f"{iterations_per_second:.2f}"
        )

    draw_entries = []

    for state, strategy in strategies.items():
        if state.phase != GamePhase.DRAW.value:
            continue

        node = trainer.node_store.get(state)

        if node is None:
            raise RuntimeError(
                "Strategy has no matching CFR node."
            )

        draw_entries.append(
            (
                node.strategy_weight_sum,
                node.visit_count,
                state,
                strategy,
                node,
            )
        )

    draw_nodes = [
        entry[4]
        for entry in draw_entries
    ]

    print()
    print("Draw-node coverage")
    print("------------------")
    print(
        "Draw nodes: "
        f"{len(draw_nodes)}"
    )
    print(
        "Weight >= 1: "
        f"{sum(
            node.strategy_weight_sum >= 1
            for node in draw_nodes
        )}"
    )
    print(
        "Weight >= 5: "
        f"{sum(
            node.strategy_weight_sum >= 5
            for node in draw_nodes
        )}"
    )
    print(
        "Weight >= 10: "
        f"{sum(
            node.strategy_weight_sum >= 10
            for node in draw_nodes
        )}"
    )
    print(
        "Weight >= 25: "
        f"{sum(
            node.strategy_weight_sum >= 25
            for node in draw_nodes
        )}"
    )

    draw_entries.sort(
        key=lambda entry: (
            entry[0],
            entry[1],
        ),
        reverse=True,
    )

    print()
    print("Most-trained draw strategies")
    print("----------------------------")

    max_draw_states_to_print = 10

    for index, (
        strategy_weight,
        visit_count,
        state,
        strategy,
        node,
    ) in enumerate(
        draw_entries[:max_draw_states_to_print],
        start=1,
    ):
        print(
            f"Draw state {index}: "
            f"observer={state.observer_seat}, "
            f"acting={state.acting_seat}"
        )

        print(
            f"  hand_key="
            f"{state.own_hand_key}"
        )

        print(
            f"  action_history="
            f"{state.action_history}"
        )

        print(
            f"  visits={visit_count}, "
            f"strategy_updates="
            f"{node.strategy_update_count}, "
            f"regret_updates="
            f"{node.regret_update_count}"
        )

        print(
            f"  strategy_weight="
            f"{strategy_weight:.6f}, "
            f"positive_regret="
            f"{node.positive_regret_sum:.6f}, "
            f"absolute_regret="
            f"{node.absolute_regret_sum:.6f}"
        )

        for action, probability in strategy.items():
            print(
                f"  {action}: "
                f"prob={probability:.4f}, "
                f"regret="
                f"{node.regret_sum[action]:.6f}, "
                f"strategy_sum="
                f"{node.strategy_sum[action]:.6f}"
            )

        print()

    if not draw_entries:
        print("No draw states found.")


if __name__ == "__main__":
    main()