"""
One external-sampling MCCFR run, two average strategies
(docs/proposals/CFR-average-weighting.md, day74).

    current  the trainer's average: accumulated at the traverser's own
             nodes with weight = own reach. Its expected per-iteration
             weight also carries the opponent's reach, which changes
             over iterations.
    simple   Lanctot et al. (2009) simple averaging: at the opponent's
             (sampled) nodes, add the current strategy with weight 1.
             Expected weight = own reach x chance, as CFR's average needs.

Regrets, sampling and node creation are those of the unmodified trainer,
so the two checkpoints differ only in how the average is accumulated
(one variable). Nodes never visited as an opponent node have no simple
average and are saved as uniform.

    python -m scripts.compare_average_modes --iterations 2000,8000 \
        --out-dir experiments/average_modes

Writes <out-dir>/<label>__current__<iters>.chk.gz and __simple__ for
each milestone, plus a JSON summary of strategy distances.
"""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.bet_sizing import (  # noqa: E402
    FAST_BET_SIZING,
    FULL_BET_SIZING,
)
from solver.cfr_trainer import CFRTrainer  # noqa: E402
from solver.game_state import GameConfig  # noqa: E402
from solver.single_draw_game import SingleDrawGame  # noqa: E402


class DualAverageTrainer(CFRTrainer):
    """
    The unmodified trainer plus a side table of simple averages.
    Only observes: never changes regrets, sampling or node creation.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self.simple_sums: dict[int, list] = {}
        self._last_node = None

    def _get_node(self, **kwargs):
        node = super()._get_node(**kwargs)
        self._last_node = node
        return node

    def _sample_action(self, *, actions, strategy):
        # In external sampling, _sample_action is called only at the
        # non-traverser's nodes, right after _get_node for that node.
        node = self._last_node
        entry = self.simple_sums.get(id(node))

        if entry is None:
            entry = [node, {action: 0.0 for action in node.actions}]
            self.simple_sums[id(node)] = entry

        sums = entry[1]

        for action, probability in strategy.items():
            sums[action] += probability

        return super()._sample_action(
            actions=actions,
            strategy=strategy,
        )


def save_simple_checkpoint(
    trainer: DualAverageTrainer,
    path: Path,
) -> None:
    """Swap the simple sums in, save, swap the originals back."""
    saved: list[tuple] = []

    for node in trainer.node_store.nodes.values():
        saved.append(
            (node, node.strategy_sum, node.strategy_weight_sum)
        )
        entry = trainer.simple_sums.get(id(node))
        sums = (
            dict(entry[1])
            if entry is not None
            else {action: 0.0 for action in node.actions}
        )
        node.strategy_sum = sums
        node.strategy_weight_sum = sum(sums.values())

    try:
        trainer.save_checkpoint(path)
    finally:
        for node, strategy_sum, weight_sum in saved:
            node.strategy_sum = strategy_sum
            node.strategy_weight_sum = weight_sum


def distances(trainer: DualAverageTrainer) -> dict:
    """
    Total-variation distance between the two averages, and of each
    from uniform, over nodes that have both averages. Unweighted and
    weighted by simple-average visit count.
    """
    count = 0
    weight_total = 0.0
    totals = {"tv": 0.0, "current_vs_uniform": 0.0, "simple_vs_uniform": 0.0}
    weighted = dict.fromkeys(totals, 0.0)

    for node, sums in trainer.simple_sums.values():
        visits = sum(sums.values())

        if visits <= 0 or sum(node.strategy_sum.values()) <= 0:
            continue

        current = node.average_strategy()
        simple = {a: v / visits for a, v in sums.items()}
        uniform = 1.0 / len(node.actions)

        values = {
            "tv": 0.5 * sum(
                abs(current[a] - simple[a]) for a in node.actions
            ),
            "current_vs_uniform": 0.5 * sum(
                abs(current[a] - uniform) for a in node.actions
            ),
            "simple_vs_uniform": 0.5 * sum(
                abs(simple[a] - uniform) for a in node.actions
            ),
        }

        count += 1
        weight_total += visits

        for key, value in values.items():
            totals[key] += value
            weighted[key] += visits * value

    return {
        "nodes_compared": count,
        "unweighted": {k: v / count for k, v in totals.items()} if count else None,
        "visit_weighted": (
            {k: v / weight_total for k, v in weighted.items()}
            if weight_total
            else None
        ),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--iterations", required=True,
                        help="Comma-separated milestones, e.g. 2000,8000")
    parser.add_argument("--max-draw", type=int, default=5)
    parser.add_argument("--abstraction", default="bucket",
                        choices=("bucket", "exact"))
    parser.add_argument("--bet-sizing", default="fast",
                        choices=("fast", "full"))
    parser.add_argument("--stack", type=float, default=20.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--label", default="avgmodes")
    args = parser.parse_args(argv)

    milestones = sorted({int(x) for x in args.iterations.split(",")})
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config = GameConfig(
        player_count=2,
        starting_stack=args.stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    trainer = DualAverageTrainer(
        max_draw=args.max_draw,
        raise_sizes=None,
        bet_sizing_policy=(
            FAST_BET_SIZING if args.bet_sizing == "fast" else FULL_BET_SIZING
        ),
        abstraction=args.abstraction,
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=args.seed,
        game_config=config,
    )

    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter
        counter += 1
        return SingleDrawGame(
            config=config,
            button_seat=0,
            deck_seed=args.seed + counter,
        )

    summary = {"arguments": vars(args), "milestones": []}
    done = 0
    started = perf_counter()

    for milestone in milestones:
        trainer.train(factory, iterations=milestone - done)
        done = milestone

        stem = f"{args.label}__{{mode}}__{milestone:06d}.chk.gz"
        trainer.save_checkpoint(out_dir / stem.format(mode="current"))
        save_simple_checkpoint(trainer, out_dir / stem.format(mode="simple"))

        record = {
            "iterations": milestone,
            "nodes": len(trainer.node_store),
            "elapsed_s": round(perf_counter() - started, 1),
            **distances(trainer),
        }
        summary["milestones"].append(record)
        print(json.dumps(record), flush=True)

        (out_dir / f"{args.label}__summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
