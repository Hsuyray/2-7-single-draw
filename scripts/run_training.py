from time import perf_counter

from solver.actions import DiscardAction
from solver.canonical_hand import canonicalize_hand
from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.hand import Hand
from solver.information_state import (
    InformationState,
)
from solver.legal_actions import SolverAction
from solver.single_draw_game import (
    GamePhase,
)
from solver.training_factory import (
    FixedHeroDrawTrainingGameFactory,
    TrainingGameFactory,
)


Strategy = dict[SolverAction, float]

StrategySnapshot = dict[
    InformationState,
    Strategy,
]


SANITY_SPOTS = (
    (
        "75432",
        Hand.from_strings(
            "2c",
            "3d",
            "4h",
            "5s",
            "7c",
        ),
    ),
    (
        "K5432",
        Hand.from_strings(
            "2c",
            "3d",
            "4h",
            "5s",
            "Kc",
        ),
    ),
    (
        "KQ432",
        Hand.from_strings(
            "2c",
            "3d",
            "4h",
            "Qs",
            "Kc",
        ),
    ),
    (
        "KQJ32",
        Hand.from_strings(
            "2c",
            "3d",
            "Jh",
            "Qs",
            "Kc",
        ),
    ),
    (
        "22547",
        Hand.from_strings(
            "2c",
            "2d",
            "4h",
            "5s",
            "7c",
        ),
    ),
)


def main() -> None:
    checkpoints = (
        1_000,
    )

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
        abstraction=abstraction,
        traversal_mode="external_sampling",
        random_seed=42,
    )

    print("Random training")
    print("---------------")

    print(
        "Checkpoints: "
        + ", ".join(
            str(value)
            for value in checkpoints
        )
    )

    print(
        f"Abstraction: {abstraction}"
    )

    print(
        "Traversal: external_sampling"
    )

    print(
        "Draw action mode: "
        f"{trainer.resolved_draw_action_mode}"
    )

    print(
        "Deck seeds: 42, 43, 44, ..."
    )

    print(
        "Button alternates: "
        "0, 1, 0, 1, ..."
    )

    print()

    overall_start = perf_counter()

    previous_snapshot: (
        StrategySnapshot | None
    ) = None

    previous_checkpoint = 0

    for checkpoint in checkpoints:
        iterations_to_run = (
            checkpoint
            - previous_checkpoint
        )

        checkpoint_start = perf_counter()

        trainer.train(
            factory,
            iterations=iterations_to_run,
        )

        checkpoint_seconds = (
            perf_counter()
            - checkpoint_start
        )

        total_seconds = (
            perf_counter()
            - overall_start
        )

        strategies = (
            trainer.average_strategies()
        )

        print_checkpoint_report(
            trainer=trainer,
            factory=factory,
            config=config,
            checkpoint=checkpoint,
            checkpoint_iterations=(
                iterations_to_run
            ),
            checkpoint_seconds=(
                checkpoint_seconds
            ),
            total_seconds=total_seconds,
            strategies=strategies,
            previous_snapshot=(
                previous_snapshot
            ),
        )

        previous_snapshot = (
            copy_strategy_snapshot(
                strategies
            )
        )

        previous_checkpoint = checkpoint

    final_strategies = (
        trainer.average_strategies()
    )

    print_final_draw_strategies(
        trainer=trainer,
        strategies=final_strategies,
    )


