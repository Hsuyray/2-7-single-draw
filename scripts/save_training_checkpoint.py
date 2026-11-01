import argparse
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


import psutil  # noqa: E402

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
from solver.information_state import (  # noqa: E402
    AbstractionMode,
)
from solver.memory_guard import (  # noqa: E402
    DEFAULT_MAX_RSS_GB,
    DEFAULT_RSS_CHECK_EVERY,
    RSSGuard,
    bytes_to_gb,
    iteration_chunks,
    peak_rss_bytes,
)
from solver.training_run import (  # noqa: E402
    TrainingRunInfo,
    TrainingState,
    config_differences,
    current_git_commit,
    load_training_state,
    make_game_factory,
    save_training_state,
)


DEFAULT_BATCH_SIZE = 500

DEFAULT_MIN_FREE_MEMORY_GB = 2.0

# Exit code when training stopped early (RSS / free memory) and a
# training state was saved, so a wrapper can resume.
EXIT_STOPPED_EARLY = 3


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train the heads-up 2-7 Single "
            "Draw CFR prototype and save an "
            "average-strategy checkpoint."
        )
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path("checkpoints")
            / "strategy.chk.gz"
        ),
    )

    parser.add_argument(
        "--stack",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--max-draw",
        type=int,
        default=2,
        choices=range(
            0,
            6,
        ),
    )

    parser.add_argument(
        "--abstraction",
        choices=(
            "exact",
            "bucket",
        ),
        default="exact",
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
        "--draw-action-mode",
        choices=(
            "auto",
            "full",
            "candidate",
        ),
        default="auto",
    )

    parser.add_argument(
        "--bet-sizing",
        choices=(
            "none",
            "fast",
            "full",
        ),
        default="fast",
        help=(
            "none disables betting raises; "
            "fast uses 33/66/100/all-in; "
            "full uses the complete sizing "
            "abstraction."
        ),
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
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=(
            "Number of iterations to run "
            "between memory checks and "
            "checkpoint saves."
        ),
    )

    parser.add_argument(
        "--min-free-memory-gb",
        type=float,
        default=(
            DEFAULT_MIN_FREE_MEMORY_GB
        ),
        help=(
            "Stop training and save if "
            "available system memory drops "
            "below this threshold, in GB."
        ),
    )

    parser.add_argument(
        "--max-rss-gb",
        type=float,
        default=DEFAULT_MAX_RSS_GB,
        help=(
            "Stop training and save if this "
            "process's resident memory (RSS) "
            "exceeds this limit, in GB. Set "
            "to 0 to disable the RSS guard."
        ),
    )

    parser.add_argument(
        "--rss-check-every",
        type=int,
        default=DEFAULT_RSS_CHECK_EVERY,
        help=(
            "Number of iterations between "
            "RSS checks when the RSS guard "
            "is enabled."
        ),
    )

    parser.add_argument(
        "--checkpoint-every-batches",
        type=int,
        default=1,
        help=(
            "Save an intermediate checkpoint "
            "every N batches, in addition to "
            "the final save. Set to 0 to "
            "disable intermediate saves."
        ),
    )

    parser.add_argument(
        "--state-output",
        type=Path,
        default=None,
        help=(
            "Also save the full training "
            "state (regrets, strategy sums, "
            "RNG) here so training can be "
            "resumed. Defaults to --resume "
            "when resuming."
        ),
    )

    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help=(
            "Resume from this training state "
            "file. --iterations is then the "
            "target total, and every setting "
            "that affects results must match "
            "the state file."
        ),
    )

    parser.add_argument(
        "--state-every-batches",
        type=int,
        default=1,
        help=(
            "Save the training state every N "
            "batches, in addition to the "
            "final save. Set to 0 to save "
            "only at the end."
        ),
    )

    return parser.parse_args(argv)


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.iterations <= 0:
        raise ValueError(
            "Iterations must be positive."
        )

    if args.stack <= 0:
        raise ValueError(
            "Starting stack must be positive."
        )

    if not (
        0
        <= args.max_draw
        <= 5
    ):
        raise ValueError(
            "Max draw must be between "
            "zero and five."
        )

    if (
        args.abstraction == "bucket"
        and args.draw_action_mode
        == "candidate"
    ):
        raise ValueError(
            "Bucket abstraction currently "
            "requires --draw-action-mode "
            "auto or full."
        )

    if args.batch_size <= 0:
        raise ValueError(
            "Batch size must be positive."
        )

    if args.min_free_memory_gb <= 0:
        raise ValueError(
            "Minimum free memory must be "
            "positive."
        )

    if args.checkpoint_every_batches < 0:
        raise ValueError(
            "Checkpoint-every-batches cannot "
            "be negative."
        )

    if args.max_rss_gb < 0:
        raise ValueError(
            "Max RSS cannot be negative. "
            "Use 0 to disable the guard."
        )

    if args.rss_check_every <= 0:
        raise ValueError(
            "RSS check interval must be "
            "positive."
        )

    if args.state_every_batches < 0:
        raise ValueError(
            "State-every-batches cannot "
            "be negative."
        )


