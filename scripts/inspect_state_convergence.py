"""
Convergence diagnostics from a C1 training state (C1 step 5, A2).

A checkpoint stores only the average strategy, so A2 reports
"current-vs-average: unavailable". A C1 training state
(`solutions/<id>/training.state.gz`) stores the whole trainer:
regret sums, strategy sums and visit counters. This script reads it
and measures, on the decisions actually reached in self-play:

  current_vs_average   L1 distance between the current strategy
                       (regret matching) and the average strategy.
                       Large values mean the strategy is still
                       moving.
  average_vs_uniform   total variation distance of the average
                       strategy from uniform, 0 (uniform) .. 1 - 1/n.
                       A continuous replacement for the binary
                       1e-6 near-uniform test (B2 found that test
                       counts barely-moved strategies as trained).
  current_vs_uniform   the same for the current strategy.
  strategy updates     how many times each reached information set
                       has accumulated strategy (median, share below
                       10 and 100).

Self-play uses the same deals, policy seed and action path as the
coverage section of scripts.evaluate_checkpoint, and looks strategies
up directly in the trainer's node store. That gives exactly the
checkpoint's average strategies (a checkpoint is
`node.average_strategy()` of every node) without loading the
checkpoint, which at v2 scale needs ~8 GB on its own. With --report,
the matched / missing decision counts are checked against that
report's coverage section; they must be identical.

    python -m scripts.inspect_state_convergence solutions/hu_d5_full_bucket_s20/training.state.gz \\
        --report solutions/hu_d5_full_bucket_s20/eval/<report>.json
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter

from solver.checkpoint_evaluation import (
    PHASES,
    deck_seed_base,
    derive_seed,
    make_deal_factory,
    make_profile_evaluator,
    setup_from_metadata,
)
from solver.information_state import (
    InformationState,
)
from solver.training_run import (
    load_training_state,
)


LOW_UPDATE_COUNTS = (10, 100)
LARGE_CURRENT_VS_AVERAGE = 0.5


class NodeStoreStrategies:
    """
    Read-only stand-in for StrategyIndex backed by a
    trainer's node store: strategy_for_hand returns the
    node's average strategy, or None when the information
    set was never created.
    """

    def __init__(self, nodes) -> None:
        self.nodes = nodes

    def __len__(self) -> int:
        return len(self.nodes)

    def strategy_for_state(self, state):
        node = self.nodes.get(state)

        return (
            None
            if node is None
            else node.average_strategy()
        )

    def strategy_for_hand(
        self,
        *,
        public_node,
        observer_seat,
        hand_key,
    ):
        return self.strategy_for_state(
            InformationState(
                observer_seat=observer_seat,
                public_node=public_node,
                own_hand_key=hand_key,
            )
        )


def total_variation_from_uniform(
    strategy: dict,
) -> float:
    uniform = 1.0 / len(strategy)

    return 0.5 * sum(
        abs(probability - uniform)
        for probability in strategy.values()
    )


def l1(
    first: dict,
    second: dict,
) -> float:
    return sum(
        abs(first[action] - second[action])
        for action in first
    )


class ConvergenceObserver:
    def __init__(self, nodes) -> None:
        self.nodes = nodes
        self.matched: Counter = Counter()
        self.missing: Counter = Counter()
        self.single_action: Counter = Counter()
        self.values: dict = {}

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
        phase = information_state.phase

        if strategy is None:
            self.missing[phase] += 1
            return

        self.matched[phase] += 1

        if len(actions) <= 1:
            self.single_action[phase] += 1
            return

        node = self.nodes[information_state]

        current = node.current_strategy()

        values = self.values.setdefault(
            phase,
            {
                "current_vs_average": [],
                "average_vs_uniform": [],
                "current_vs_uniform": [],
                "strategy_updates": [],
                "visits": [],
            },
        )

        values["current_vs_average"].append(
            l1(current, strategy)
        )
        values["average_vs_uniform"].append(
            total_variation_from_uniform(strategy)
        )
        values["current_vs_uniform"].append(
            total_variation_from_uniform(current)
        )
        values["strategy_updates"].append(
            node.strategy_update_count
        )
        values["visits"].append(
            node.visit_count
        )


def summarize(values: dict) -> dict:
    summary = {
        "decisions": len(
            values["current_vs_average"]
        ),
    }

    for name in (
        "current_vs_average",
        "average_vs_uniform",
        "current_vs_uniform",
    ):
        series = values[name]
        summary[f"{name}_mean"] = (
            sum(series) / len(series)
        )

    summary["current_vs_average_share_over_0.5"] = (
        sum(
            1
            for value in values["current_vs_average"]
            if value > LARGE_CURRENT_VS_AVERAGE
        )
        / len(values["current_vs_average"])
    )

    updates = values["strategy_updates"]

    summary["strategy_updates_median"] = median(
        updates
    )

    for limit in LOW_UPDATE_COUNTS:
        summary[f"strategy_updates_share_below_{limit}"] = (
            sum(1 for value in updates if value < limit)
            / len(updates)
        )

    summary["visits_median"] = median(
        values["visits"]
    )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Current-vs-average and related "
            "convergence diagnostics from a C1 "
            "training state."
        )
    )

    parser.add_argument("state")

    parser.add_argument(
        "--deals",
        type=int,
        default=20_000,
        help=(
            "Self-play deals (evaluate_checkpoint "
            "standard preset: 20,000)."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2027,
    )

    parser.add_argument(
        "--report",
        help=(
            "evaluate_checkpoint report of the same "
            "strategy, same seed and deals: the "
            "matched / missing counts must match its "
            "coverage section."
        ),
    )

    parser.add_argument(
        "--out-dir",
        help=(
            "Default: the state file's directory "
            "(solutions/<id>/eval if it exists)."
        ),
    )

    return parser.parse_args()


def check_against_report(
    observer: ConvergenceObserver,
    report_path: str,
    *,
    deals: int,
    seed: int,
) -> list[str]:
    report = json.loads(
        Path(report_path).read_text(
            encoding="utf-8"
        )
    )

    coverage = report.get("coverage")

    if coverage is None:
        return ["report has no coverage section"]

    problems = []

    if coverage["deals"] != deals:
        problems.append(
            f"report used {coverage['deals']} deals, "
            f"this run {deals}"
        )

    if report["parameters"]["seed"] != seed:
        problems.append(
            f"report seed {report['parameters']['seed']}, "
            f"this run {seed}"
        )

    if problems:
        return problems

    for phase, stats in coverage["by_phase"].items():
        for name, counter in (
            ("matched", observer.matched),
            ("missing", observer.missing),
        ):
            if stats[name] != counter[phase]:
                problems.append(
                    f"{phase} {name}: report "
                    f"{stats[name]}, state {counter[phase]}"
                )

    return problems


def main() -> None:
    args = parse_args()

    state_path = Path(args.state)

    print(f"Loading {state_path} ...", flush=True)

    started = perf_counter()

    state = load_training_state(state_path)
    trainer = state.trainer

    load_seconds = perf_counter() - started

    nodes = trainer.node_store.nodes

    setup = setup_from_metadata(
        trainer.checkpoint_metadata()
    )

    print(
        f"  {trainer.completed_iterations:,} iterations, "
        f"{len(nodes):,} information sets, "
        f"loaded in {load_seconds:.0f}s",
        flush=True,
    )

    print(
        f"Self-play ({args.deals:,} deals, seed "
        f"{args.seed}) ...",
        flush=True,
    )

    observer = ConvergenceObserver(nodes)

    # Same derivation as checkpoint_evaluation.evaluate_coverage.
    make_profile_evaluator(
        NodeStoreStrategies(nodes),
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

    by_phase = {
        phase: summarize(observer.values[phase])
        for phase in PHASES
        if phase in observer.values
    }

    all_values: dict = {}

    for values in observer.values.values():
        for name, series in values.items():
            all_values.setdefault(name, []).extend(series)

    report = {
        "state": state_path.name,
        "completed_iterations": (
            trainer.completed_iterations
        ),
        "information_sets": len(nodes),
        "deals": args.deals,
        "seed": args.seed,
        "matched": dict(sorted(observer.matched.items())),
        "missing": dict(sorted(observer.missing.items())),
        "single_action": dict(
            sorted(observer.single_action.items())
        ),
        "overall": summarize(all_values),
        "by_phase": by_phase,
        "definitions": {
            "current_vs_average": (
                "L1 distance, 0..2, between regret-"
                "matching current and average strategy"
            ),
            "average_vs_uniform": (
                "total variation distance from uniform, "
                "0..1-1/n"
            ),
            "weighting": (
                "every multi-action decision reached in "
                "self-play counts once"
            ),
        },
    }

    check = None

    if args.report:
        problems = check_against_report(
            observer,
            args.report,
            deals=args.deals,
            seed=args.seed,
        )

        check = {
            "report": Path(args.report).name,
            "problems": problems,
        }

    report["report_check"] = check

    print()
    print(
        f"{'phase':<17} {'decisions':>9} "
        f"{'cur-vs-avg':>10} {'>0.5':>6} "
        f"{'avg-vs-unif':>11} {'cur-vs-unif':>11} "
        f"{'upd med':>8} {'upd<10':>7} {'upd<100':>8}"
    )

    for name, row in [
        *by_phase.items(),
        ("all", report["overall"]),
    ]:
        print(
            f"{name:<17} {row['decisions']:>9,} "
            f"{row['current_vs_average_mean']:>10.3f} "
            f"{row['current_vs_average_share_over_0.5']:>6.1%} "
            f"{row['average_vs_uniform_mean']:>11.3f} "
            f"{row['current_vs_uniform_mean']:>11.3f} "
            f"{row['strategy_updates_median']:>8,.0f} "
            f"{row['strategy_updates_share_below_10']:>7.1%} "
            f"{row['strategy_updates_share_below_100']:>8.1%}"
        )

    if check is not None:
        print()

        if check["problems"]:
            print(
                "REPORT CHECK FAILED (the decisions differ "
                "from the report's coverage section):"
            )

            for line in check["problems"]:
                print("  " + line)

        else:
            print(
                "REPORT CHECK OK: matched / missing "
                "decisions equal the report's coverage."
            )

    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif (state_path.parent / "eval").is_dir():
        out_dir = state_path.parent / "eval"
    else:
        out_dir = state_path.parent

    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / (
        f"convergence__{trainer.completed_iterations:06d}"
        f"__s{args.seed}.json"
    )

    report["elapsed_s"] = perf_counter() - started

    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    print(f"\nWrote {out_path}")

    if check is not None and check["problems"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
