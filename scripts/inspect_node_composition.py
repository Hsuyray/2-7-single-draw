import argparse
from collections import Counter, defaultdict
from pathlib import Path
import statistics
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.strategy_checkpoint import (  # noqa: E402
    load_strategy_checkpoint,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Decompose checkpoint information "
            "states by phase, public node and "
            "hand key; test float fragmentation."
        )
    )
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()

    loaded = load_strategy_checkpoint(args.checkpoint)
    strategies = loaded.strategy_index.strategies()

    print(f"info sets: {len(strategies):,}")

    by_phase = defaultdict(list)

    for state in strategies:
        by_phase[state.phase].append(state)

    for phase, states in sorted(by_phase.items()):
        hands_by_public = defaultdict(set)

        for s in states:
            hands_by_public[s.public_node].add(
                (s.observer_seat, s.own_hand_key)
            )

        reduced_keys = {
            (
                s.public_node.acting_seat,
                s.public_node.button_seat,
                s.public_node.action_history,
            )
            for s in states
        }

        counts = [len(v) for v in hands_by_public.values()]
        hand_keys = {s.own_hand_key for s in states}

        print()
        print(f"[{phase}]")
        print(f"  info sets:               {len(states):,}")
        print(f"  distinct public nodes:   {len(hands_by_public):,}")
        print(f"  distinct history keys:   {len(reduced_keys):,}")
        print(f"  distinct hand keys:      {len(hand_keys):,}")
        print(
            "  hands per public node:   "
            f"mean={statistics.mean(counts):.1f} "
            f"median={statistics.median(counts):.0f} "
            f"max={max(counts)}"
        )
        print(
            "  distinct pots:           "
            f"{len({s.public_node.pot for s in states}):,}"
        )

        draw_pairs = Counter(
            tuple(p.draw_count for p in s.public_node.players)
            for s in states
        )
        length_dist = Counter(
            len(s.public_node.action_history)
            for s in states
        )

        print(f"  top draw-count pairs:    {draw_pairs.most_common(5)}")
        print(f"  history length dist:     {sorted(length_dist.items())}")


if __name__ == "__main__":
    main()
