import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path
import sys
from time import perf_counter


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from solver.bet_sizing import (  # noqa: E402
    FAST_BET_SIZING,
    FULL_BET_SIZING,
    BetSizingPolicy,
)
from solver.cards import Card  # noqa: E402
from solver.cfr_trainer import CFRTrainer  # noqa: E402
from solver.draw_hand_bucket import (  # noqa: E402
    DrawHandBucket,
    draw_hand_bucket,
)
from solver.game_state import GameConfig  # noqa: E402
from solver.hand import Hand  # noqa: E402
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


RANKS = "23456789TJQKA"
SUITS = "shdc"

TOTAL_FIVE_CARD_HANDS = 2_598_960


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure exact probability-mass "
            "coverage of DrawHandBucket at the "
            "initial predraw information state."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--max-draw",
        type=int,
        choices=range(0, 6),
        default=1,
    )

    parser.add_argument(
        "--bet-sizing",
        choices=(
            "none",
            "fast",
            "full",
        ),
        default="fast",
    )

    parser.add_argument(
        "--training-seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=20,
    )

    return parser.parse_args()


def resolve_bet_sizing(
    mode: str,
) -> tuple[
    tuple[float, ...] | None,
    BetSizingPolicy | None,
]:
    if mode == "none":
        return (), None

    if mode == "fast":
        return None, FAST_BET_SIZING

    if mode == "full":
        return None, FULL_BET_SIZING

    raise ValueError(
        "Unknown bet sizing mode."
    )


def make_training_factory(
    *,
    stack: float,
    initial_seed: int,
):
    game_counter = 0

    def game_factory() -> SingleDrawGame:
        nonlocal game_counter

        game = SingleDrawGame(
            config=GameConfig(
                player_count=2,
                starting_stack=stack,
                small_blind=1.0,
                big_blind=2.0,
                big_blind_ante=1.5,
            ),
            button_seat=0,
            deck_seed=(
                initial_seed
                + game_counter
            ),
        )

        game_counter += 1

        return game

    return game_factory


def standard_deck() -> tuple[
    Card,
    ...,
]:
    return tuple(
        Card(
            rank=rank,
            suit=suit,
        )
        for rank in RANKS
        for suit in SUITS
    )


def enumerate_bucket_frequencies() -> Counter:
    frequencies = Counter()

    deck = standard_deck()

    for cards in combinations(
        deck,
        5,
    ):
        hand = Hand(
            cards=tuple(cards)
        )

        bucket = draw_hand_bucket(
            hand
        )

        frequencies[
            bucket
        ] += 1

    return frequencies


def find_root_training_buckets(
    trainer: CFRTrainer,
) -> set[
    DrawHandBucket
]:
    root_buckets = set()

    for state in trainer.node_store.nodes:
        if (
            state.phase
            != "predraw_betting"
        ):
            continue

        public_node = (
            state.public_node
        )

        if (
            public_node.acting_seat
            != 0
        ):
            continue

        if len(
            public_node.action_history
        ) != 0:
            continue

        if not isinstance(
            state.own_hand_key,
            DrawHandBucket,
        ):
            continue

        root_buckets.add(
            state.own_hand_key
        )

    return root_buckets


