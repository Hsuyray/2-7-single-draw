"""
SBR budget experiment (A2, docs/A2_DESIGN.md section 11).

Question: why is the sampled-best-response gain negative at the
standard budget (100 response deals)? Two hypotheses:

  overfit   the pure response learned on few deals does not
            generalise; gain should rise with response deals.
  samples   (added day50, after overfit and fallback were both
            falsified) learned states grow about linearly with
            response deals, so each state's action is chosen from
            about one sampled value per action however many deals
            are used. Measured here as visits per learned state.
  fallback  on validation states it never learned, the responder
            plays the profile's highest-probability action. For a
            uniform or missing strategy that is the first legal
            action: FOLD when facing a bet, stand pat on the draw.
            That alone can make the gain negative.

For each response-deal budget, seat and repeat this runs the
unchanged SampledBestResponse once. In the same validation pass
it also plays a probe variant on its own RNG, identical except
that the fallback samples from the profile's strategy instead of
taking the argmax. The production numbers are therefore exactly
those of scripts.evaluate_checkpoint with the same seed (checked
with --check-report), and the probe never changes them.

Seeds match evaluate_checkpoint: response decks for (seat, repeat)
start at the same seed for every budget, so a larger budget's deals
contain the smaller budget's deals; validation deals are shared.

    python -m scripts.inspect_sbr_budget checkpoints/production_v1.chk.gz
    python -m scripts.inspect_sbr_budget checkpoints/production_v1.chk.gz \
        --check-report experiments/eval/production_v1__9069fb8b__standard__s2027.json

Not an algorithm change to solver/best_response.py; the probe
lives only in this script.
"""

import argparse
import json
import random
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from time import perf_counter

from solver.best_response import (
    SampledBestResponse,
)
from solver.checkpoint_evaluation import (
    AssumedGameConfig,
    deck_seed_base,
    derive_seed,
    make_deal_factory,
    setup_from_metadata,
)
from solver.information_state import (
    InformationState,
)
from solver.single_draw_game import (
    GamePhase,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)
from solver.strategy_profile_evaluator import (
    standard_error,
)
from solver.terminal_utility import (
    terminal_utility,
)


