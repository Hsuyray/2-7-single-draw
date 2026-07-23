from dataclasses import dataclass
from time import perf_counter

from solver.cards import Card
from solver.cfr_node import CFRNode
from solver.cfr_trainer import CFRTrainer
from solver.discard_actions import DiscardAction
from solver.game_state import GameConfig
from solver.hand import Hand
from solver.information_state import InformationState
from solver.single_draw_game import GamePhase
from solver.training_factory import (
    FixedHandsDrawTrainingGameFactory,
)


@dataclass(frozen=True)
class DiagnosticCase:
    name: str
    hero_cards: tuple[str, ...]
    opponent_cards: tuple[str, ...]
    expected_discards: tuple[int, ...]


def parse_card(text: str) -> Card:
    if len(text) != 2:
        raise ValueError(
            f"Invalid card text: {text}"
        )

    return Card(
        rank=text[0],
        suit=text[1],
    )


def make_hand(
    cards: tuple[str, ...],
) -> Hand:
    if len(cards) != 5:
        raise ValueError(
            "A diagnostic hand must contain "
            "exactly five cards."
        )

    parsed_cards = tuple(
        parse_card(card)
        for card in cards
    )

    if len(set(parsed_cards)) != 5:
        raise ValueError(
            "A diagnostic hand cannot contain "
            "duplicate cards."
        )

    return Hand(
        cards=parsed_cards,
    )


def find_root_draw_node(
    trainer: CFRTrainer,
    *,
    hero_seat: int,
) -> tuple[InformationState, CFRNode]:
    matching_nodes: list[
        tuple[InformationState, CFRNode]
    ] = []

    for state, node in (
        trainer.node_store.nodes.items()
    ):
        if state.phase != GamePhase.DRAW.value:
            continue

        if state.observer_seat != hero_seat:
            continue

        if state.acting_seat != hero_seat:
            continue

        has_previous_draw = any(
            action.phase
            == GamePhase.DRAW.value
            for action in state.action_history
        )

        if has_previous_draw:
            continue

        matching_nodes.append(
            (
                state,
                node,
            )
        )

    if len(matching_nodes) != 1:
        raise RuntimeError(
            "Expected exactly one root hero "
            "draw node, found "
            f"{len(matching_nodes)}."
        )

    return matching_nodes[0]


def format_action(
    action: DiscardAction,
) -> str:
    if not action.discard_indices:
        return "stand pat"

    indices = ", ".join(
        str(index)
        for index in action.discard_indices
    )

    return f"discard ({indices})"


