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
from solver.postdraw_strength_bucket import (  # noqa: E402
    POSTDRAW_BUCKET_COUNT,
    PostdrawStrengthBucket,
    score_frequencies_snapshot,
)
from solver.single_draw_game import (  # noqa: E402
    SingleDrawGame,
)


SeedMode = Literal[
    "fixed",
    "sequential",
]


DEFAULT_BUCKET_COUNTS = (
    32,
    64,
    128,
    256,
    512,
    1024,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate postdraw CFR state-space "
            "compression using ordered "
            "made-hand strength buckets."
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

    parser.add_argument(
        "--bucket-counts",
        type=str,
        default=",".join(
            str(value)
            for value in DEFAULT_BUCKET_COUNTS
        ),
        help=(
            "Comma-separated candidate "
            "strength bucket counts."
        ),
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


def parse_bucket_counts(
    raw: str,
) -> tuple[int, ...]:
    try:
        values = tuple(
            int(item.strip())
            for item in raw.split(",")
            if item.strip()
        )
    except ValueError as error:
        raise ValueError(
            "Bucket counts must be "
            "comma-separated integers."
        ) from error

    if not values:
        raise ValueError(
            "At least one bucket count "
            "is required."
        )

    if any(
        value <= 0
        for value in values
    ):
        raise ValueError(
            "Bucket counts must be positive."
        )

    return tuple(
        sorted(
            set(
                values
            )
        )
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

        private_key = (
            information_state.own_hand_key
        )

        if not isinstance(
            private_key,
            PostdrawStrengthBucket,
        ):
            continue

        result.append(
            (
                information_state,
                node,
                private_key,
            )
        )

    return tuple(
        result
    )


def ordered_scores() -> tuple[
    tuple[int, ...],
    ...,
]:
    return tuple(
        sorted(
            score_frequencies_snapshot().keys()
        )
    )


def build_score_ranks(
    scores: tuple[
        tuple[int, ...],
        ...,
    ],
) -> dict[
    tuple[int, ...],
    int,
]:
    return {
        score: index
        for (
            index,
            score,
        ) in enumerate(
            scores
        )
    }


def strength_bucket_id(
    *,
    score: tuple[int, ...],
    score_ranks: dict[
        tuple[int, ...],
        int,
    ],
    unique_score_count: int,
    bucket_count: int,
) -> int:
    rank = score_ranks[
        score
    ]

    if unique_score_count <= 1:
        return 0

    bucket = (
        rank
        * bucket_count
        // unique_score_count
    )

    return min(
        bucket,
        bucket_count - 1,
    )


def rescaled_bucket_id(
    *,
    original_bucket_id: int,
    original_bucket_count: int,
    target_bucket_count: int,
) -> int:
    bucket = (
        original_bucket_id
        * target_bucket_count
        // original_bucket_count
    )

    return min(
        bucket,
        target_bucket_count - 1,
    )


def hypothetical_state_count(
    postdraw_states,
    *,
    bucket_count: int,
) -> tuple[
    int,
    int,
]:
    state_keys = set()
    used_bucket_ids = set()

    for (
        information_state,
        _node,
        made_bucket,
    ) in postdraw_states:
        bucket_id = (
            rescaled_bucket_id(
                original_bucket_id=(
                    made_bucket.bucket_id
                ),
                original_bucket_count=(
                    POSTDRAW_BUCKET_COUNT
                ),
                target_bucket_count=(
                    bucket_count
                ),
            )
        )

        used_bucket_ids.add(
            bucket_id
        )

        state_keys.add(
            (
                information_state.observer_seat,
                information_state.public_node,
                bucket_id,
            )
        )

    return (
        len(
            state_keys
        ),
        len(
            used_bucket_ids
        ),
    )


def reduction(
    original: int,
    reduced: int,
) -> float:
    if original <= 0:
        return 0.0

    return (
        1.0
        - reduced
        / original
    )


def bucket_population_distribution(
    *,
    scores: tuple[
        tuple[int, ...],
        ...,
    ],
    score_ranks: dict[
        tuple[int, ...],
        int,
    ],
    bucket_count: int,
) -> Counter:
    populations = Counter()

    unique_score_count = len(
        scores
    )

    for score in scores:
        bucket_id = (
            strength_bucket_id(
                score=score,
                score_ranks=score_ranks,
                unique_score_count=(
                    unique_score_count
                ),
                bucket_count=(
                    bucket_count
                ),
            )
        )

        populations[
            bucket_id
        ] += 1

    return populations


def print_bucket_analysis(
    *,
    postdraw_states,
    scores: tuple[
        tuple[int, ...],
        ...,
    ],
    score_ranks: dict[
        tuple[int, ...],
        int,
    ],
    bucket_counts: tuple[
        int,
        ...,
    ],
) -> None:
    original_states = len(
        postdraw_states
    )

    original_scores = len(
        scores
    )

    print()
    print(
        "Ordered strength-bucket analysis"
    )

    print(
        f"  original postdraw states: "
        f"{original_states:,}"
    )

    print(
        f"  unique full scores: "
        f"{original_scores:,}"
    )

    for bucket_count in (
        bucket_counts
    ):
        (
            hypothetical_states,
            used_buckets,
        ) = hypothetical_state_count(
            postdraw_states,
            bucket_count=(
                bucket_count
            ),
        )

        populations = (
            bucket_population_distribution(
                scores=scores,
                score_ranks=score_ranks,
                bucket_count=(
                    bucket_count
                ),
            )
        )

        population_values = tuple(
            populations.values()
        )

        minimum_population = min(
            population_values,
            default=0,
        )

        maximum_population = max(
            population_values,
            default=0,
        )

        average_population = (
            original_scores
            / used_buckets
            if used_buckets
            else 0.0
        )

        print()
        print(
            f"  target buckets: "
            f"{bucket_count:,}"
        )

        print(
            f"    used buckets: "
            f"{used_buckets:,}"
        )

        print(
            f"    hypothetical states: "
            f"{hypothetical_states:,}"
        )

        print(
            f"    state reduction: "
            f"{reduction(original_states, hypothetical_states):.2%}"
        )

        print(
            f"    avg scores/bucket: "
            f"{average_population:.2f}"
        )

        print(
            f"    min scores/bucket: "
            f"{minimum_population:,}"
        )

        print(
            f"    max scores/bucket: "
            f"{maximum_population:,}"
        )


def print_category_ranges(
    scores: tuple[
        tuple[int, ...],
        ...,
    ],
) -> None:
    categories: dict[
        int,
        list[
            tuple[int, ...]
        ],
    ] = {}

    for score in scores:
        if not score:
            continue

        categories.setdefault(
            score[0],
            [],
        ).append(
            score
        )

    print()
    print(
        "Score-category ranges"
    )

    running_index = 0

    for category in sorted(
        categories
    ):
        category_scores = (
            categories[
                category
            ]
        )

        start = (
            running_index
        )

        end = (
            running_index
            + len(
                category_scores
            )
            - 1
        )

        print(
            f"  category {category}: "
            f"{len(category_scores):,} scores "
            f"(ordered indices "
            f"{start:,}-{end:,})"
        )

        running_index += len(
            category_scores
        )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    bucket_counts = (
        parse_bucket_counts(
            args.bucket_counts
        )
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
        "Postdraw ordered-strength "
        "bucket diagnostic"
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
        f"  candidate bucket counts: "
        f"{bucket_counts}"
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

    scores = ordered_scores()

    score_ranks = (
        build_score_ranks(
            scores
        )
    )

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
        f"  unique full scores: "
        f"{len(scores):,}"
    )

    print_category_ranges(
        scores
    )

    print_bucket_analysis(
        postdraw_states=(
            postdraw_states
        ),
        scores=scores,
        score_ranks=(
            score_ranks
        ),
        bucket_counts=(
            bucket_counts
        ),
    )


if __name__ == "__main__":
    main()