class FallbackProbeSBR(SampledBestResponse):
    """
    SampledBestResponse plus a measurement-only
    probe. Training, the production validation
    rollouts and the main RNG are untouched; the
    probe uses probe_seed's own RNG on copies of
    the validation games.
    """

    def __init__(
        self,
        *,
        probe_seed: int,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self._probe_random = random.Random(
            probe_seed
        )

        self.probe_count = 0
        self.probe_total = 0.0
        self.probe_sum_squares = 0.0
        self.probe_gain_sum_squares = 0.0

        self._last_baseline: float | None = None

        # Responder-state visits during training,
        # summed over sweeps (measurement only).
        self.training_visits: Counter = Counter()

    def _sampled_response_traversal(
        self,
        *,
        game,
        **kwargs,
    ) -> float:
        if (
            game.phase
            != GamePhase.COMPLETE
            and game.acting_seat
            == self.responder_seat
        ):
            self.training_visits[
                InformationState.from_game(
                    game,
                    observer_seat=(
                        self.responder_seat
                    ),
                    abstraction=self.abstraction,
                )
            ] += 1

        return super()._sampled_response_traversal(
            game=game,
            **kwargs,
        )

    def _sample_profile_rollout(
        self,
        game,
    ) -> float:
        value = super()._sample_profile_rollout(
            game
        )

        self._last_baseline = value

        return value

    def _sample_response_rollout(
        self,
        *,
        game,
        policy,
    ) -> float:
        probe_game = deepcopy(game)

        value = super()._sample_response_rollout(
            game=game,
            policy=policy,
        )

        probe_value = self._probe_rollout(
            game=probe_game,
            policy=policy,
        )

        gain = (
            probe_value
            - self._last_baseline
        )

        self.probe_count += 1
        self.probe_total += probe_value
        self.probe_sum_squares += (
            probe_value * probe_value
        )
        self.probe_gain_sum_squares += (
            gain * gain
        )

        return value

    def _probe_rollout(
        self,
        *,
        game,
        policy,
    ) -> float:
        while (
            game.phase
            != GamePhase.COMPLETE
        ):
            acting_seat = game.acting_seat

            actions = self._solver_actions(
                game
            )

            state = InformationState.from_game(
                game,
                observer_seat=acting_seat,
                abstraction=self.abstraction,
            )

            action = None

            if (
                acting_seat
                == self.responder_seat
            ):
                learned = policy.get(state)

                if learned in actions:
                    action = learned

            if action is None:
                # Responder fallback and opponent
                # both sample the profile.
                strategy = (
                    self._normalized_strategy(
                        actions=actions,
                        strategy=(
                            self.strategy_index
                            .strategy_for_state(
                                state
                            )
                        ),
                    )
                )

                action = self._probe_sample(
                    actions=actions,
                    strategy=strategy,
                )

            game = self._apply_action(
                game=game,
                action=action,
            )

        return terminal_utility(
            game,
            seat=self.responder_seat,
        )

    def _probe_sample(
        self,
        *,
        actions,
        strategy,
    ):
        threshold = (
            self._probe_random.random()
        )

        cumulative = 0.0

        for action in actions:
            cumulative += strategy[action]

            if threshold <= cumulative:
                return action

        return actions[-1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "SBR gain vs response-deal budget, "
            "with an argmax-vs-sample fallback "
            "probe."
        )
    )

    parser.add_argument("checkpoint")

    parser.add_argument(
        "--response-deals",
        default="100,300,1000",
        help="Comma-separated budgets.",
    )

    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--validation-deals",
        type=int,
        default=1_000,
    )

    parser.add_argument(
        "--sweeps",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--seats",
        default="0,1",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2027,
    )

    parser.add_argument(
        "--assume-config",
        help="STACK,SB,BB,ANTE for old checkpoints.",
    )

    parser.add_argument(
        "--check-report",
        help=(
            "evaluate_checkpoint standard report "
            "of the same checkpoint and seed; the "
            "100-deal production gains must match "
            "it exactly."
        ),
    )

    parser.add_argument(
        "--out-dir",
        default="experiments/eval",
    )

    return parser.parse_args()


def summary(
    values: list[float],
) -> dict:
    count = len(values)
    mean = sum(values) / count

    sd = (
        (
            sum(
                (value - mean) ** 2
                for value in values
            )
            / (count - 1)
        )
        ** 0.5
        if count > 1
        else 0.0
    )

    return {
        "mean": mean,
        "sd": sd,
        "min": min(values),
        "max": max(values),
    }


