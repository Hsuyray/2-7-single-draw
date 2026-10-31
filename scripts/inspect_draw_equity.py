"""
Exact draw-equity oracle and bucket regret (workstream B2).

Question: for a 5-card holding, which draw option (stand pat or a
discard) has the highest showdown equity, and does the
DrawHandBucket abstraction force hands with different best options
into one information state?

Equity = P(win) + 0.5 P(tie) at showdown against a reference
opponent situation, by enumerating replacement cards from the live
deck (both hands' cards and the discards are dead). It counts every
way a draw can pair, straighten or flush. It ignores betting, so it
is a first-order reference for the draw choice, not the solver's EV:
an option that is clearly worse in every reasonable situation is a
mistake; close calls are for the solver to decide.

Reference opponent situations (the in-position player sees how many
cards the opponent drew before choosing):
    pat 9-7-6-4-2, pat 8-6-4-3-2, pat 7-6-4-3-2,
    draws 1 to 7-5-3-2, draws 1 to 8-6-4-2.

Bucket regret: hands sharing a DrawHandBucket must play the same
bucket-canonical action. For each bucket and situation, the common
action is the one with the highest mean equity over the bucket's
hands; regret = a hand's best equity minus its equity with the common
action. Large regret means the bucket merges hands that need
different draws.

Scope (v0): no-pair, non-straight holdings (1,278 rank sets, suits
fixed to avoid flushes), options = stand pat, all 1-card and all
2-card discards (16). Draws of 3+ cards are not compared yet.

    python -m scripts.inspect_draw_equity
    python -m scripts.inspect_draw_equity --limit-top 9   # made 9-or-better only
"""

import argparse
import json
import random
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from time import perf_counter

from solver.actions import (
    DiscardAction,
)
from solver.bucket_hand_codec import (
    actual_discard_action_for_bucket_hand,
)
from solver.draw_hand_bucket import (
    draw_hand_bucket,
)
from solver.hand import (
    Hand,
)
from solver.made_hand_bucket import (
    made_hand_bucket,
)


RANKS = "23456789TJQKA"
SUITS = "shdc"

# Card = (rank value 2..14, suit index 0..3)
DECK = [
    (rank, suit)
    for rank in range(2, 15)
    for suit in range(4)
]

SITUATIONS = {
    "opp_pat_97642": ("pat", (9, 7, 6, 4, 2)),
    "opp_pat_86432": ("pat", (8, 6, 4, 3, 2)),
    "opp_pat_76432": ("pat", (7, 6, 4, 3, 2)),
    "opp_draw1_7532": ("draw", (7, 5, 3, 2)),
    "opp_draw1_8642": ("draw", (8, 6, 4, 2)),
}

# 2-card hero draws against a drawing opponent are paired with
# this many opponent replacement cards per hero draw (sampled with
# a fixed seed); everything else is exact.
OPPONENT_SAMPLES_PER_DRAW = 6


# ----------------------------------------------------------------
# Scoring (2-7: depends only on ranks and whether it is a flush)
# ----------------------------------------------------------------


_SCORE_CACHE: dict = {}


def card_text(card) -> str:
    return RANKS[card[0] - 2] + SUITS[card[1]]


def score(cards) -> tuple:
    ranks = tuple(sorted(card[0] for card in cards))
    flush = len({card[1] for card in cards}) == 1
    key = (ranks, flush)

    cached = _SCORE_CACHE.get(key)

    if cached is None:
        cached = made_hand_bucket(
            Hand.from_strings(
                *(card_text(card) for card in cards)
            )
        ).score
        _SCORE_CACHE[key] = cached

    return cached


# ----------------------------------------------------------------
# Hands and situations
# ----------------------------------------------------------------


def assign_suits(
    ranks,
    *,
    avoid=frozenset(),
):
    """
    Cards with the given ranks, no flush, avoiding the given
    cards. Deterministic.
    """
    cards = []
    counts = defaultdict(int)

    for rank in ranks:
        for offset in range(4):
            suit = (len(cards) + offset) % 4
            card = (rank, suit)

            if card in avoid or card in cards:
                continue

            cards.append(card)
            counts[suit] += 1
            break

        else:
            raise ValueError(
                f"Cannot place rank {rank}."
            )

    if len(ranks) == 5 and len(counts) == 1:
        raise ValueError("Unexpected flush.")

    return cards


