import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.postdraw_strength_bucket import (  # noqa: E402
    _score_to_bucket,
)


OUTPUT_PATH = (
    PROJECT_ROOT
    / "solver"
    / "postdraw_bucket_mapping.json"
)


def main() -> None:
    mapping = _score_to_bucket()

    serializable = [
        {
            "score": list(score),
            "category": bucket.category,
            "bucket_id": bucket.bucket_id,
            "category_bucket": (
                bucket.category_bucket
            ),
        }
        for score, bucket in mapping.items()
    ]

    OUTPUT_PATH.write_text(
        json.dumps(
            serializable,
            indent=None,
        ),
        encoding="utf-8",
    )

    print(
        f"Exported {len(serializable):,} "
        f"score-to-bucket entries to "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()