def training_config(
    args: argparse.Namespace,
    game_config: GameConfig,
) -> dict[str, object]:
    """
    Every setting that changes training results. A resume must
    match these exactly.
    """
    return {
        "player_count": (
            game_config.player_count
        ),
        "stack": (
            game_config.starting_stack
        ),
        "small_blind": (
            game_config.small_blind
        ),
        "big_blind": (
            game_config.big_blind
        ),
        "big_blind_ante": (
            game_config.big_blind_ante
        ),
        "max_draw": args.max_draw,
        "abstraction": args.abstraction,
        "traversal_mode": (
            args.traversal_mode
        ),
        "draw_action_mode": (
            args.draw_action_mode
        ),
        "bet_sizing": args.bet_sizing,
        "seed": args.seed,
        "seed_mode": args.seed_mode,
    }


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


def available_memory_gb() -> float:
    return (
        psutil.virtual_memory().available
        / (1024 ** 3)
    )


def main(
    argv: list[str] | None = None,
) -> None:
    args = parse_args(
        argv
    )

    validate_args(
        args
    )

    (
        raise_sizes,
        bet_sizing_policy,
    ) = resolve_bet_sizing(
        args.bet_sizing
    )

    shared_game_config = GameConfig(
        player_count=2,
        starting_stack=args.stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    run_config = training_config(
        args,
        shared_game_config,
    )

    state_path: Path | None = (
        args.state_output
        if args.state_output is not None
        else args.resume
    )

    run_info: TrainingRunInfo | None = None

    if args.resume is not None:
        resumed_state = load_training_state(
            args.resume
        )

        differences = config_differences(
            resumed_state.run.config,
            run_config,
        )

        if differences:
            raise ValueError(
                "Cannot resume: settings that "
                "affect results differ from the "
                "training state:\n  "
                + "\n  ".join(differences)
            )

        trainer = resumed_state.trainer

        run_info = resumed_state.run

        if (
            trainer.completed_iterations
            >= args.iterations
        ):
            raise ValueError(
                f"Training state already has "
                f"{trainer.completed_iterations:,} "
                f"iterations; --iterations is the "
                f"target total when resuming."
            )

    else:
        abstraction: AbstractionMode = (
            args.abstraction
        )

        trainer = CFRTrainer(
            max_draw=args.max_draw,
            raise_sizes=raise_sizes,
            bet_sizing_policy=(
                bet_sizing_policy
            ),
            abstraction=abstraction,
            traversal_mode=(
                args.traversal_mode
            ),
            draw_action_mode=(
                args.draw_action_mode
            ),
            random_seed=args.seed,
            game_config=shared_game_config,
        )

        if state_path is not None:
            run_info = TrainingRunInfo(
                config=run_config,
                git_commit=(
                    current_git_commit()
                ),
            )

    # The game seed comes from completed_iterations, which equals
    # the old per-call counter for a fresh trainer and continues
    # the same sequence for a resumed one.
    game_factory = make_game_factory(
        trainer,
        game_config=shared_game_config,
        seed=args.seed,
        seed_mode=args.seed_mode,
    )

    segment_start_iteration = (
        trainer.completed_iterations
    )

    prior_segments = (
        list(run_info.segments)
        if run_info is not None
        else []
    )

    def save_state(
        stop_reason: str,
        wall_seconds: float,
    ) -> None:
        assert state_path is not None
        assert run_info is not None

        peak = peak_rss_bytes()

        run_info.segments = prior_segments + [
            {
                "start_iteration": (
                    segment_start_iteration
                ),
                "end_iteration": (
                    trainer.completed_iterations
                ),
                "wall_seconds": wall_seconds,
                "peak_rss_gb": (
                    bytes_to_gb(peak)
                    if peak is not None
                    else None
                ),
                "stop_reason": stop_reason,
            }
        ]

        saved_path = save_training_state(
            state_path,
            TrainingState(
                trainer=trainer,
                run=run_info,
            ),
        )

        print(
            f"  Saved training state "
            f"({trainer.completed_iterations:,} "
            f"iterations) to "
            f"{saved_path.resolve()}"
        )

        # The stored peak_rss_gb is read before the state is
        # written, so it misses this save's own peak; print the
        # peak including it.
        peak_after_save = peak_rss_bytes()

        if peak_after_save is not None:
            print(
                f"  peak RSS including this "
                f"save: "
                f"{bytes_to_gb(peak_after_save):.2f}GB"
            )

    print(
        "Training started:"
    )

    print(
        f"  iterations: "
        f"{args.iterations:,}"
    )

    if args.resume is not None:
        print(
            f"  resumed from: "
            f"{args.resume} "
            f"({trainer.completed_iterations:,} "
            f"iterations done)"
        )

    if state_path is not None:
        print(
            f"  training state: "
            f"{state_path}"
        )

    print(
        f"  stack: "
        f"{args.stack}"
    )

    print(
        f"  abstraction: "
        f"{args.abstraction}"
    )

    print(
        f"  traversal: "
        f"{args.traversal_mode}"
    )

    print(
        f"  bet sizing: "
        f"{args.bet_sizing}"
    )

    if bet_sizing_policy is not None:
        print(
            f"  pot fractions: "
            f"{bet_sizing_policy.pot_fractions}"
        )

        print(
            f"  include all-in: "
            f"{bet_sizing_policy.include_all_in}"
        )

    print(
        f"  draw action setting: "
        f"{args.draw_action_mode}"
    )

    print(
        f"  resolved draw actions: "
        f"{trainer.resolved_draw_action_mode}"
    )

    print(
        f"  max draw: "
        f"{args.max_draw}"
    )

    print(
        f"  seed: "
        f"{args.seed}"
    )

    print(
        f"  seed mode: "
        f"{args.seed_mode}"
    )

    print(
        f"  batch size: "
        f"{args.batch_size:,}"
    )

    print(
        f"  min free memory (GB): "
        f"{args.min_free_memory_gb}"
    )

    print(
        f"  checkpoint every N batches: "
        f"{args.checkpoint_every_batches}"
    )

    rss_guard = RSSGuard(
        max_rss_gb=args.max_rss_gb,
    )

    if rss_guard.enabled:
        print(
            f"  max RSS (GB): "
            f"{args.max_rss_gb}"
        )

        print(
            f"  RSS check every N iterations: "
            f"{args.rss_check_every:,}"
        )

    else:
        print(
            "  max RSS (GB): disabled"
        )

    print()

    print(
        f"  starting free memory: "
        f"{available_memory_gb():.2f} GB"
    )

    print()

    remaining_iterations = (
        args.iterations
        - trainer.completed_iterations
    )

    batch_number = 0

    stopped_early = False

    stop_reason = "low memory"

    overall_start = time.perf_counter()

    while remaining_iterations > 0:
        batch_number += 1

        this_batch_size = min(
            args.batch_size,
            remaining_iterations,
        )

        batch_start = time.perf_counter()

        # With the guard disabled the whole batch
        # is one train() call, exactly as before.
        # Splitting train() into chunks does not
        # change results: trainer RNG and the game
        # counter persist across calls.
        check_every = (
            args.rss_check_every
            if rss_guard.enabled
            else this_batch_size
        )

        batch_iterations_run = 0

        rss_limit_check = None

        rss_check = None

        for chunk_size in iteration_chunks(
            this_batch_size,
            check_every,
        ):
            trainer.train(
                game_factory,
                iterations=chunk_size,
            )

            batch_iterations_run += (
                chunk_size
            )

            rss_check = rss_guard.check()

            if (
                rss_check is not None
                and rss_check.exceeded
            ):
                rss_limit_check = rss_check
                break

        batch_seconds = (
            time.perf_counter()
            - batch_start
        )

        remaining_iterations -= (
            batch_iterations_run
        )

        free_memory = (
            available_memory_gb()
        )

        elapsed_total = (
            time.perf_counter()
            - overall_start
        )

        print(
            f"Batch {batch_number}: "
            f"completed_iterations="
            f"{trainer.completed_iterations:,}, "
            f"CFR_nodes="
            f"{len(trainer.node_store):,}, "
            f"batch_seconds="
            f"{batch_seconds:.1f}, "
            f"elapsed_total="
            f"{elapsed_total:.1f}s, "
            f"free_memory="
            f"{free_memory:.2f}GB"
        )

        if rss_check is not None:
            print(
                f"  process_rss="
                f"{rss_check.rss_gb:.2f}GB "
                f"(limit {rss_check.limit_gb:.2f}GB)"
            )

        if rss_limit_check is not None:
            print()

            print(
                "WARNING: process RSS "
                f"({rss_limit_check.rss_gb:.2f} GB) "
                "exceeded the limit "
                f"({args.max_rss_gb} GB). "
                "Stopping training and "
                "saving now."
            )

            stopped_early = True

            stop_reason = "RSS limit"

            # The final save below writes the
            # checkpoint; skip the intermediate
            # save so only one save runs.
            break

        should_checkpoint = (
            args.checkpoint_every_batches
            > 0
            and batch_number
            % args.checkpoint_every_batches
            == 0
        )

        low_memory = (
            free_memory
            < args.min_free_memory_gb
        )

        if low_memory:
            print()

            print(
                "WARNING: free memory "
                f"({free_memory:.2f} GB) "
                "is below the safety "
                "threshold "
                f"({args.min_free_memory_gb} "
                "GB). Stopping training "
                "and saving now."
            )

            stopped_early = True

        if should_checkpoint or low_memory:
            checkpoint_path = (
                trainer.save_checkpoint(
                    args.output
                )
            )

            print(
                f"  Saved checkpoint "
                f"({trainer.completed_iterations:,} "
                f"iterations) to "
                f"{checkpoint_path.resolve()}"
            )

        # The last batch is covered by the final
        # save below, so it is not saved twice.
        should_save_state = (
            state_path is not None
            and not low_memory
            and remaining_iterations > 0
            and args.state_every_batches > 0
            and batch_number
            % args.state_every_batches
            == 0
        )

        if should_save_state:
            save_state(
                "checkpoint",
                elapsed_total,
            )

        if low_memory:
            break

    final_checkpoint_path = (
        trainer.save_checkpoint(
            args.output
        )
    )

    if state_path is not None:
        save_state(
            stop_reason
            if stopped_early
            else "completed",
            time.perf_counter()
            - overall_start,
        )

    print()

    print(
        "Training completed"
        if not stopped_early
        else "Training stopped early "
        f"({stop_reason})"
    )

    print(
        ":"
    )

    print(
        f"  iterations: "
        f"{trainer.completed_iterations:,}"
    )

    print(
        f"  CFR nodes: "
        f"{len(trainer.node_store):,}"
    )

    print(
        f"  final free memory: "
        f"{available_memory_gb():.2f} GB"
    )

    print(
        f"  checkpoint: "
        f"{final_checkpoint_path.resolve()}"
    )

    if (
        stopped_early
        and state_path is not None
    ):
        print(
            f"  resume with: --resume "
            f"{state_path} (same settings, "
            f"--iterations {args.iterations})"
        )

        sys.exit(
            EXIT_STOPPED_EARLY
        )


if __name__ == "__main__":
    main()