def equity(
    hero_kept,
    hero_draw: int,
    opponent,
    dead,
    rng: random.Random,
) -> float:
    kind, opponent_cards = opponent

    live = [
        card
        for card in DECK
        if card not in dead
    ]

    total = 0.0
    count = 0

    for drawn in combinations(live, hero_draw):
        hero_score = score(
            list(hero_kept) + list(drawn)
        )

        if kind == "pat":
            finals = [opponent_cards]

        else:
            rest = [
                card
                for card in live
                if card not in drawn
            ]

            if hero_draw >= 2:
                picks = rng.sample(
                    rest,
                    OPPONENT_SAMPLES_PER_DRAW,
                )
            else:
                picks = rest

            finals = [
                list(opponent_cards) + [card]
                for card in picks
            ]

        for final in finals:
            opponent_score = score(final)

            if hero_score < opponent_score:
                total += 1.0
            elif hero_score == opponent_score:
                total += 0.5

            count += 1

    return total / count


OPTIONS = tuple(
    DiscardAction(indices)
    for size in (0, 1, 2)
    for indices in combinations(range(5), size)
)


def option_equities(
    hero_cards,
    situation: str,
    rng: random.Random,
) -> dict[DiscardAction, float]:
    """
    Equity per bucket-canonical option for one hand.
    """
    kind, opponent_ranks = SITUATIONS[situation]

    opponent_cards = assign_suits(
        opponent_ranks,
        avoid=frozenset(hero_cards),
    )

    hand = Hand.from_strings(
        *(card_text(card) for card in hero_cards)
    )

    results = {}

    for option in OPTIONS:
        physical = actual_discard_action_for_bucket_hand(
            hand=hand,
            action=option,
        )

        kept = [
            card
            for index, card in enumerate(hero_cards)
            if index not in physical.discard_indices
        ]

        results[option] = equity(
            kept,
            option.draw_count,
            (kind, opponent_cards),
            dead=set(hero_cards) | set(opponent_cards),
            rng=rng,
        )

    return results


