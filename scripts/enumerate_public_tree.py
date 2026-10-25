"""
Enumerate every reachable public node of the training game and
derive an exact upper bound on the number of CFR information sets.

An information set is (acting seat, public node, own hand key), so
for a fixed abstraction

    info sets <= sum over phases of (public nodes in phase) x
                                    (hand keys in phase)

The public tree depends only on stacks, blinds, bet sizing and
max_draw, not on the cards, so one deal is enough. At a draw node
the public effect of a discard is only the number of cards drawn,
so one representative discard per draw count is applied.

Measurement only: no solver code is changed.

Usage:
    python -m scripts.enumerate_public_tree
    python -m scripts.enumerate_public_tree --bet-sizing full --stack 20
"""

import argparse
from collections import Counter, deque
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


from scripts.save_training_checkpoint import (  # noqa: E402
    resolve_bet_sizing,
)
from solver.action_executor import (  # noqa: E402
    apply_solver_action,
)
from solver.actions import DiscardAction  # noqa: E402
from solver.game_state import GameConfig  # noqa: E402
from solver.legal_actions import legal_actions  # noqa: E402
from solver.postdraw_strength_bucket import (  # noqa: E402
    POSTDRAW_BUCKET_COUNT,
)
from solver.public_state import PublicNodeKey  # noqa: E402
from solver.single_draw_game import (  # noqa: E402
    GamePhase,
    SingleDrawGame,
)


# Distinct DrawHandBucket keys seen in experiments/p0_small.chk.gz
# (predraw and draw phases). Confirm with
# scripts/inspect_draw_bucket_universe.py.
DEFAULT_DRAW_BUCKET_COUNT = 609


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate public nodes and bound the "
            "number of CFR information sets."
        )
    )

    parser.add_argument("--stack", type=float, default=20.0)
    parser.add_argument(
        "--max-draw",
        type=int,
        default=5,
        choices=range(0, 6),
    )
    parser.add_argument(
        "--bet-sizing",
        choices=("none", "fast", "full"),
        default="fast",
    )
    parser.add_argument("--button-seat", type=int, default=0)
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=500_000,
        help="Abort if more public nodes than this are found.",
    )
    parser.add_argument(
        "--draw-bucket-count",
        type=int,
        default=DEFAULT_DRAW_BUCKET_COUNT,
    )
    parser.add_argument(
        "--bytes-per-node",
        type=float,
        default=3900.0,
        help=(
            "Measured RSS per CFR node "
            "(experiments/memory_profile/p0_small_rss.csv)."
        ),
    )

    return parser.parse_args(argv)


def representative_actions(
    game: SingleDrawGame,
    *,
    max_draw: int,
    raise_sizes,
    bet_sizing_policy,
) -> list:
    actions = legal_actions(
        game,
        max_draw=max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=bet_sizing_policy,
        draw_action_mode="full",
    )

    if game.phase != GamePhase.DRAW:
        return list(actions)

    # Public effect of a discard is only its size.
    by_count: dict[int, DiscardAction] = {}

    for action in actions:
        by_count.setdefault(
            len(action.discard_indices),
            action,
        )

    return [by_count[count] for count in sorted(by_count)]


ROUND_DECIMALS = 6


def rounded_public_key(key: PublicNodeKey) -> tuple:
    """
    The public node with every float rounded to ROUND_DECIMALS.
    Two PublicNodeKeys that differ only by float residue (for
    example 3.5999999999999996 vs 3.6) map to the same value.
    """

    def r(value):
        return None if value is None else round(value, ROUND_DECIMALS)

    return (
        key.phase,
        key.acting_seat,
        key.button_seat,
        r(key.pot),
        r(key.current_bet),
        r(key.minimum_raise_size),
        tuple(
            (
                p.seat,
                r(p.stack),
                r(p.committed_total),
                r(p.committed_this_round),
                p.has_folded,
                p.is_all_in,
                p.draw_count,
            )
            for p in key.players
        ),
        tuple(
            (a.phase, a.seat, a.action_type, r(a.amount), a.draw_count)
            for a in key.action_history
        ),
    )