def print_checkpoint_report(
    *,
    trainer: CFRTrainer,
    factory: TrainingGameFactory,
    config: GameConfig,
    checkpoint: int,
    checkpoint_iterations: int,
    checkpoint_seconds: float,
    total_seconds: float,
    strategies: StrategySnapshot,
    previous_snapshot: (
        StrategySnapshot | None
    ),
) -> None:
    print()
    print("=" * 72)
    print(
        f"Training checkpoint: {checkpoint}"
    )
    print("=" * 72)

    print(
        "Completed iterations: "
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
        "Checkpoint seconds: "
        f"{checkpoint_seconds:.4f}"
    )

    print(
        "Total seconds: "
        f"{total_seconds:.4f}"
    )

    if checkpoint_seconds > 0:
        checkpoint_speed = (
            checkpoint_iterations
            / checkpoint_seconds
        )

        print(
            "Checkpoint iterations/sec: "
            f"{checkpoint_speed:.2f}"
        )

    if total_seconds > 0:
        total_speed = (
            checkpoint
            / total_seconds
        )

        print(
            "Overall iterations/sec: "
            f"{total_speed:.2f}"
        )

    phase_counts = get_phase_counts(
        trainer
    )

    print()
    print(
        "Information states by phase"
    )
    print(
        "---------------------------"
    )

    for phase, count in sorted(
        phase_counts.items()
    ):
        print(
            f"{phase}: {count}"
        )

    unique_hand_keys = {
        state.own_hand_key
        for state
        in trainer.node_store.nodes
    }

    print()

    print(
        "Unique private hand keys: "
        f"{len(unique_hand_keys)}"
    )

    print_draw_coverage(
        trainer
    )

    print_regret_diagnostics(
        trainer
    )

    print_strategy_stability(
        trainer=trainer,
        strategies=strategies,
        previous_snapshot=(
            previous_snapshot
        ),
    )

    print_sanity_spots(
        config=config,
        strategies=strategies,
    )


def get_phase_counts(
    trainer: CFRTrainer,
) -> dict[str, int]:
    phase_counts: dict[str, int] = {}

    for state in trainer.node_store.nodes:
        phase_counts[state.phase] = (
            phase_counts.get(
                state.phase,
                0,
            )
            + 1
        )

    return phase_counts


def get_draw_nodes(
    trainer: CFRTrainer,
):
    nodes = []

    for state in trainer.node_store.nodes:
        if (
            state.phase
            != GamePhase.DRAW.value
        ):
            continue

        node = trainer.node_store.get(
            state
        )

        if node is None:
            raise RuntimeError(
                "Information state has "
                "no matching CFR node."
            )

        nodes.append(node)

    return nodes


def print_draw_coverage(
    trainer: CFRTrainer,
) -> None:
    draw_nodes = get_draw_nodes(
        trainer
    )

    print()
    print("Draw-node coverage")
    print("------------------")

    print(
        "Draw nodes: "
        f"{len(draw_nodes)}"
    )

    for threshold in (
        1,
        5,
        10,
        25,
        50,
        100,
    ):
        count = sum(
            node.strategy_weight_sum
            >= threshold
            for node in draw_nodes
        )

        print(
            f"Weight >= {threshold}: "
            f"{count}"
        )

    if draw_nodes:
        max_updates = max(
            node.strategy_update_count
            for node in draw_nodes
        )

        max_visits = max(
            node.visit_count
            for node in draw_nodes
        )

        print(
            "Maximum strategy updates: "
            f"{max_updates}"
        )

        print(
            "Maximum visits: "
            f"{max_visits}"
        )


def print_regret_diagnostics(
    trainer: CFRTrainer,
) -> None:
    nodes = []

    for state in trainer.node_store.nodes:
        node = trainer.node_store.get(
            state
        )

        if node is None:
            continue

        if node.regret_update_count <= 0:
            continue

        nodes.append(node)

    print()
    print("Regret diagnostics")
    print("------------------")

    if not nodes:
        print(
            "No regret-updated nodes."
        )
        return

    total_positive_regret = sum(
        node.positive_regret_sum
        for node in nodes
    )

    total_absolute_regret = sum(
        node.absolute_regret_sum
        for node in nodes
    )

    total_regret_updates = sum(
        node.regret_update_count
        for node in nodes
    )

    average_positive_regret = (
        total_positive_regret
        / len(nodes)
    )

    average_absolute_regret = (
        total_absolute_regret
        / len(nodes)
    )

    positive_per_update = (
        total_positive_regret
        / total_regret_updates
    )

    absolute_per_update = (
        total_absolute_regret
        / total_regret_updates
    )

    print(
        "Nodes with regret updates: "
        f"{len(nodes)}"
    )

    print(
        "Average positive regret/node: "
        f"{average_positive_regret:.6f}"
    )

    print(
        "Average absolute regret/node: "
        f"{average_absolute_regret:.6f}"
    )

    print(
        "Positive regret/update: "
        f"{positive_per_update:.6f}"
    )

    print(
        "Absolute regret/update: "
        f"{absolute_per_update:.6f}"
    )


