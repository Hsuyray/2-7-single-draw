"""
HTTP layer for the D1 query API (docs/API.md section 3). Thin: all
logic is in product/api/service.py.

    python -m product.api.app --solution hu_d5_full_bucket_s20 --iterations 16000
    python -m product.api.app --checkpoint checkpoints/production_v1.chk.gz --solution v1 --iterations 20000

Then open http://127.0.0.1:8000/docs for the interactive API docs.
Loading a v2-scale checkpoint needs about 8 GB (the SQLite store that
avoids this is the next slice).
"""

import argparse
import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from solver.strategy_checkpoint import load_strategy_checkpoint

from product.api.paths import IllegalPath
from product.api.service import API_VERSION, BadHand, QueryService


def create_app(services: dict[tuple[str, int], QueryService]) -> FastAPI:
    app = FastAPI(
        title="2-7 Single Draw solution API",
        version=API_VERSION,
    )

    def lookup(solution: str, iterations: int):
        service = services.get((solution, iterations))

        if service is None:
            return None, JSONResponse(
                status_code=404,
                content={
                    "error": "unknown_solution",
                    "available": [
                        {"solution": key[0], "iterations": key[1]}
                        for key in sorted(services)
                    ],
                },
            )

        return service, None

    def illegal(error: IllegalPath) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": "illegal_action",
                "at": error.at,
                "legal": error.legal,
            },
        )

    @app.get("/v0/solutions")
    def solutions():
        return {
            "api_version": API_VERSION,
            "solutions": [
                {
                    "id": service.solution,
                    "iterations": service.iterations,
                    "players": 2,
                    "stack": service.setup.game_config.starting_stack,
                    "small_blind": service.setup.game_config.small_blind,
                    "big_blind": service.setup.game_config.big_blind,
                    "big_blind_ante": service.setup.game_config.big_blind_ante,
                    "max_draw": service.setup.max_draw,
                    "abstraction": service.setup.abstraction,
                }
                for service in services.values()
            ],
        }

    @app.get("/v0/solutions/{solution}/{iterations}/node")
    def node(solution: str, iterations: int, path: str = ""):
        service, error = lookup(solution, iterations)

        if error is not None:
            return error

        try:
            return service.node(path)
        except IllegalPath as exception:
            return illegal(exception)

    @app.get("/v0/solutions/{solution}/{iterations}/hand")
    def hand(
        solution: str,
        iterations: int,
        cards: str = Query(..., description="e.g. 7s5h4d3c2s"),
        path: str = "",
    ):
        service, error = lookup(solution, iterations)

        if error is not None:
            return error

        try:
            return service.hand(path, cards)
        except IllegalPath as exception:
            return illegal(exception)
        except BadHand as exception:
            return JSONResponse(
                status_code=400,
                content={"error": "bad_hand", "detail": str(exception)},
            )

    return app


def load_service(
    checkpoint: Path,
    *,
    solution: str,
    iterations: int,
) -> QueryService:
    loaded = load_strategy_checkpoint(checkpoint)

    return QueryService(
        strategy_index=loaded.strategy_index,
        metadata=loaded.metadata,
        solution=solution,
        iterations=iterations,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--solution", required=True)
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument(
        "--checkpoint",
        help="Default: the solution's checkpoint in solutions/manifest.json.",
    )
    parser.add_argument("--manifest", default="solutions/manifest.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.checkpoint:
        checkpoint = Path(args.checkpoint)
    else:
        manifest_path = Path(args.manifest)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["solutions"][args.solution]["checkpoints"]
        entry = next(
            item for item in entries
            if item["iterations"] == args.iterations
        )
        checkpoint = manifest_path.parent / entry["path"]

    print(f"Loading {checkpoint} ...", flush=True)

    service = load_service(
        checkpoint,
        solution=args.solution,
        iterations=args.iterations,
    )

    import uvicorn

    uvicorn.run(
        create_app({(args.solution, args.iterations): service}),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