def run_one(
    index,
    setup,
    *,
    seed: int,
    seat: int,
    repeat: int,
    response_deals: int,
    validation_deals: int,
    sweeps: int,
) -> dict:
    optimizer = FallbackProbeSBR(
        probe_seed=derive_seed(
            seed,
            "sbr-probe",
            seat,
            repeat,
            response_deals,
        ),
        strategy_index=index,
        abstraction=setup.abstraction,
        responder_seat=seat,
        max_draw=setup.max_draw,
        raise_sizes=setup.raise_sizes,
        bet_sizing_policy=(
            setup.bet_sizing_policy
        ),
        draw_action_mode=(
            setup.draw_action_mode
        ),
        # Same derivation as
        # checkpoint_evaluation.evaluate_sampled_best_response.
        random_seed=derive_seed(
            seed,
            "sbr",
            "policy",
            seat,
            repeat,
        ),
    )

    started = perf_counter()

    result = optimizer.optimize(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=deck_seed_base(
                seed,
                "sbr",
                "response",
                seat,
                repeat,
            ),
        ),
        deals=response_deals,
        max_sweeps=sweeps,
        validation_game_factory=(
            make_deal_factory(
                setup.game_config,
                first_deck_seed=deck_seed_base(
                    seed,
                    "sbr",
                    "validation",
                ),
            )
        ),
        validation_deals=validation_deals,
    )

    elapsed = perf_counter() - started

    count = optimizer.probe_count

    probe_value = (
        optimizer.probe_total / count
    )

    probe_gain = (
        probe_value
        - result.baseline_value
    )

    decisions = (
        result.response_policy_decisions
        + result.response_fallback_decisions
    )

    # Visits per learned state per sweep: the number
    # of sampled values behind each action choice.
    per_sweep = sorted(
        count / result.sweeps
        for count in (
            optimizer.training_visits.values()
        )
    )

    return {
        "seat": seat,
        "repeat": repeat,
        "response_deals": response_deals,
        "sweeps_completed": result.sweeps,
        "information_states": (
            result.information_states
        ),
        "changed_actions": (
            result.changed_actions
        ),
        "baseline_value": (
            result.baseline_value
        ),
        "gain_argmax": result.improvement,
        "gain_argmax_se": (
            result.improvement_standard_error
        ),
        "gain_sample": probe_gain,
        "gain_sample_se": standard_error(
            mean=probe_gain,
            sum_squares=(
                optimizer.probe_gain_sum_squares
            ),
            count=count,
        ),
        "fallback_share": (
            result.response_fallback_share
        ),
        "fallback_tie_share": (
            result.response_fallback_tie_decisions
            / decisions
            if decisions
            else 0.0
        ),
        "visits_per_state_mean": (
            sum(per_sweep) / len(per_sweep)
        ),
        "visits_per_state_median": per_sweep[
            len(per_sweep) // 2
        ],
        "states_with_one_visit_share": (
            sum(
                1
                for value in per_sweep
                if value <= 1.0
            )
            / len(per_sweep)
        ),
        "states_with_at_most_three_visits_share": (
            sum(
                1
                for value in per_sweep
                if value <= 3.0
            )
            / len(per_sweep)
        ),
        "elapsed_s": elapsed,
    }


def check_against_report(
    runs: list[dict],
    report_path: str,
) -> list[str]:
    report = json.loads(
        Path(report_path).read_text(
            encoding="utf-8"
        )
    )

    sbr = report["sbr"]

    problems = []

    if (
        sbr["validation_deals"] != runs[0]["_validation_deals"]
        or sbr["max_sweeps"] != runs[0]["_sweeps"]
        or report["parameters"]["seed"] != runs[0]["_seed"]
    ):
        return [
            "report was made with different "
            "validation deals, sweeps or seed"
        ]

    expected = {
        (
            int(seat_name.split("_")[1]),
            run["repeat"],
        ): run["gain"]
        for seat_name, seat_runs in sbr[
            "runs"
        ].items()
        for run in seat_runs
    }

    for run in runs:
        if run["response_deals"] != sbr[
            "response_deals"
        ]:
            continue

        key = (
            run["seat"],
            run["repeat"],
        )

        if key not in expected:
            continue

        if run["gain_argmax"] != expected[key]:
            problems.append(
                f"seat {key[0]} repeat {key[1]}: "
                f"{run['gain_argmax']!r} != "
                f"report {expected[key]!r}"
            )

    return problems