def run_case(
    diagnostic_case: DiagnosticCase,
    *,
    config: GameConfig,
    iterations: int,
    random_seed: int,
) -> None:
    hero_seat = 0

    hero_hand = make_hand(
        diagnostic_case.hero_cards
    )
    opponent_hand = make_hand(
        diagnostic_case.opponent_cards
    )

    all_cards = (
        hero_hand.cards
        + opponent_hand.cards
    )

    if len(set(all_cards)) != 10:
        raise ValueError(
            f"{diagnostic_case.name}: "
            "Hero and opponent hands contain "
            "a duplicate physical card."
        )

    factory = FixedHandsDrawTrainingGameFactory(
        config=config,
        fixed_hands=(
            hero_hand,
            opponent_hand,
        ),
        button_seat=1,
        initial_seed=random_seed,
    )

    trainer = CFRTrainer(
        max_draw=3,
        raise_sizes=(),
        abstraction="exact",
        traversal_mode="external_sampling",
        random_seed=random_seed,
    )

    start_time = perf_counter()

    trainer.train(
        factory,
        iterations=iterations,
    )

    elapsed_seconds = (
        perf_counter() - start_time
    )

    state, node = find_root_draw_node(
        trainer,
        hero_seat=hero_seat,
    )

    strategy = node.average_strategy()

    sorted_actions = sorted(
        strategy.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    expected_action = DiscardAction(
        discard_indices=(
            diagnostic_case.expected_discards
        )
    )

    expected_probability = strategy.get(
        expected_action,
        0.0,
    )

    top_action, top_probability = (
        sorted_actions[0]
    )

    expected_is_top = (
        top_action == expected_action
    )

    print()
    print("=" * 72)
    print(diagnostic_case.name)
    print("=" * 72)

    print(
        "Hero cards: "
        + " ".join(
            diagnostic_case.hero_cards
        )
    )

    print(
        "Opponent cards: "
        + " ".join(
            diagnostic_case.opponent_cards
        )
    )

    print(
        "Canonical hero hand key: "
        f"{state.own_hand_key}"
    )

    print(
        f"Iterations: {iterations}"
    )

    print(
        "Elapsed seconds: "
        f"{elapsed_seconds:.2f}"
    )

    print(
        "Games created: "
        f"{factory.games_created}"
    )

    print(
        "Hero strategy updates: "
        f"{node.strategy_update_count}"
    )

    print(
        "Hero node visits: "
        f"{node.visit_count}"
    )

    print(
        "Expected action: "
        f"{format_action(expected_action)}"
    )

    print(
        "Expected probability: "
        f"{expected_probability:.4f}"
    )

    print(
        "Top action: "
        f"{format_action(top_action)}"
    )

    print(
        "Top probability: "
        f"{top_probability:.4f}"
    )

    print(
        "Expected action is top: "
        f"{expected_is_top}"
    )

    print()
    print("Top 10 actions")
    print("--------------")

    for action, probability in (
        sorted_actions[:10]
    ):
        marker = ""

        if action == expected_action:
            marker = "  <-- expected"

        print(
            f"{format_action(action):22s} "
            f"{probability:.4f}"
            f"{marker}"
        )


def main() -> None:
    iterations = 500
    random_seed = 42

    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    cases = (
        DiagnosticCase(
            name="Made seven: stand pat",
            hero_cards=(
                "2c",
                "3d",
                "4h",
                "5s",
                "7c",
            ),
            opponent_cards=(
                "2d",
                "3h",
                "4s",
                "6c",
                "8d",
            ),
            expected_discards=(),
        ),
        DiagnosticCase(
            name="Four-card wheel with king",
            hero_cards=(
                "2c",
                "3d",
                "4h",
                "5s",
                "Kc",
            ),
            opponent_cards=(
                "2d",
                "3h",
                "6s",
                "8c",
                "Td",
            ),
            expected_discards=(4,),
        ),
        DiagnosticCase(
            name="Three-card low with queen-king",
            hero_cards=(
                "2c",
                "3d",
                "4h",
                "Qs",
                "Kc",
            ),
            opponent_cards=(
                "2d",
                "5h",
                "7s",
                "9c",
                "Jd",
            ),
            expected_discards=(
                3,
                4,
            ),
        ),
        DiagnosticCase(
            name=(
                "Two-card low with "
                "jack-queen-king"
            ),
            hero_cards=(
                "2c",
                "3d",
                "Jh",
                "Qs",
                "Kc",
            ),
            opponent_cards=(
                "4d",
                "5h",
                "7s",
                "9c",
                "Td",
            ),
            expected_discards=(
                2,
                3,
                4,
            ),
        ),
        DiagnosticCase(
            name="Paired deuces",
            hero_cards=(
                "2c",
                "2d",
                "4h",
                "5s",
                "7c",
            ),
            opponent_cards=(
                "3c",
                "6d",
                "8h",
                "9s",
                "Tc",
            ),
            expected_discards=(1,),
        ),
    )

    print("Fixed-hands MCCFR diagnostics")
    print("-----------------------------")

    print(
        "Iterations per case: "
        f"{iterations}"
    )

    print("Abstraction: exact")
    print("Traversal: external_sampling")
    print("Maximum draw count: 3")
    print("Hero seat: 0")
    print("Button seat: 1")

    for index, diagnostic_case in enumerate(
        cases,
        start=1,
    ):
        run_case(
            diagnostic_case,
            config=config,
            iterations=iterations,
            random_seed=(
                random_seed
                + index * 10_000
            ),
        )


if __name__ == "__main__":
    main()