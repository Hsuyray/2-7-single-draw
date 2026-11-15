"""
Starting-hand combinations per DrawHandBucket and made-hand type
(D1, for conditioned ranges).

DrawHandBucket depends on suits (flush-risk positions), so the counts
come from enumerating all 2,598,960 hands once (~40 s) and are stored
in product/api/data/draw_bucket_combos.json. The "type" of a hand is
its D3 postdraw class (made-hand type of the five cards it holds).

    python -m product.api.hand_data          # regenerate the file
"""

import json
from collections import Counter
from dataclasses import asdict, fields
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from solver.draw_hand_bucket import DrawHandBucket, draw_hand_bucket
from solver.hand import Hand
from solver.hand_classes import postdraw_class


DATA_PATH = Path(__file__).parent / "data" / "draw_bucket_combos.json"

DATA_VERSION = 1

TOTAL_HANDS = 2_598_960


def bucket_to_json(bucket: DrawHandBucket) -> dict:
    return {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in asdict(bucket).items()
    }


def bucket_from_json(data: dict) -> DrawHandBucket:
    return DrawHandBucket(
        **{
            field.name: (
                tuple(data[field.name])
                if isinstance(data[field.name], list)
                else data[field.name]
            )
            for field in fields(DrawHandBucket)
        }
    )


def generate() -> dict:
    deck = [rank + suit for rank in "23456789TJQKA" for suit in "shdc"]

    counts: dict[DrawHandBucket, Counter] = {}

    for cards in combinations(deck, 5):
        hand = Hand.from_strings(*cards)
        bucket = draw_hand_bucket(hand)
        counts.setdefault(bucket, Counter())[
            postdraw_class(hand).key
        ] += 1

    rows = sorted(
        (
            {
                "bucket": bucket_to_json(bucket),
                "types": dict(sorted(types.items())),
            }
            for bucket, types in counts.items()
        ),
        key=lambda row: json.dumps(row["bucket"], sort_keys=True),
    )

    return {
        "version": DATA_VERSION,
        "total": sum(sum(row["types"].values()) for row in rows),
        "buckets": rows,
    }


@lru_cache(maxsize=1)
def bucket_combos() -> dict[DrawHandBucket, dict[str, int]]:
    """{bucket: {made-hand type: combinations}}."""
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    if data["version"] != DATA_VERSION or data["total"] != TOTAL_HANDS:
        raise ValueError(f"Unexpected data in {DATA_PATH}.")

    return {
        bucket_from_json(row["bucket"]): row["types"]
        for row in data["buckets"]
    }


def main() -> None:
    data = generate()

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {DATA_PATH}: {len(data['buckets'])} buckets, "
        f"{data['total']:,} hands"
    )


if __name__ == "__main__":
    main()
