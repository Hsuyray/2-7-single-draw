import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Literal


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
from solver.cfr_trainer import (  # noqa: E402
    CFRTrainer,
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.made_hand_bucket import (  # noqa: E402
    MadeHandBucket,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


SeedMode = Literal[
    "fixed",
    "sequential",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect postdraw MadeHandBucket "
            "cardinality and estimate how much "
            "coarser score abstractions would "
            "reduce CFR state space."
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
        choices=range(
            0,
            6,
        ),
        default=1,
    )

    parser.add_argument(
        "--traversal-mode",
        choices=(
            "full",
            "external_sampling",
        ),
        default="external_sampling",
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
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--seed-mode",
        choices=(
            "fixed",
            "sequential",
        ),
        default="sequential",
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.iterations <= 0:
        raise ValueError(
            "Iterations must be positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Stack must be positive."
        )


def resolve_bet_sizing(
    mode: str,
) -> tuple[
    tuple[float, ...] | None,
    BetSizingPolicy | None,
]:
    if mode == "none":
        return (
            (),
            None,
        )

    if mode == "fast":
        return (
            None,
            FAST_BET_SIZING,
        )

    if mode == "full":
        return (
            None,
            FULL_BET_SIZING,
        )

    raise ValueError(
        "Unknown bet sizing mode."
    )


def make_game_factory(
    *,
    stack: float,
    seed: int,
    seed_mode: SeedMode,
):
    game_counter = 0

    def game_factory() -> SingleDrawGame:
        nonlocal game_counter

        if seed_mode == "fixed":
            game_seed = seed
        else:
            game_seed = (
                seed
                + game_counter
            )

        game_counter += 1

        return SingleDrawGame(
            config=GameConfig(
                player_count=2,
                starting_stack=stack,
                small_blind=1.0,
                big_blind=2.0,
                big_blind_ante=1.5,
            ),
            button_seat=0,
            deck_seed=game_seed,
        )

    return game_factory


def score_prefix(
    bucket: MadeHandBucket,
    length: int,
) -> tuple[int, ...]:
    return tuple(
        bucket.score[
            :length
        ]
    )


def collect_postdraw_states(
    trainer: CFRTrainer,
):
    result = []

    for (
        information_state,
        node,
    ) in trainer.node_store.nodes.items():
        if (
            information_state.phase
            != "postdraw_betting"
        ):
            continue

        hand_key = (
            information_state
            .own_hand_key
        )

        if not isinstance(
            hand_key,
            MadeHandBucket,
        ):
            continue

        result.append(
            (
                information_state,
                node,
                hand_key,
            )
        )

    return tuple(
        result
    )


def print_score_length_distribution(
    buckets: set[
        MadeHandBucket
    ],
) -> None:
    distribution = Counter(
        len(
            bucket.score
        )
        for bucket in buckets
    )

    print()
    print(
        "Score length distribution"
    )

    for (
        length,
        count,
    ) in sorted(
        distribution.items()
    ):
        print(
            f"  length {length}: "
            f"{count:,}"
        )


def print_category_distribution(
    buckets: set[
        MadeHandBucket
    ],
) -> None:
    category_counts = Counter(
        bucket.score[0]
        for bucket in buckets
        if bucket.score
    )

    print()
    print(
        "Made-hand category distribution"
    )

    for (
        category,
        count,
    ) in sorted(
        category_counts.items()
    ):
        print(
            f"  category {category}: "
            f"{count:,}"
        )


def hypothetical_state_count(
    postdraw_states,
    *,
    prefix_length: int,
) -> int:
    keys = set()

    for (
        information_state,
        _node,
        bucket,
    ) in postdraw_states:
        abstract_private_key = (
            score_prefix(
                bucket,
                prefix_length,
            )
        )

        keys.add(
            (
                information_state.observer_seat,
                information_state.public_node,
                abstract_private_key,
            )
        )

    return len(
        keys
    )


def unique_prefix_count(
    buckets: set[
        MadeHandBucket
    ],
    *,
    prefix_length: int,
) -> int:
    return len(
        {
            score_prefix(
                bucket,
                prefix_length,
            )
            for bucket in buckets
        }
    )


def compression_ratio(
    *,
    original: int,
    reduced: int,
) -> float:
    if original == 0:
        return 0.0

    return (
        1.0
        - reduced
        / original
    )


def print_prefix_analysis(
    *,
    buckets: set[
        MadeHandBucket
    ],
    postdraw_states,
) -> None:
    original_bucket_count = len(
        buckets
    )

    original_state_count = len(
        postdraw_states
    )

    maximum_score_length = max(
        (
            len(
                bucket.score
            )
            for bucket in buckets
        ),
        default=0,
    )

    print()
    print(
        "Hypothetical score-prefix "
        "abstractions"
    )

    print(
        "  original unique buckets: "
        f"{original_bucket_count:,}"
    )

    print(
        "  original postdraw states: "
        f"{original_state_count:,}"
    )

    print()

    for prefix_length in range(
        1,
        maximum_score_length + 1,
    ):
        prefix_buckets = (
            unique_prefix_count(
                buckets,
                prefix_length=(
                    prefix_length
                ),
            )
        )

        prefix_states = (
            hypothetical_state_count(
                postdraw_states,
                prefix_length=(
                    prefix_length
                ),
            )
        )

        bucket_reduction = (
            compression_ratio(
                original=(
                    original_bucket_count
                ),
                reduced=(
                    prefix_buckets
                ),
            )
        )

        state_reduction = (
            compression_ratio(
                original=(
                    original_state_count
                ),
                reduced=(
                    prefix_states
                ),
            )
        )

        print(
            f"  score[:{prefix_length}]"
        )

        print(
            f"    private buckets: "
            f"{prefix_buckets:,}"
        )

        print(
            f"    bucket reduction: "
            f"{bucket_reduction:.2%}"
        )

        print(
            f"    hypothetical states: "
            f"{prefix_states:,}"
        )

        print(
            f"    state reduction: "
            f"{state_reduction:.2%}"
        )


def print_top_prefixes(
    *,
    buckets: set[
        MadeHandBucket
    ],
) -> None:
    print()
    print(
        "Most common structural prefixes"
    )

    for prefix_length in (
        1,
        2,
        3,
    ):
        counts = Counter(
            score_prefix(
                bucket,
                prefix_length,
            )
            for bucket in buckets
        )

        print()
        print(
            f"  score[:{prefix_length}] "
            f"top 15:"
        )

        for (
            prefix,
            count,
        ) in counts.most_common(
            15
        ):
            print(
                f"    {prefix}: "
                f"{count:,} full buckets"
            )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    (
        raise_sizes,
        bet_sizing_policy,
    ) = resolve_bet_sizing(
        args.bet_sizing
    )

    game_factory = make_game_factory(
        stack=args.stack,
        seed=args.seed,
        seed_mode=args.seed_mode,
    )

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=(
            bet_sizing_policy
        ),
        abstraction="bucket",
        traversal_mode=(
            args.traversal_mode
        ),
        draw_action_mode="auto",
        random_seed=args.seed,
    )

    print(
        "Postdraw bucket-space diagnostic"
    )

    print(
        f"  iterations: "
        f"{args.iterations:,}"
    )

    print(
        f"  stack: "
        f"{args.stack:g}"
    )

    print(
        f"  bet sizing: "
        f"{args.bet_sizing}"
    )

    print(
        f"  max draw: "
        f"{args.max_draw}"
    )

    print(
        f"  seed mode: "
        f"{args.seed_mode}"
    )

    print(
        "Training..."
    )

    trainer.train(
        game_factory,
        iterations=(
            args.iterations
        ),
    )

    postdraw_states = (
        collect_postdraw_states(
            trainer
        )
    )

    buckets = {
        bucket
        for (
            _state,
            _node,
            bucket,
        ) in postdraw_states
    }

    public_nodes = {
        state.public_node
        for (
            state,
            _node,
            _bucket,
        ) in postdraw_states
    }

    print()
    print(
        "Summary"
    )

    print(
        f"  total CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  postdraw states: "
        f"{len(postdraw_states):,}"
    )

    print(
        f"  postdraw public nodes: "
        f"{len(public_nodes):,}"
    )

    print(
        f"  unique MadeHandBucket: "
        f"{len(buckets):,}"
    )

    if buckets:
        print_score_length_distribution(
            buckets
        )

        print_category_distribution(
            buckets
        )

        print_prefix_analysis(
            buckets=buckets,
            postdraw_states=(
                postdraw_states
            ),
        )

        print_top_prefixes(
            buckets=buckets
        )


if __name__ == "__main__":
    main()