def option_label(
    ranks_low_to_high,
    option: DiscardAction,
) -> str:
    if option.draw_count == 0:
        return "pat"

    return "throw " + "".join(
        RANKS[ranks_low_to_high[position] - 2]
        for position in reversed(option.discard_indices)
    )


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="B2 draw-equity oracle and bucket regret."
    )

    parser.add_argument(
        "--limit-top",
        type=int,
        default=14,
        help=(
            "Only holdings whose highest card is at "
            "most this rank (9 = made 9-or-better)."
        ),
    )

    parser.add_argument(
        "--situations",
        default=",".join(SITUATIONS),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2027,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Buckets to list by regret.",
    )

    parser.add_argument(
        "--out-dir",
        default="experiments/eval",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    situations = args.situations.split(",")

    rank_sets = [
        ranks
        for ranks in combinations(range(2, 15), 5)
        if max(ranks) - min(ranks) != 4
        and max(ranks) <= args.limit_top
    ]

    print(
        f"{len(rank_sets):,} no-pair holdings, "
        f"{len(OPTIONS)} options, situations "
        f"{situations}",
        flush=True,
    )

    started = perf_counter()

    # bucket -> situation -> list of (ranks, equities)
    by_bucket: dict = defaultdict(
        lambda: defaultdict(list)
    )

    for number, ranks in enumerate(rank_sets):
        hero_cards = assign_suits(ranks)

        bucket = draw_hand_bucket(
            Hand.from_strings(
                *(card_text(card) for card in hero_cards)
            )
        )

        for situation in situations:
            # Deterministic per (seed, holding, situation);
            # not hash(), which depends on PYTHONHASHSEED.
            rng = random.Random(
                f"{args.seed}|{ranks}|{situation}"
            )

            by_bucket[bucket][situation].append(
                (
                    ranks,
                    option_equities(
                        hero_cards,
                        situation,
                        rng,
                    ),
                )
            )

        if (number + 1) % 100 == 0:
            print(
                f"  {number + 1:,}/{len(rank_sets):,} "
                f"({perf_counter() - started:.0f}s)",
                flush=True,
            )

    rows = []
    best_counts: dict = defaultdict(lambda: defaultdict(int))

    for bucket, per_situation in by_bucket.items():
        for situation, members in per_situation.items():
            mean = {
                option: sum(
                    equities[option]
                    for _, equities in members
                )
                / len(members)
                for option in OPTIONS
            }

            common = max(
                OPTIONS,
                key=lambda option: (
                    mean[option],
                    -option.draw_count,
                ),
            )

            regrets = []

            for ranks, equities in members:
                best = max(
                    OPTIONS,
                    key=lambda option: (
                        equities[option],
                        -option.draw_count,
                    ),
                )

                best_counts[situation][
                    "pat" if best.draw_count == 0
                    else f"draw{best.draw_count}"
                ] += 1

                regrets.append(
                    (
                        equities[best] - equities[common],
                        ranks,
                        best,
                    )
                )

            regrets.sort(reverse=True)

            worst_regret, worst_ranks, worst_best = regrets[0]

            rows.append(
                {
                    "bucket_rank_classes": list(
                        bucket.rank_classes
                    ),
                    "situation": situation,
                    "members": len(members),
                    "common_action": list(
                        common.discard_indices
                    ),
                    "mean_regret": sum(
                        regret for regret, _, _ in regrets
                    )
                    / len(regrets),
                    "max_regret": worst_regret,
                    "worst_hand": "-".join(
                        RANKS[rank - 2]
                        for rank in reversed(worst_ranks)
                    ),
                    "worst_hand_best": option_label(
                        worst_ranks,
                        worst_best,
                    ),
                    "worst_hand_forced": option_label(
                        worst_ranks,
                        common,
                    ),
                }
            )

    rows.sort(
        key=lambda row: (
            -row["max_regret"],
            row["situation"],
            row["bucket_rank_classes"],
        )
    )

    hands_total = len(rank_sets)

    summary = {}

    for situation in situations:
        selected = [
            row
            for row in rows
            if row["situation"] == situation
        ]

        weighted = sum(
            row["mean_regret"] * row["members"]
            for row in selected
        ) / sum(row["members"] for row in selected)

        summary[situation] = {
            "hand_weighted_mean_regret": weighted,
            "buckets_with_max_regret_over_0.05": sum(
                1
                for row in selected
                if row["max_regret"] > 0.05
            ),
            "buckets": len(selected),
            "best_option_counts": dict(
                best_counts[situation]
            ),
        }

    print()
    print(
        f"{'situation':<17} {'mean regret':>12} "
        f"{'buckets >0.05':>14} {'best: pat/draw1/draw2'}"
    )

    for situation, row in summary.items():
        counts = row["best_option_counts"]

        print(
            f"{situation:<17} "
            f"{row['hand_weighted_mean_regret']:>12.4f} "
            f"{row['buckets_with_max_regret_over_0.05']:>6}"
            f"/{row['buckets']:<7} "
            f"{counts.get('pat', 0)}/"
            f"{counts.get('draw1', 0)}/"
            f"{counts.get('draw2', 0)}"
        )

    print()
    print(f"Top {args.top} bucket x situation by max regret:")

    for row in rows[: args.top]:
        print(
            f"  {str(tuple(row['bucket_rank_classes'])):<17} "
            f"{row['situation']:<16} n={row['members']:<3} "
            f"max {row['max_regret']:.3f} "
            f"mean {row['mean_regret']:.3f}  "
            f"{row['worst_hand']}: best {row['worst_hand_best']}, "
            f"forced {row['worst_hand_forced']}"
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / (
        f"draw_equity__top{args.limit_top}__s{args.seed}.json"
    )

    out_path.write_text(
        json.dumps(
            {
                "parameters": {
                    "limit_top": args.limit_top,
                    "situations": situations,
                    "seed": args.seed,
                    "options": [
                        list(option.discard_indices)
                        for option in OPTIONS
                    ],
                    "opponent_samples_per_draw": (
                        OPPONENT_SAMPLES_PER_DRAW
                    ),
                },
                "holdings": hands_total,
                "summary": summary,
                "rows": rows,
                "elapsed_s": perf_counter() - started,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nWrote {out_path} ({perf_counter() - started:.0f}s)")


if __name__ == "__main__":
    main()
