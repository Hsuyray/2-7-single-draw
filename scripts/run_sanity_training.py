from solver.actions import DiscardAction
from solver.canonical_hand import canonicalize_hand
from solver.cfr_trainer import CFRTrainer
from solver.game_state import GameConfig
from solver.hand import Hand
from solver.information_state import InformationState
from solver.training_factory import (
    FixedHeroDrawTrainingGameFactory,
)


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
    (
        "24466",
        Hand.from_strings(
            "2c",
            "4d",
            "4h",
            "6s",
            "6c",
        ),
    ),
    (
        "TTJQK",
        Hand.from_strings(
            "Tc",
            "Td",
            "Jh",
            "Qs",
            "Kc",
        ),
    ),
)


def main() -> None:
    iterations = 1_000

    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    print("Dedicated poker sanity training")
    print("-------------------------------")
    print(
        "Abstraction: bucket"
    )
    print(
        "Draw actions: candidate"
    )
    print(
        "Postdraw raise sizes: (2.0,)"
    )
    print(
        f"Iterations per spot/context: "
        f"{iterations}"
    )
    print()

    for label, hand in SANITY_SPOTS:
        print("=" * 72)
        print(
            f"{label}: {format_hand(hand)}"
        )
        print("=" * 72)

        run_spot(
            label="seat 0 / button 1",
            hand=hand,
            config=config,
            hero_seat=0,
            button_seat=1,
            iterations=iterations,
        )

        run_spot(
            label="seat 1 / button 0",
            hand=hand,
            config=config,
            hero_seat=1,
            button_seat=0,
            iterations=iterations,
        )

        print()


def run_spot(
    *,
    label: str,
    hand: Hand,
    config: GameConfig,
    hero_seat: int,
    button_seat: int,
    iterations: int,
) -> None:
    factory = (
        FixedHeroDrawTrainingGameFactory(
            config=config,
            hero_hand=hand,
            hero_seat=hero_seat,
            button_seat=button_seat,
            initial_seed=42,
        )
    )

    trainer = CFRTrainer(
        max_draw=3,
        raise_sizes=(2.0,),
        abstraction="bucket",
        traversal_mode="external_sampling",
        draw_action_mode="candidate",
        random_seed=42,
    )

    trainer.train(
        factory,
        iterations=iterations,
    )

    probe_factory = (
        FixedHeroDrawTrainingGameFactory(
            config=config,
            hero_hand=hand,
            hero_seat=hero_seat,
            button_seat=button_seat,
            initial_seed=42,
        )
    )

    game = probe_factory()

    state = InformationState.from_game(
        game,
        observer_seat=hero_seat,
        abstraction="bucket",
    )

    node = trainer.node_store.get(
        state
    )

    strategies = (
        trainer.average_strategies()
    )

    strategy = strategies.get(
        state
    )

    print()
    print(
        f"Context: {label}"
    )

    print(
        f"  hand_key="
        f"{state.own_hand_key}"
    )

    if (
        node is None
        or strategy is None
    ):
        print(
            "  Root hero strategy "
            "was not trained."
        )
        return

    print(
        f"  visits="
        f"{node.visit_count}"
    )

    print(
        "  strategy_updates="
        f"{node.strategy_update_count}"
    )

    print(
        "  regret_updates="
        f"{node.regret_update_count}"
    )

    print(
        "  strategy_weight="
        f"{node.strategy_weight_sum:.6f}"
    )

    print(
        "  positive_regret="
        f"{node.positive_regret_sum:.6f}"
    )

    print(
        "  absolute_regret="
        f"{node.absolute_regret_sum:.6f}"
    )

    print(
        "  Strategy:"
    )

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

        print(
            "    "
            f"{format_discard_action(
                hand=hand,
                action=action,
            )}: "
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
    canonical_hand = (
        canonicalize_hand(
            hand
        )
    )

    if not action.discard_indices:
        return "stand pat"

    discarded_cards = [
        canonical_hand.cards[index]
        for index
        in action.discard_indices
    ]

    cards_text = ", ".join(
        str(card)
        for card
        in discarded_cards
    )

    return (
        f"discard [{cards_text}]"
    )


if __name__ == "__main__":
    main()