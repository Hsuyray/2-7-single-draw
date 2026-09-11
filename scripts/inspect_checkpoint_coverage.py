import argparse
from pathlib import Path
import sys
import random

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
)
from solver.game_state import (  # noqa: E402
    GameConfig,
)
from solver.information_state import (  # noqa: E402
    InformationState,
)
from solver.legal_actions import (  # noqa: E402
    legal_actions,
)
from solver.single_draw_game import (  # noqa: E402
    GamePhase,
    SingleDrawGame,
)
from solver.strategy_checkpoint import (  # noqa: E402
    load_strategy_checkpoint,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate strategy coverage of "
            "an existing checkpoint on fresh "
            "deals, without retraining."
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


def resolve_bet_sizing_policy(
    metadata,
):
    if metadata.bet_sizing_mode == "none":
        return None

    if metadata.bet_sizing_mode == "fixed":
        return None

    if metadata.bet_pot_fractions == (
        FAST_BET_SIZING.pot_fractions
    ):
        return FAST_BET_SIZING

    return FULL_BET_SIZING


def main() -> None:
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

    print()

    game_config = GameConfig(
        player_count=(
            metadata.player_count
            or 2
        ),
        starting_stack=(
            metadata.starting_stack
            or 20.0
        ),
        small_blind=(
            metadata.small_blind
            or 1.0
        ),
        big_blind=(
            metadata.big_blind
            or 2.0
        ),
        big_blind_ante=(
            metadata.big_blind_ante
            or 1.5
        ),
    )

    bet_sizing_policy = (
        resolve_bet_sizing_policy(
            metadata
        )
    )

    raise_sizes = metadata.raise_sizes

    strategy_index = (
        checkpoint.strategy_index
    )

    matched = 0
    missing = 0

    phase_matched: dict[str, int] = {}
    phase_missing: dict[str, int] = {}

    fallback_rng = random.Random(
        args.evaluation_seed
        + 999_999_937
    )

    print(
        "Evaluating fresh deals "
        "against saved strategy..."
    )

    for deal_index in range(
        args.evaluation_deals
    ):
        deck_seed = (
            args.evaluation_seed
            + deal_index
        )

        game = SingleDrawGame(
            config=game_config,
            button_seat=(
                deal_index % 2
            ),
            deck_seed=deck_seed,
        )

        while (
            game.phase
            != GamePhase.COMPLETE
        ):
            acting_seat = (
                game.acting_seat
            )

            if acting_seat is None:
                break

            actions = legal_actions(
                game,
                max_draw=metadata.max_draw,
                raise_sizes=raise_sizes,
                bet_sizing_policy=(
                    bet_sizing_policy
                ),
                draw_action_mode=(
                    metadata
                    .draw_action_mode
                ),
            )

            if not actions:
                break

            information_state = (
                InformationState
                .from_game(
                    game,
                    observer_seat=(
                        acting_seat
                    ),
                    abstraction=(
                        metadata
                        .abstraction
                    ),
                )
            )

            strategy = (
                strategy_index
                .strategy_for_hand(
                    public_node=(
                        information_state
                        .public_node
                    ),
                    observer_seat=(
                        acting_seat
                    ),
                    hand_key=(
                        information_state
                        .own_hand_key
                    ),
                )
            )

            phase = (
                information_state.phase
            )

            if strategy is None:
                missing += 1

                phase_missing[phase] = (
                    phase_missing.get(
                        phase,
                        0,
                    )
                    + 1
                )

                chosen_action = (
                    fallback_rng.choice(
                        actions
                    )
                )

            else:
                matched += 1

                phase_matched[phase] = (
                    phase_matched.get(
                        phase,
                        0,
                    )
                    + 1
                )

                chosen_action = max(
                    actions,
                    key=lambda action: (
                        strategy.get(
                            action,
                            0.0,
                        )
                    ),
                )

            from solver.action_executor import (
                apply_solver_action,
            )

            game = apply_solver_action(
                game,
                chosen_action,
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
        phase_matched
    ) | set(
        phase_missing
    )

    for phase in sorted(
        all_phases
    ):
        phase_total = (
            phase_matched.get(
                phase,
                0,
            )
            + phase_missing.get(
                phase,
                0,
            )
        )

        phase_coverage = (
            phase_matched.get(
                phase,
                0,
            )
            / phase_total
            if phase_total > 0
            else 0.0
        )

        print(
            f"  {phase}: "
            f"{phase_coverage:.2%} "
            f"({phase_matched.get(phase, 0):,}"
            f"/{phase_total:,})"
        )


if __name__ == "__main__":
    main()