def enumerate_public_tree(
    root: SingleDrawGame,
    *,
    max_draw: int,
    raise_sizes,
    bet_sizing_policy,
    max_nodes: int,
) -> tuple[Counter, Counter, Counter]:
    """
    Returns (public nodes per phase, edges per phase, public
    nodes per phase after rounding floats). Nodes that differ
    only by float residue are separate in the first counter and
    merged in the third. Raises RuntimeError past max_nodes.
    """
    seen: set[PublicNodeKey] = set()
    rounded: dict[str, set] = {}
    nodes_per_phase: Counter = Counter()
    edges_per_phase: Counter = Counter()

    queue: deque[SingleDrawGame] = deque([root])
    root_key = PublicNodeKey.from_game(root)
    seen.add(root_key)
    rounded.setdefault(root_key.phase, set()).add(
        rounded_public_key(root_key)
    )

    while queue:
        game = queue.popleft()

        if game.phase == GamePhase.COMPLETE:
            continue

        nodes_per_phase[game.phase.value] += 1

        if len(seen) > max_nodes:
            raise RuntimeError(
                f"More than {max_nodes:,} public nodes; "
                "raise --max-nodes."
            )

        for action in representative_actions(
            game,
            max_draw=max_draw,
            raise_sizes=raise_sizes,
            bet_sizing_policy=bet_sizing_policy,
        ):
            edges_per_phase[game.phase.value] += 1

            child = apply_solver_action(game, action)
            key = PublicNodeKey.from_game(child)

            if key in seen:
                continue

            seen.add(key)
            rounded.setdefault(key.phase, set()).add(
                rounded_public_key(key)
            )
            queue.append(child)

    rounded_per_phase = Counter(
        {
            phase: len(keys)
            for phase, keys in rounded.items()
            if phase != GamePhase.COMPLETE.value
        }
    )

    return nodes_per_phase, edges_per_phase, rounded_per_phase


def info_set_upper_bound(
    nodes_per_phase: dict[str, int],
    *,
    draw_bucket_count: int,
    postdraw_bucket_count: int = POSTDRAW_BUCKET_COUNT,
) -> dict[str, int]:
    hand_keys = {
        GamePhase.PREDRAW_BETTING.value: draw_bucket_count,
        GamePhase.DRAW.value: draw_bucket_count,
        GamePhase.POSTDRAW_BETTING.value: postdraw_bucket_count,
    }

    return {
        phase: count * hand_keys[phase]
        for phase, count in nodes_per_phase.items()
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    raise_sizes, bet_sizing_policy = resolve_bet_sizing(
        args.bet_sizing
    )

    config = GameConfig(
        player_count=2,
        starting_stack=args.stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=1.5,
    )

    root = SingleDrawGame(
        config=config,
        button_seat=args.button_seat,
        deck_seed=42,
    )

    print("Public tree enumeration:")
    print(f"  stack: {args.stack}")
    print(f"  max draw: {args.max_draw}")
    print(f"  bet sizing: {args.bet_sizing}")
    print(f"  button seat: {args.button_seat}")

    start = time.perf_counter()

    nodes, edges, rounded_nodes = enumerate_public_tree(
        root,
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=bet_sizing_policy,
        max_nodes=args.max_nodes,
    )

    print(f"  seconds: {time.perf_counter() - start:.1f}")
    print()

    bound = info_set_upper_bound(
        nodes,
        draw_bucket_count=args.draw_bucket_count,
    )

    total_nodes = sum(nodes.values())
    total_bound = sum(bound.values())

    print("phase                 public nodes   edges   info-set upper bound")

    for phase in (
        GamePhase.PREDRAW_BETTING.value,
        GamePhase.DRAW.value,
        GamePhase.POSTDRAW_BETTING.value,
    ):
        print(
            f"{phase:<20}{nodes[phase]:>14,}"
            f"{edges[phase]:>8,}{bound.get(phase, 0):>23,}"
        )

    print(
        f"{'total':<20}{total_nodes:>14,}"
        f"{sum(edges.values()):>8,}{total_bound:>23,}"
    )
    print()
    print(
        "public nodes after rounding floats to "
        f"{ROUND_DECIMALS} dp (fragmentation test):"
    )

    for phase in (
        GamePhase.PREDRAW_BETTING.value,
        GamePhase.DRAW.value,
        GamePhase.POSTDRAW_BETTING.value,
    ):
        print(
            f"  {phase:<20}{nodes[phase]:>8,} -> "
            f"{rounded_nodes[phase]:>8,}"
        )

    print()
    print(
        "hand keys per phase: predraw/draw "
        f"{args.draw_bucket_count}, postdraw {POSTDRAW_BUCKET_COUNT}"
    )
    print(
        f"memory at the bound (x {args.bytes_per_node:,.0f} B/node): "
        f"{total_bound * args.bytes_per_node / 1024 ** 3:.2f} GB"
    )


if __name__ == "__main__":
    main()
