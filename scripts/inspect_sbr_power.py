"""
Power test for the SBR exploitability proxy (A2, docs/A2_DESIGN.md
section 12.1).

Plants a graded fold-to-bet leak in one seat of a checkpoint and
checks whether SBR, run for the other seat, finds it. Compares the
original per-information-set SBR ("per_state") with grouped SBR
("grouped", solver/response_grouping.coarse_grouping). A hand-written
exploit (smallest raise whenever legal) gives a reference gain.

Pre-registered criteria per mode and responder seat (see
solver/exploitability_power.judge_estimator):
    P1 power     finds the largest leak, >= 50% of the reference gain
    P2 monotone  gain does not fall as the leak grows
    P3 validity  no significantly negative gain without a leak

Validation decks are shared by every leak level, mode and repeat
(common random numbers).

    python -m scripts.inspect_sbr_power checkpoints/production_v1.chk.gz
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

from solver.best_response import (
    SampledBestResponse,
)
from solver.checkpoint_evaluation import (
    deck_seed_base,
    derive_seed,
    make_deal_factory,
    setup_from_metadata,
)
from solver.exploitability_power import (
    judge_estimator,
    plant_fold_leak,
    reference_exploit_gain,
)
from solver.response_grouping import (
    coarse_grouping,
)
from solver.strategy_checkpoint import (
    load_strategy_checkpoint,
)


MODES = {
    "per_state": None,
    "grouped": coarse_grouping,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Can SBR find a planted leak?"
        )
    )

    parser.add_argument("checkpoint")

    parser.add_argument(
        "--leak-probabilities",
        default="0,0.1,0.3,1",
    )

    parser.add_argument(
        "--modes",
        default="per_state,grouped",
    )

    parser.add_argument(
        "--responder-seats",
        default="0,1",
        help=(
            "The leak is planted in the "
            "other seat."
        ),
    )

    parser.add_argument(
        "--response-deals",
        type=int,
        default=300,
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
        "--repeats",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2027,
    )

    parser.add_argument(
        "--out-dir",
        default="experiments/eval",
    )

    return parser.parse_args()


def run_sbr(
    index,
    setup,
    *,
    grouping,
    seat: int,
    repeat: int,
    seed: int,
    response_deals: int,
    validation_deals: int,
    sweeps: int,
) -> dict:
    optimizer = SampledBestResponse(
        strategy_index=index,
        abstraction=setup.abstraction,
        responder_seat=seat,
        max_draw=setup.max_draw,
        raise_sizes=setup.raise_sizes,
        bet_sizing_policy=setup.bet_sizing_policy,
        draw_action_mode=setup.draw_action_mode,
        random_seed=derive_seed(
            seed,
            "power",
            "policy",
            seat,
            repeat,
        ),
        response_grouping=grouping,
    )

    started = perf_counter()

    result = optimizer.optimize(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=deck_seed_base(
                seed,
                "power",
                "response",
                seat,
                repeat,
            ),
        ),
        deals=response_deals,
        max_sweeps=sweeps,
        validation_game_factory=make_deal_factory(
            setup.game_config,
            first_deck_seed=deck_seed_base(
                seed,
                "power",
                "validation",
            ),
        ),
        validation_deals=validation_deals,
    )

    return {
        "gain": result.improvement,
        "gain_se": (
            result.improvement_standard_error
        ),
        "baseline_value": result.baseline_value,
        "policy_keys": result.information_states,
        "sweeps_completed": result.sweeps,
        "fallback_share": (
            result.response_fallback_share
        ),
        "elapsed_s": perf_counter() - started,
    }


def main() -> None:
    args = parse_args()

    probabilities = sorted(
        float(part)
        for part in args.leak_probabilities.split(",")
    )

    modes = [
        part
        for part in args.modes.split(",")
    ]

    unknown = set(modes) - set(MODES)

    if unknown:
        raise SystemExit(
            f"Unknown modes: {sorted(unknown)}"
        )

    seats = [
        int(part)
        for part in args.responder_seats.split(",")
    ]

    print(
        f"Loading {args.checkpoint} ...",
        flush=True,
    )

    loaded = load_strategy_checkpoint(
        args.checkpoint
    )

    setup = setup_from_metadata(
        loaded.metadata
    )

    print(
        f"leaks={probabilities} modes={modes} "
        f"responder seats={seats} "
        f"response={args.response_deals} "
        f"validation={args.validation_deals} "
        f"sweeps<={args.sweeps} "
        f"repeats={args.repeats} seed={args.seed}",
        flush=True,
    )

    references: dict[str, dict] = {}
    runs: list[dict] = []

    for seat in seats:
        leaky_seat = 1 - seat

        for probability in probabilities:
            index = plant_fold_leak(
                loaded.strategy_index,
                leaky_seat=leaky_seat,
                probability=probability,
            )

            reference = reference_exploit_gain(
                index,
                setup,
                responder_seat=seat,
                deals=args.validation_deals,
                first_deck_seed=deck_seed_base(
                    args.seed,
                    "power",
                    "validation",
                ),
                random_seed=derive_seed(
                    args.seed,
                    "power",
                    "reference",
                    seat,
                ),
            )

            references[
                f"seat_{seat}_leak_{probability:g}"
            ] = {
                "gain": reference.gain,
                "gain_se": (
                    reference.gain_standard_error
                ),
            }

            print(
                f"  seat={seat} leak={probability:g}: "
                f"reference exploit {reference.gain:+.4f} "
                f"(se {reference.gain_standard_error:.4f})",
                flush=True,
            )

            for mode in modes:
                for repeat in range(args.repeats):
                    run = run_sbr(
                        index,
                        setup,
                        grouping=MODES[mode],
                        seat=seat,
                        repeat=repeat,
                        seed=args.seed,
                        response_deals=(
                            args.response_deals
                        ),
                        validation_deals=(
                            args.validation_deals
                        ),
                        sweeps=args.sweeps,
                    ) | {
                        "seat": seat,
                        "leak": probability,
                        "mode": mode,
                        "repeat": repeat,
                    }

                    runs.append(run)

                    print(
                        f"    {mode:<9} repeat={repeat}: "
                        f"gain {run['gain']:+.4f} "
                        f"(se {run['gain_se']:.4f})  "
                        f"keys {run['policy_keys']:,}  "
                        f"fallback {run['fallback_share']:.1%}  "
                        f"{run['elapsed_s']:.0f}s",
                        flush=True,
                    )

    verdicts = {}

    print()
    print(
        f"{'seat':>4} {'mode':<9} "
        + " ".join(
            f"{'leak ' + format(p, 'g'):>16}"
            for p in probabilities
        )
        + "   verdict"
    )

    for seat in seats:
        print(
            f"{seat:>4} {'reference':<9} "
            + " ".join(
                f"{references[f'seat_{seat}_leak_{p:g}']['gain']:>+16.4f}"
                for p in probabilities
            )
        )

        for mode in modes:
            rows = {}

            for probability in probabilities:
                selected = [
                    run
                    for run in runs
                    if run["seat"] == seat
                    and run["mode"] == mode
                    and run["leak"] == probability
                ]

                rows[probability] = {
                    "mean": sum(
                        run["gain"]
                        for run in selected
                    )
                    / len(selected),
                    # Conservative: repeats share the
                    # validation decks, so their errors
                    # are correlated; use the mean
                    # per-run se, not se / sqrt(K).
                    "se": sum(
                        run["gain_se"]
                        for run in selected
                    )
                    / len(selected),
                }

            verdict = judge_estimator(
                rows,
                reference_at_largest_leak=(
                    references[
                        f"seat_{seat}_leak_"
                        f"{probabilities[-1]:g}"
                    ]["gain"]
                ),
            )

            verdicts[f"seat_{seat}_{mode}"] = {
                "rows": {
                    format(p, "g"): row
                    for p, row in rows.items()
                },
                "verdict": verdict,
            }

            print(
                f"{seat:>4} {mode:<9} "
                + " ".join(
                    f"{rows[p]['mean']:>+9.4f}±{rows[p]['se']:.3f}"
                    for p in probabilities
                )
                + "   "
                + ("PASS" if verdict["pass"] else "FAIL")
                + " ("
                + ", ".join(
                    f"{key.split('_')[0]}="
                    f"{'ok' if value else 'no'}"
                    for key, value in verdict.items()
                    if key != "pass"
                )
                + ")"
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
        f"sbr_power__{name}__s{args.seed}.json"
    )

    out_path.write_text(
        json.dumps(
            {
                "checkpoint": Path(
                    args.checkpoint
                ).name,
                "parameters": {
                    "leak_probabilities": probabilities,
                    "modes": modes,
                    "responder_seats": seats,
                    "response_deals": (
                        args.response_deals
                    ),
                    "validation_deals": (
                        args.validation_deals
                    ),
                    "sweeps": args.sweeps,
                    "repeats": args.repeats,
                    "seed": args.seed,
                },
                "references": references,
                "runs": runs,
                "verdicts": verdicts,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