def print_strategy_stability(
    *,
    trainer: CFRTrainer,
    strategies: StrategySnapshot,
    previous_snapshot: (
        StrategySnapshot | None
    ),
) -> None:
    print()
    print("Strategy stability")
    print("------------------")

    if previous_snapshot is None:
        print(
            "No previous checkpoint."
        )
        return

    all_changes: list[float] = []
    trained_changes: list[float] = []
    high_coverage_changes: list[
        float
    ] = []

    shared_states = (
        strategies.keys()
        & previous_snapshot.keys()
    )

    comparable_states = 0

    for state in shared_states:
        current_strategy = (
            strategies[state]
        )

        previous_strategy = (
            previous_snapshot[state]
        )

        if (
            current_strategy.keys()
            != previous_strategy.keys()
        ):
            continue

        change = strategy_distance(
            current_strategy,
            previous_strategy,
        )

        all_changes.append(
            change
        )

        comparable_states += 1

        node = trainer.node_store.get(
            state
        )

        if node is None:
            continue

        if (
            node.strategy_weight_sum
            >= 5
        ):
            trained_changes.append(
                change
            )

        if (
            node.strategy_weight_sum
            >= 25
        ):
            high_coverage_changes.append(
                change
            )

    print(
        "Shared states: "
        f"{len(shared_states)}"
    )

    print(
        "Comparable states: "
        f"{comparable_states}"
    )

    print_change_summary(
        label="All shared states",
        changes=all_changes,
    )

    print_change_summary(
        label="Weight >= 5",
        changes=trained_changes,
    )

    print_change_summary(
        label="Weight >= 25",
        changes=(
            high_coverage_changes
        ),
    )


def strategy_distance(
    current: Strategy,
    previous: Strategy,
) -> float:
    return (
        0.5
        * sum(
            abs(
                current[action]
                - previous[action]
            )
            for action in current
        )
    )


def print_change_summary(
    *,
    label: str,
    changes: list[float],
) -> None:
    if not changes:
        print(
            f"{label}: "
            "no comparable states"
        )
        return

    ordered = sorted(
        changes
    )

    average_change = (
        sum(changes)
        / len(changes)
    )

    median_change = percentile(
        ordered,
        0.50,
    )

    p90_change = percentile(
        ordered,
        0.90,
    )

    max_change = ordered[-1]

    print(
        f"{label}: "
        f"n={len(changes)}, "
        f"avg={average_change:.4f}, "
        f"median={median_change:.4f}, "
        f"p90={p90_change:.4f}, "
        f"max={max_change:.4f}"
    )


def percentile(
    ordered_values: list[float],
    fraction: float,
) -> float:
    if not ordered_values:
        raise ValueError(
            "Cannot calculate percentile "
            "of an empty list."
        )

    if not (
        0.0
        <= fraction
        <= 1.0
    ):
        raise ValueError(
            "Percentile fraction must "
            "be between 0 and 1."
        )

    index = round(
        fraction
        * (
            len(ordered_values)
            - 1
        )
    )

    return ordered_values[index]


def copy_strategy_snapshot(
    strategies: StrategySnapshot,
) -> StrategySnapshot:
    return {
        state: dict(strategy)
        for state, strategy
        in strategies.items()
    }


def print_sanity_spots(
    *,
    config: GameConfig,
    strategies: StrategySnapshot,
) -> None:
    print()
    print("Poker sanity spots")
    print("------------------")

    for label, hand in SANITY_SPOTS:
        print_sanity_spot(
            label=label,
            hand=hand,
            config=config,
            strategies=strategies,
        )


