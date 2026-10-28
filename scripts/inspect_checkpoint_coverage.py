import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from solver.checkpoint_evaluation import (  # noqa: E402
    AssumedGameConfig,
    CoverageObserver,
    make_deal_factory,
    make_profile_evaluator,
    setup_from_metadata,
)
from solver.strategy_checkpoint import (  # noqa: E402
    load_strategy_checkpoint,
)


# Game config this script used to assume when old
# checkpoints lack it. Now only applied to missing
# fields, and reported when used.
LEGACY_GAME_CONFIG = AssumedGameConfig(
    starting_stack=20.0,
    small_blind=1.0,
    big_blind=2.0,
    big_blind_ante=1.5,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate strategy coverage of "
            "an existing checkpoint on fresh "
            "deals, without retraining. "
            "For the full report use "
            "scripts.evaluate_checkpoint."
        )
    )

    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--evaluation-deals",
        type=int,
        default=500,
    )

    parser.add_argument(
        "--evaluation-seed",
        type=int,
        default=100000,
    )

    return parser.parse_args()


def main() -> None:
    """
    Fixed (day45) to measure what training produced:

    - button_seat is always 0, as in training. It used to
      alternate 0/1; PublicNodeKey stores the absolute
      button seat and training never sees button 1, so
      every odd deal missed from its first decision
      (production_v1: 51% reported vs 97% actual).
    - actions go through the trainer's solver-action path
      (bucket draw actions), via StrategyProfileEvaluator.
    - actions are sampled from the strategy instead of
      taking the argmax, so visited states follow the
      profile's own reach.
    - bet sizing is rebuilt from all stored policy fields.
    """
    args = parse_args()

    print(
        "Checkpoint coverage diagnostic "
        "(no retraining)"
    )

    print(
        f"  checkpoint: {args.checkpoint}"
    )

    checkpoint = load_strategy_checkpoint(
        args.checkpoint
    )

    metadata = checkpoint.metadata

    print(
        f"  completed_iterations: "
        f"{metadata.completed_iterations:,}"
    )

    print(
        f"  abstraction: "
        f"{metadata.abstraction}"
    )

    print(
        f"  max_draw: {metadata.max_draw}"
    )

    print(
        f"  bet_sizing_mode: "
        f"{metadata.bet_sizing_mode}"
    )

    print(
        f"  strategy_count: "
        f"{checkpoint.strategy_count:,}"
    )

    setup = setup_from_metadata(
        metadata,
        assumed=LEGACY_GAME_CONFIG,
    )

    if setup.assumed_fields:
        print(
            "  WARNING: metadata lacks "
            + ", ".join(
                setup.assumed_fields
            )
            + "; assumed 20 / 1 / 2 / 1.5"
        )

    print(
        "  button seat: 0 (training "
        "distribution)"
    )

    print()

    print(
        "Evaluating fresh deals "
        "against saved strategy..."
    )

    observer = CoverageObserver()

    result = make_profile_evaluator(
        checkpoint.strategy_index,
        setup,
        random_seed=(
            args.evaluation_seed
            + 999_999_937
        ),
    ).evaluate(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=(
                args.evaluation_seed
            ),
        ),
        deals=args.evaluation_deals,
        observer=observer,
    )

    matched = result.strategy_decisions
    missing = (
        result.missing_strategy_decisions
    )
    total = matched + missing

    print()

    print(
        "OVERALL COVERAGE"
    )

    print(
        f"  matched decisions: "
        f"{matched:,}"
    )

    print(
        f"  missing decisions: "
        f"{missing:,}"
    )

    print(
        f"  total decisions: "
        f"{total:,}"
    )

    if total > 0:
        print(
            f"  coverage: "
            f"{matched / total:.2%}"
        )

    print()

    print(
        "PHASE COVERAGE"
    )

    all_phases = set(
        observer.matched
    ) | set(
        observer.missing
    )

    for phase in sorted(
        all_phases
    ):
        phase_matched = observer.matched[
            phase
        ]

        phase_total = (
            phase_matched
            + observer.missing[phase]
        )

        phase_coverage = (
            phase_matched / phase_total
            if phase_total > 0
            else 0.0
        )

        print(
            f"  {phase}: "
            f"{phase_coverage:.2%} "
            f"({phase_matched:,}"
            f"/{phase_total:,})"
        )


if __name__ == "__main__":
    main()
