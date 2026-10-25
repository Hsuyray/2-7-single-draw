"""
Deterministic fingerprint of a trained node store.

Trains a fixed-seed run and hashes, in insertion order, every
information state (repr), its action tuple, the exact regret and
strategy sums (float.hex) and the update counters. Two code
versions that print the same fingerprint built identical node
stores, so a behavior-preserving change can be proved by running
this on the old and the new code:

    git checkout main;                python -m scripts.fingerprint_node_store > before.json
    git checkout ws-a1-memory;        python -m scripts.fingerprint_node_store > after.json
    fc before.json after.json

Fingerprints are only comparable for the same Python version.
Measurement only: no solver code is changed.
"""

import argparse
import hashlib
import json
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


from solver.bet_sizing import FAST_BET_SIZING  # noqa: E402
from solver.cfr_trainer import CFRTrainer  # noqa: E402
from solver.game_state import GameConfig  # noqa: E402
from solver.single_draw_game import SingleDrawGame  # noqa: E402


DEFAULT_RUNS = (
    ("md5_bucket_40", 5, "bucket", 40),
    ("md2_exact_15", 2, "exact", 15),
)


def fingerprint_trainer(
    trainer: CFRTrainer,
) -> dict[str, object]:
    digest = hashlib.sha256()

    for state, node in trainer.node_store.nodes.items():
        digest.update(repr(state).encode())
        digest.update(repr(node.actions).encode())

        for action in node.actions:
            digest.update(
                float(node.regret_sum[action]).hex().encode()
            )
            digest.update(
                float(node.strategy_sum[action]).hex().encode()
            )

        digest.update(
            (
                f"{node.visit_count},"
                f"{node.strategy_update_count},"
                f"{node.regret_update_count},"
                f"{float(node.strategy_weight_sum).hex()}"
            ).encode()
        )

    return {
        "nodes": len(trainer.node_store),
        "sha256": digest.hexdigest(),
    }


def run(
    *,
    max_draw: int,
    abstraction: str,
    iterations: int,
    seed: int,
) -> dict[str, object]:
    config = GameConfig(
        player_count=2,
        starting_stack=20.0,
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
            deck_seed=seed + counter,
        )

        counter += 1

        return game

    trainer = CFRTrainer(
        max_draw=max_draw,
        raise_sizes=None,
        bet_sizing_policy=FAST_BET_SIZING,
        abstraction=abstraction,
        traversal_mode="external_sampling",
        draw_action_mode="auto",
        random_seed=seed,
        game_config=config,
    )

    trainer.train(factory, iterations=iterations)

    return fingerprint_trainer(trainer)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Print a fingerprint of fixed-seed training runs."
    )

    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args(argv)

    result = {
        name: run(
            max_draw=max_draw,
            abstraction=abstraction,
            iterations=iterations,
            seed=args.seed,
        )
        for name, max_draw, abstraction, iterations in DEFAULT_RUNS
    }

    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