def print_sanity_spot(
    *,
    label: str,
    hand: Hand,
    config: GameConfig,
    strategies: StrategySnapshot,
) -> None:
    factory = (
        FixedHeroDrawTrainingGameFactory(
            config=config,
            hero_hand=hand,
            hero_seat=0,
            button_seat=1,
            initial_seed=987_654,
        )
    )

    game = factory()

    state = InformationState.from_game(
        game,
        observer_seat=0,
        abstraction="bucket",
    )

    strategy = strategies.get(
        state
    )

    print()
    print(
        f"{label}: "
        f"{format_hand(hand)}"
    )

    print(
        "  hand_key="
        f"{state.own_hand_key}"
    )

    if strategy is None:
        print(
            "  Strategy not found "
            "in random training."
        )
        return

    ordered_strategy = sorted(
        strategy.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    for action, probability in (
        ordered_strategy
    ):
        if not isinstance(
            action,
            DiscardAction,
        ):
            continue

        action_text = (
            format_discard_action(
                hand=hand,
                action=action,
            )
        )

        print(
            f"  {action_text}: "
            f"{probability:.4f}"
        )


def format_hand(
    hand: Hand,
) -> str:
    return " ".join(
        str(card)
        for card in hand.cards
    )


def format_discard_action(
    *,
    hand: Hand,
    action: DiscardAction,
) -> str:
    canonical_hand = canonicalize_hand(
        hand
    )

    if not action.discard_indices:
        return "stand pat"

    discarded_cards = [
        canonical_hand.cards[index]
        for index in action.discard_indices
    ]

    cards_text = ", ".join(
        str(card)
        for card in discarded_cards
    )

    return f"discard [{cards_text}]"


def print_final_draw_strategies(
    *,
    trainer: CFRTrainer,
    strategies: StrategySnapshot,
) -> None:
    draw_entries = []

    for state, strategy in (
        strategies.items()
    ):
        if (
            state.phase
            != GamePhase.DRAW.value
        ):
            continue

        node = trainer.node_store.get(
            state
        )

        if node is None:
            raise RuntimeError(
                "Strategy has no matching "
                "CFR node."
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

    draw_entries.sort(
        key=lambda entry: (
            entry[0],
            entry[1],
        ),
        reverse=True,
    )

    print()
    print("=" * 72)
    print(
        "Final most-trained "
        "draw strategies"
    )
    print("=" * 72)

    if not draw_entries:
        print(
            "No draw states found."
        )
        return

    max_draw_states_to_print = 10

    for index, (
        strategy_weight,
        visit_count,
        state,
        strategy,
        node,
    ) in enumerate(
        draw_entries[
            :max_draw_states_to_print
        ],
        start=1,
    ):
        print(
            f"Draw state {index}: "
            f"observer="
            f"{state.observer_seat}, "
            f"acting="
            f"{state.acting_seat}"
        )

        print(
            "  hand_key="
            f"{state.own_hand_key}"
        )

        print(
            "  action_history="
            f"{state.action_history}"
        )

        print(
            f"  visits={visit_count}, "
            "strategy_updates="
            f"{node.strategy_update_count}, "
            "regret_updates="
            f"{node.regret_update_count}"
        )

        print(
            "  strategy_weight="
            f"{strategy_weight:.6f}, "
            "positive_regret="
            f"{node.positive_regret_sum:.6f}, "
            "absolute_regret="
            f"{node.absolute_regret_sum:.6f}"
        )

        ordered_strategy = sorted(
            strategy.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        for action, probability in (
            ordered_strategy
        ):
            print(
                f"  {action}: "
                f"prob={probability:.4f}, "
                "regret="
                f"{node.regret_sum[action]:.6f}, "
                "strategy_sum="
                f"{node.strategy_sum[action]:.6f}"
            )

        print()


if __name__ == "__main__":
    main()