def main() -> None:
    args = parse_args()

    if args.iterations <= 0:
        raise ValueError(
            "Iterations must be positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Stack must be positive."
        )

    (
        raise_sizes,
        bet_sizing_policy,
    ) = resolve_bet_sizing(
        args.bet_sizing
    )

    training_factory = (
        make_training_factory(
            stack=args.stack,
            initial_seed=(
                args.training_seed
            ),
        )
    )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
        abstraction="bucket",
        traversal_mode=(
            "external_sampling"
        ),
        draw_action_mode="auto",
        random_seed=(
            args.training_seed
        ),
    )

    print(
        "DrawHandBucket root coverage diagnostic"
    )

    print(
        f"  training iterations: "
        f"{args.iterations:,}"
    )

    print(
        f"  bet sizing: "
        f"{args.bet_sizing}"
    )

    print(
        f"  max draw: "
        f"{args.max_draw}"
    )

    print()

    print(
        "Training..."
    )

    training_start = (
        perf_counter()
    )

    trainer.train(
        training_factory,
        iterations=(
            args.iterations
        ),
    )

    print(
        f"  CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  training time: "
        f"{perf_counter() - training_start:.3f}s"
    )

    root_buckets = (
        find_root_training_buckets(
            trainer
        )
    )

    print()

    print(
        "Enumerating complete five-card "
        "DrawHandBucket universe..."
    )

    enumeration_start = (
        perf_counter()
    )

    frequencies = (
        enumerate_bucket_frequencies()
    )

    elapsed = (
        perf_counter()
        - enumeration_start
    )

    total_hands = sum(
        frequencies.values()
    )

    if (
        total_hands
        != TOTAL_FIVE_CARD_HANDS
    ):
        raise RuntimeError(
            "Unexpected five-card "
            "hand count."
        )

    all_buckets = set(
        frequencies
    )

    seen_buckets = (
        root_buckets
        & all_buckets
    )

    unseen_buckets = (
        all_buckets
        - seen_buckets
    )

    seen_mass = sum(
        frequencies[
            bucket
        ]
        for bucket in seen_buckets
    )

    unseen_mass = (
        total_hands
        - seen_mass
    )

    unique_bucket_coverage = (
        len(
            seen_buckets
        )
        / len(
            all_buckets
        )
    )

    probability_mass_coverage = (
        seen_mass
        / total_hands
    )

    print()

    print(
        "=" * 72
    )

    print(
        "ROOT COVERAGE"
    )

    print(
        f"  total exact hands: "
        f"{total_hands:,}"
    )

    print(
        f"  total DrawHandBuckets: "
        f"{len(all_buckets):,}"
    )

    print(
        f"  root buckets seen in training: "
        f"{len(seen_buckets):,}"
    )

    print(
        f"  unseen root buckets: "
        f"{len(unseen_buckets):,}"
    )

    print()

    print(
        f"  unique bucket coverage: "
        f"{unique_bucket_coverage:.2%}"
    )

    print(
        f"  covered exact-hand mass: "
        f"{seen_mass:,}"
    )

    print(
        f"  uncovered exact-hand mass: "
        f"{unseen_mass:,}"
    )

    print(
        f"  probability-mass coverage: "
        f"{probability_mass_coverage:.2%}"
    )

    print()

    print(
        f"  enumeration time: "
        f"{elapsed:.3f}s"
    )

    print()

    print(
        "=" * 72
    )

    print(
        "TOP UNSEEN BUCKETS BY "
        "EXACT-HAND MASS"
    )

    unseen_ranked = sorted(
        (
            (
                frequencies[
                    bucket
                ],
                bucket,
            )
            for bucket
            in unseen_buckets
        ),
        reverse=True,
        key=lambda item: (
            item[0]
        ),
    )

    cumulative_missing_mass = 0

    for (
        rank,
        (
            count,
            bucket,
        ),
    ) in enumerate(
        unseen_ranked[
            : args.top
        ],
        start=1,
    ):
        cumulative_missing_mass += (
            count
        )

        print()

        print(
            f"  #{rank}: "
            f"{count:,} exact hands "
            f"({count / total_hands:.4%})"
        )

        print(
            f"    {bucket}"
        )

    print()

    print(
        "=" * 72
    )

    print(
        "COVERAGE INTERPRETATION"
    )

    if (
        probability_mass_coverage
        >= 0.95
    ):
        print(
            "  Root DrawHandBucket probability "
            "mass coverage is at least 95%."
        )

        print(
            "  The main issue is likely deeper "
            "draw/public-state sampling rather "
            "than root private abstraction."
        )

    elif (
        probability_mass_coverage
        >= 0.85
    ):
        print(
            "  Root probability-mass coverage "
            "is moderate."
        )

        print(
            "  More training or improved chance "
            "sampling may be sufficient before "
            "changing the abstraction."
        )

    else:
        print(
            "  Root probability-mass coverage "
            "is low."
        )

        print(
            "  The current DrawHandBucket "
            "abstraction and chance-sampling "
            "scheme need further attention "
            "before exploitability testing."
        )


if __name__ == "__main__":
    main()