def main() -> None:
    args = parse_args()

    budgets = [
        int(part)
        for part in args.response_deals.split(",")
    ]

    seats = [
        int(part)
        for part in args.seats.split(",")
    ]

    assumed = None

    if args.assume_config:
        values = [
            float(part)
            for part in args.assume_config.split(",")
        ]

        assumed = AssumedGameConfig(*values)

    print(
        f"Loading {args.checkpoint} ...",
        flush=True,
    )

    loaded = load_strategy_checkpoint(
        args.checkpoint
    )

    setup = setup_from_metadata(
        loaded.metadata,
        assumed=assumed,
    )

    print(
        f"budgets={budgets} repeats={args.repeats} "
        f"seats={seats} validation={args.validation_deals} "
        f"sweeps<={args.sweeps} seed={args.seed}",
        flush=True,
    )

    runs = []

    for response_deals in budgets:
        for repeat in range(args.repeats):
            for seat in seats:
                run = run_one(
                    loaded.strategy_index,
                    setup,
                    seed=args.seed,
                    seat=seat,
                    repeat=repeat,
                    response_deals=response_deals,
                    validation_deals=(
                        args.validation_deals
                    ),
                    sweeps=args.sweeps,
                )

                runs.append(run)

                print(
                    f"  deals={response_deals:>5} "
                    f"seat={seat} repeat={repeat}: "
                    f"argmax {run['gain_argmax']:+.4f} "
                    f"(se {run['gain_argmax_se']:.4f})  "
                    f"sample {run['gain_sample']:+.4f} "
                    f"(se {run['gain_sample_se']:.4f})  "
                    f"fallback {run['fallback_share']:.1%} "
                    f"tie {run['fallback_tie_share']:.1%}  "
                    f"visits/state {run['visits_per_state_mean']:.2f} "
                    f"(1-visit {run['states_with_one_visit_share']:.0%})  "
                    f"{run['elapsed_s']:.0f}s",
                    flush=True,
                )

    table = {}

    for response_deals in budgets:
        for seat in seats:
            selected = [
                run
                for run in runs
                if run["response_deals"]
                == response_deals
                and run["seat"] == seat
            ]

            table[
                f"deals_{response_deals}_seat_{seat}"
            ] = {
                key: summary(
                    [run[key] for run in selected]
                )
                for key in (
                    "gain_argmax",
                    "gain_sample",
                    "fallback_share",
                    "fallback_tie_share",
                    "visits_per_state_mean",
                    "states_with_one_visit_share",
                )
            }

    print()
    print(
        f"{'budget':>6} {'seat':>4} "
        f"{'argmax gain (sd)':>20} "
        f"{'sample gain (sd)':>20} "
        f"{'fallback':>9} {'tie':>7} "
        f"{'visits':>7} {'1-visit':>8}"
    )

    for response_deals in budgets:
        for seat in seats:
            row = table[
                f"deals_{response_deals}_seat_{seat}"
            ]

            print(
                f"{response_deals:>6} {seat:>4} "
                f"{row['gain_argmax']['mean']:>+11.4f} "
                f"({row['gain_argmax']['sd']:.4f}) "
                f"{row['gain_sample']['mean']:>+11.4f} "
                f"({row['gain_sample']['sd']:.4f}) "
                f"{row['fallback_share']['mean']:>9.1%} "
                f"{row['fallback_tie_share']['mean']:>7.1%} "
                f"{row['visits_per_state_mean']['mean']:>7.2f} "
                f"{row['states_with_one_visit_share']['mean']:>8.0%}"
            )

    check = None

    if args.check_report:
        for run in runs:
            run["_validation_deals"] = (
                args.validation_deals
            )
            run["_sweeps"] = args.sweeps
            run["_seed"] = args.seed

        problems = check_against_report(
            runs,
            args.check_report,
        )

        for run in runs:
            for key in (
                "_validation_deals",
                "_sweeps",
                "_seed",
            ):
                run.pop(key)

        check = {
            "report": Path(
                args.check_report
            ).name,
            "problems": problems,
        }

        print()

        if problems:
            print(
                "CHECK FAILED: production gains "
                "differ from the report:"
            )

            for line in problems:
                print("  " + line)

        else:
            print(
                "CHECK OK: production gains at the "
                "report's budget match it exactly."
            )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    name = Path(args.checkpoint).name

    for suffix in (".gz", ".chk"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    out_path = out_dir / (
        f"sbr_budget__{name}__s{args.seed}.json"
    )

    out_path.write_text(
        json.dumps(
            {
                "checkpoint": Path(
                    args.checkpoint
                ).name,
                "parameters": {
                    "budgets": budgets,
                    "repeats": args.repeats,
                    "seats": seats,
                    "validation_deals": (
                        args.validation_deals
                    ),
                    "sweeps": args.sweeps,
                    "seed": args.seed,
                },
                "runs": runs,
                "summary": table,
                "check": check,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {out_path}")

    if check and check["problems"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
