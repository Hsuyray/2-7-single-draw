"""
Memory census of a live CFRTrainer node store.

Trains for N iterations (same game config and seeding as
scripts/save_training_checkpoint.py), then walks every
(InformationState, CFRNode) pair and reports, per structure type:

  refs      how many times the structure is referenced by the store
  objects   how many distinct objects (by id) hold those references
  values    how many distinct values (by ==) those objects represent
  bytes     shallow size of one object (+ its __dict__ if it has one)

If objects >> values, the same value is stored many times and
interning (sharing one object per value) would save
(objects - values) x bytes. The script reports that estimate; it
does not change any solver code.

Sizes use sys.getsizeof, so they ignore allocator overhead. Python
3.11 and 3.12 lay out instance dicts differently: run on the Python
version you train with before quoting byte figures. The objects /
values counts do not depend on the version.

Usage:
    python -m scripts.inspect_memory_model --iterations 100
"""

import argparse
from dataclasses import dataclass
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
from solver.cfr_trainer import CFRTrainer  # noqa: E402
from solver.game_state import GameConfig  # noqa: E402
from solver.single_draw_game import SingleDrawGame  # noqa: E402


@dataclass
class Census:
    name: str
    refs: int = 0
    unit_bytes: int = 0
    total_bytes: int = 0

    def __post_init__(self) -> None:
        self._ids: set[int] = set()
        self._values: set = set()

    def add(self, obj: object) -> None:
        self.refs += 1

        key = id(obj)

        if key in self._ids:
            return

        self._ids.add(key)

        size = object_bytes(obj)

        self.total_bytes += size

        try:
            self._values.add(obj)
        except TypeError:
            self._values.add(id(obj))

        self.unit_bytes = max(self.unit_bytes, size)

    @property
    def objects(self) -> int:
        return len(self._ids)

    @property
    def values(self) -> int:
        return len(self._values)

    @property
    def duplicate_bytes(self) -> int:
        """Bytes that sharing one object per value would free."""
        if self.objects == 0:
            return 0

        mean = self.total_bytes / self.objects

        return int((self.objects - self.values) * mean)


def object_bytes(obj: object) -> int:
    size = sys.getsizeof(obj)

    instance_dict = getattr(obj, "__dict__", None)

    if instance_dict is not None:
        size += sys.getsizeof(instance_dict)

    return size


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Per-structure memory census of the node store."
    )

    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--stack", type=float, default=20.0)
    parser.add_argument(
        "--max-draw",
        type=int,
        default=5,
        choices=range(0, 6),
    )
    parser.add_argument(
        "--abstraction",
        choices=("exact", "bucket"),
        default="bucket",
    )
    parser.add_argument(
        "--bet-sizing",
        choices=("none", "fast", "full"),
        default="fast",
    )
    parser.add_argument("--seed", type=int, default=42)

    return parser.parse_args(argv)


def build_trainer_and_factory(args: argparse.Namespace):
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

    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter

        game = SingleDrawGame(
            config=config,
            button_seat=0,
            deck_seed=args.seed + counter,
        )

        counter += 1

        return game

    trainer = CFRTrainer(
        max_draw=args.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=bet_sizing_policy,
        abstraction=args.abstraction,
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=args.seed,
        game_config=config,
    )

    return trainer, factory


def take_census(node_store) -> dict[str, Census]:
    names = (
        "CFRNode",
        "regret_sum dict",
        "strategy_sum dict",
        "actions tuple",
        "action objects",
        "InformationState",
        "PublicNodeKey",
        "players tuple",
        "PublicPlayerState",
        "action_history tuple",
        "PublicAction",
        "own_hand_key",
        "float values",
    )

    census = {name: Census(name) for name in names}

    for state, node in node_store.nodes.items():
        census["CFRNode"].add(node)
        census["regret_sum dict"].add(node.regret_sum)
        census["strategy_sum dict"].add(node.strategy_sum)
        census["actions tuple"].add(node.actions)

        for action in node.actions:
            census["action objects"].add(action)

        for value in node.regret_sum.values():
            census["float values"].add(value)

        for value in node.strategy_sum.values():
            census["float values"].add(value)

        census["InformationState"].add(state)
        census["own_hand_key"].add(state.own_hand_key)

        public = state.public_node

        census["PublicNodeKey"].add(public)
        census["players tuple"].add(public.players)

        for player in public.players:
            census["PublicPlayerState"].add(player)

        census["action_history tuple"].add(public.action_history)

        for action in public.action_history:
            census["PublicAction"].add(action)

    return census


def print_census(
    census: dict[str, Census],
    node_count: int,
) -> None:
    print(
        f"{'structure':<22}{'refs':>11}{'objects':>11}"
        f"{'values':>9}{'B/obj':>8}{'total MiB':>11}"
        f"{'dup MiB':>9}"
    )

    total = 0
    duplicate = 0

    for entry in census.values():
        mean = (
            entry.total_bytes / entry.objects
            if entry.objects
            else 0
        )

        print(
            f"{entry.name:<22}{entry.refs:>11,}{entry.objects:>11,}"
            f"{entry.values:>9,}{mean:>8.0f}"
            f"{entry.total_bytes / 1024 ** 2:>11.2f}"
            f"{entry.duplicate_bytes / 1024 ** 2:>9.2f}"
        )

        total += entry.total_bytes
        duplicate += entry.duplicate_bytes

    print()
    print(f"accounted bytes: {total / 1024 ** 2:.1f} MiB")
    print(f"per CFR node:    {total / node_count:,.0f} B")
    print(
        f"shareable by interning (equal values stored as separate "
        f"objects): {duplicate / 1024 ** 2:.1f} MiB "
        f"= {100 * duplicate / total:.0f}% of accounted bytes"
    )
    print(
        f"per CFR node after sharing: "
        f"{(total - duplicate) / node_count:,.0f} B"
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    trainer, factory = build_trainer_and_factory(args)

    print(
        f"Training {args.iterations:,} iterations "
        f"(max_draw={args.max_draw}, {args.abstraction}, "
        f"{args.bet_sizing}, stack {args.stack}, seed {args.seed}) "
        f"on Python {sys.version.split()[0]}"
    )

    start = time.perf_counter()

    trainer.train(factory, iterations=args.iterations)

    print(
        f"done in {time.perf_counter() - start:.1f}s, "
        f"{len(trainer.node_store):,} CFR nodes"
    )
    print()

    print_census(
        take_census(trainer.node_store),
        len(trainer.node_store),
    )


if __name__ == "__main__":
    main()
