"""
Draw-phase sanity analysis of a saved checkpoint (workstream B2).

Read-only: loads a checkpoint, classifies every draw information
state by its DrawHandBucket, and measures how much probability the
stored strategy puts on clearly wrong discards, both over the stored
states (static) and over the draw decisions actually reached in
self-play (reach-weighted, same deals and action path as
scripts.evaluate_checkpoint).

Bucket-canonical card positions 0..4 are sorted by rank, low to high
(draw_bucket_card_ordering), and DrawHandBucket.rank_classes /
rank_multiplicities are aligned with them, so discard actions can be
judged from the bucket alone:

  break_made_low   no pair, no straight or flush, every card 7 or
                   lower (rank class <= 2): drawing any card breaks a
                   made 7-low or better. Standing pat is never worse.
  keep_pair        the discard keeps two or more cards of one rank.
A flagged action counts as a mistake only when the state also has a
legal action that is not flagged (avoidable mistakes): with
max_draw=1, two pair must keep a pair, for example.

Informational, not mistakes:
  keep_high        an unpaired card is discarded while a higher
                   unpaired card is kept (straights and flush-risk
                   hands excluded). NOT counted as a mistake: the
                   bucket does not encode straight-draw structure,
                   so 3-4-5-6-8 (throw the 6, a straight-draw
                   breaker, is right) and 2-4-5-7-8 (throw the 7 is
                   wrong) share one bucket; see bucket resolution.
  snow             standing pat with a pair or worse, a straight or
                   flush, or a T-high or worse no-pair hand. Snowing
                   is part of a sound 2-7 strategy in moderation.

Rank classes merge 2-3, 4-5, 6-7, 8-9, T-J, Q-K-A, so the bucket
cannot tell e.g. 8-5-4-3-2 from 9-5-4-3-2; the analysis inherits that
limit and reports it (bucket resolution section).

    python -m scripts.inspect_draw_decisions checkpoints/production_v1.chk.gz
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

from solver.actions import (
    DiscardAction,
)
from solver.checkpoint_evaluation import (
    _is_near_uniform,
    _stored_strategies,
    deck_seed_base,
    derive_seed,
    make_deal_factory,
    make_profile_evaluator,
    setup_from_metadata,
)
from solver.draw_hand_bucket import (
    DrawHandBucket,
)


LOW_RANK_CLASS_MAX = 2
SNOW_HIGH_RANK_CLASS_MIN = 4

MISTAKES = (
    "break_made_low",
    "keep_pair",
)


# ----------------------------------------------------------------
# Hand and action classification
# ----------------------------------------------------------------


def rank_blocks(
    bucket: DrawHandBucket,
) -> list[tuple[int, ...]]:
    """
    Positions grouped by rank. Equal ranks are adjacent
    in the canonical order and each rank's block has
    length equal to its multiplicity.
    """
    blocks = []
    position = 0

    while position < len(bucket.rank_classes):
        size = bucket.rank_multiplicities[position]

        blocks.append(
            tuple(
                range(
                    position,
                    position + size,
                )
            )
        )

        position += size

    return blocks


def hand_category(
    bucket: DrawHandBucket,
) -> str:
    if bucket.is_straight or bucket.is_flush:
        return "straight_or_flush"

    if bucket.unique_rank_count == 5:
        top = max(bucket.rank_classes)

        if top <= LOW_RANK_CLASS_MAX:
            return "made_7_or_better"

        if top == 3:
            return "made_8_or_9"

        low = sum(
            1
            for rank_class in bucket.rank_classes
            if rank_class <= LOW_RANK_CLASS_MAX
        )

        return f"no_pair_T_plus_{low}_low"

    if bucket.unique_rank_count == 4:
        return "one_pair"

    return "two_pair_or_worse"


def action_flags(
    bucket: DrawHandBucket,
    action: DiscardAction,
) -> dict[str, bool]:
    discarded = set(action.discard_indices)

    kept = [
        position
        for position in range(5)
        if position not in discarded
    ]

    category = hand_category(bucket)

    break_made_low = (
        category == "made_7_or_better"
        and action.draw_count > 0
    )

    keep_pair = any(
        len(block) >= 2
        and sum(
            1
            for position in block
            if position in kept
        )
        >= 2
        for block in rank_blocks(bucket)
    )

    keep_high = False

    if not (
        bucket.is_straight
        or any(bucket.flush_risk_positions)
    ):
        unpaired = [
            block[0]
            for block in rank_blocks(bucket)
            if len(block) == 1
        ]

        # Positions are sorted by rank, so a larger
        # position is a strictly higher unpaired rank.
        keep_high = any(
            low in discarded
            and high not in discarded
            for low in unpaired
            for high in unpaired
            if high > low
        )

    snow = (
        action.draw_count == 0
        and (
            category
            in (
                "one_pair",
                "two_pair_or_worse",
                "straight_or_flush",
            )
            or (
                bucket.unique_rank_count == 5
                and max(bucket.rank_classes)
                >= SNOW_HIGH_RANK_CLASS_MIN
            )
        )
    )

    return {
        "break_made_low": break_made_low,
        "keep_pair": keep_pair,
        "keep_high": keep_high,
        "snow": snow,
    }


def strategy_masses(
    bucket: DrawHandBucket,
    strategy: dict,
) -> dict[str, float]:
    masses = {
        name: 0.0
        for name in (
            *MISTAKES,
            "keep_high",
            "snow",
            "any_mistake",
        )
    }

    flags_by_action = {
        action: action_flags(bucket, action)
        for action in strategy
    }

    # A mistake type is avoidable only if some legal
    # action is free of it.
    avoidable = {
        name: not all(
            flags[name]
            for flags in flags_by_action.values()
        )
        for name in (*MISTAKES, "keep_high")
    }

    draw_count = 0.0

    for action, probability in strategy.items():
        flags = flags_by_action[action]

        for name, flagged in flags.items():
            if flagged and avoidable.get(name, True):
                masses[name] += probability

        if any(
            flags[name] and avoidable[name]
            for name in MISTAKES
        ):
            masses["any_mistake"] += probability

        draw_count += (
            probability
            * action.draw_count
        )

    masses["expected_draw_count"] = draw_count

    return masses


# ----------------------------------------------------------------
# Accumulators
# ----------------------------------------------------------------


class MassTable:
    """
    Weighted mean masses per hand category,
    split by whether the strategy is near uniform.
    """

    def __init__(self) -> None:
        self.weight: Counter = Counter()
        self.sums: dict = {}

    def add(
        self,
        *,
        category: str,
        kind: str,
        masses: dict[str, float],
        weight: float = 1.0,
    ) -> None:
        for key in (
            (category, kind),
            (category, "all"),
            ("all", kind),
            ("all", "all"),
        ):
            self.weight[key] += weight

            sums = self.sums.setdefault(
                key,
                Counter(),
            )

            for name, value in masses.items():
                sums[name] += weight * value

    def to_dict(self) -> dict:
        table = {}

        for key in sorted(self.weight):
            weight = self.weight[key]

            table[f"{key[0]}|{key[1]}"] = {
                "weight": weight,
            } | {
                name: total / weight
                for name, total in sorted(
                    self.sums[key].items()
                )
            }

        return table


class DrawObserver:
    def __init__(self) -> None:
        self.table = MassTable()
        self.missing: Counter = Counter()
        self.decisions = 0

    def on_deal_start(self, deal_index):
        pass

    def on_deal_end(self, **kwargs):
        pass

    def on_decision(
        self,
        *,
        game,
        information_state,
        actions,
        strategy,
    ) -> None:
        if information_state.phase != "draw":
            return

        bucket = information_state.own_hand_key

        if not isinstance(bucket, DrawHandBucket):
            return

        self.decisions += 1

        category = hand_category(bucket)

        if strategy is None:
            # The evaluator plays uniformly here.
            self.missing[category] += 1

            strategy = {
                action: 1.0 / len(actions)
                for action in actions
            }

            kind = "missing"

        else:
            kind = (
                "near_uniform"
                if _is_near_uniform(strategy)
                else "trained"
            )

        self.table.add(
            category=category,
            kind=kind,
            masses=strategy_masses(
                bucket,
                strategy,
            ),
        )


# ----------------------------------------------------------------
# Bucket resolution
# ----------------------------------------------------------------


def bucket_resolution() -> dict:
    """
    How many distinct exact rank patterns (no-pair,
    no straight / flush ignored) each no-pair bucket
    rank-class pattern merges, e.g. 8-5-4-3-2 and
    9-5-4-3-2 both map to (0, 0, 1, 1, 3).
    """
    from itertools import combinations

    from solver.draw_hand_bucket import _rank_class

    by_classes: dict[tuple, list] = {}

    for ranks in combinations(range(2, 15), 5):
        classes = tuple(
            _rank_class(rank)
            for rank in ranks
        )

        by_classes.setdefault(
            classes,
            [],
        ).append(ranks)

    sizes = sorted(
        len(value)
        for value in by_classes.values()
    )

    # For each no-pair rank-class pattern and each
    # one-card discard position, do its member rank
    # sets disagree on whether the kept four cards are
    # a straight draw (four distinct ranks within a
    # span of 5, so one card can make a straight)?
    def straight_draw(ranks) -> bool:
        return max(ranks) - min(ranks) <= 4

    ambiguous_pairs = 0
    ambiguous_rank_sets = 0
    total_pairs = 0

    for members in by_classes.values():
        for position in range(5):
            total_pairs += 1

            outcomes = {
                straight_draw(
                    ranks[:position] + ranks[position + 1:]
                )
                for ranks in members
            }

            if len(outcomes) > 1:
                ambiguous_pairs += 1
                ambiguous_rank_sets += len(members)

    examples = {
        "made_8_vs_9 (0,0,1,1,3)": [
            "-".join(
                "23456789TJQKA"[rank - 2]
                for rank in reversed(ranks)
            )
            for ranks in by_classes.get(
                (0, 0, 1, 1, 3),
                [],
            )
        ],
    }

    return {
        "no_pair_rank_sets": sum(sizes),
        "rank_class_patterns": len(sizes),
        "max_merged": sizes[-1],
        "patterns_merging_more_than_one": sum(
            1
            for size in sizes
            if size > 1
        ),
        "one_card_discards": total_pairs,
        "straight_draw_ambiguous_discards": (
            ambiguous_pairs
        ),
        "straight_draw_ambiguous_rank_set_discards": (
            ambiguous_rank_sets
        ),
        "examples": examples,
    }


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="B2 draw-decision sanity report."
    )

    parser.add_argument("checkpoint")

    parser.add_argument(
        "--deals",
        type=int,
        default=20_000,
        help="Self-play deals for reach weighting.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2027,
        help=(
            "Same default as evaluate_checkpoint, "
            "so the deals match its coverage section."
        ),
    )

    parser.add_argument(
        "--out-dir",
        default="experiments/eval",
    )

    return parser.parse_args()


def print_table(
    title: str,
    table: dict,
) -> None:
    print()
    print(title)
    print(
        f"  {'category|kind':<34} {'weight':>9} "
        f"{'mistake':>8} {'brk_low':>8} "
        f"{'pair':>7} {'high*':>7} {'snow':>7} "
        f"{'E[draw]':>8}"
    )

    for key, row in table.items():
        print(
            f"  {key:<34} {row['weight']:>9,.0f} "
            f"{row['any_mistake']:>8.1%} "
            f"{row['break_made_low']:>8.1%} "
            f"{row['keep_pair']:>7.1%} "
            f"{row['keep_high']:>7.1%} "
            f"{row['snow']:>7.1%} "
            f"{row['expected_draw_count']:>8.2f}"
        )


def main() -> None:
    args = parse_args()

    from solver.strategy_checkpoint import (
        load_strategy_checkpoint,
    )

    print(f"Loading {args.checkpoint} ...", flush=True)

    loaded = load_strategy_checkpoint(
        args.checkpoint
    )

    setup = setup_from_metadata(
        loaded.metadata
    )

    if setup.abstraction != "bucket":
        raise SystemExit(
            "Only bucket checkpoints are supported."
        )

    started = perf_counter()

    static = MassTable()

    for (
        state,
        strategy,
    ) in _stored_strategies(
        loaded.strategy_index
    ).items():
        if state.phase != "draw":
            continue

        bucket = state.own_hand_key

        static.add(
            category=hand_category(bucket),
            kind=(
                "near_uniform"
                if _is_near_uniform(strategy)
                else "trained"
            ),
            masses=strategy_masses(
                bucket,
                strategy,
            ),
        )

    print(
        f"Self-play reach weighting "
        f"({args.deals:,} deals) ...",
        flush=True,
    )

    observer = DrawObserver()

    make_profile_evaluator(
        loaded.strategy_index,
        setup,
        random_seed=derive_seed(
            args.seed,
            "coverage",
            "policy",
        ),
    ).evaluate(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=deck_seed_base(
                args.seed,
                "coverage",
            ),
        ),
        deals=args.deals,
        observer=observer,
    )

    report = {
        "checkpoint": Path(args.checkpoint).name,
        "max_draw": setup.max_draw,
        "deals": args.deals,
        "seed": args.seed,
        "draw_decisions": observer.decisions,
        "missing_draw_decisions": dict(
            sorted(observer.missing.items())
        ),
        "static": static.to_dict(),
        "reach_weighted": observer.table.to_dict(),
        "bucket_resolution": bucket_resolution(),
        "elapsed_s": perf_counter() - started,
    }

    print(
        f"\n{report['checkpoint']}  max_draw="
        f"{report['max_draw']}  draw decisions "
        f"{observer.decisions:,}"
    )

    print_table(
        "STATIC (every stored draw state, unweighted)",
        report["static"],
    )

    print_table(
        "REACH-WEIGHTED (draw decisions in self-play; "
        "missing = uniform fallback)",
        report["reach_weighted"],
    )

    resolution = report["bucket_resolution"]

    print()
    print(
        "BUCKET RESOLUTION: "
        f"{resolution['no_pair_rank_sets']:,} no-pair "
        f"rank sets fall into "
        f"{resolution['rank_class_patterns']:,} rank-class "
        f"patterns (largest merges "
        f"{resolution['max_merged']})"
    )

    print(
        "  (structure only, not evidence of strategic loss; "
        "see docs/proposals/B2-draw-analysis.md 2.1)\n"
        "  one-card discards whose 'kept four is a "
        "straight draw' answer differs inside a pattern: "
        f"{resolution['straight_draw_ambiguous_discards']:,}"
        f" of {resolution['one_card_discards']:,} "
        f"(covering "
        f"{resolution['straight_draw_ambiguous_rank_set_discards']:,}"
        f" of {resolution['no_pair_rank_sets'] * 5:,} "
        "rank-set discards)"
    )

    for name, hands in resolution["examples"].items():
        print(f"  {name}: {', '.join(hands)}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    name = report["checkpoint"]

    for suffix in (".gz", ".chk"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    out_path = out_dir / (
        f"draw_decisions__{name}__s{args.seed}.json"
    )

    out_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
