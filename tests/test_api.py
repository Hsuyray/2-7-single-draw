"""
D1 query API, slice 1 (product/api): paths, strategies, hand mode,
conditioned ranges and the HTTP layer, on a small trained checkpoint.
"""

import random
from collections import deque

import pytest
from fastapi.testclient import TestClient

from product.api.app import create_app, load_service
from product.api.hand_data import TOTAL_HANDS, bucket_combos
from product.api.paths import (
    IllegalPath,
    action_token,
    legal_public_actions,
    solver_action,
    walk,
)
from product.api.service import hand_key_for, public_frequencies
from scripts import save_training_checkpoint
from solver.draw_hand_bucket import draw_hand_bucket
from solver.hand import Hand
from solver.hand_classes import combination_counts, postdraw_class
from solver.information_state import InformationState
from solver.public_legal_actions import PublicDrawAction
from solver.public_node_navigator import PublicNodeNavigator
from solver.single_draw_game import SingleDrawGame


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    path = tmp_path_factory.mktemp("api") / "tiny.chk.gz"

    save_training_checkpoint.main(
        [
            "--max-draw", "5",
            "--abstraction", "bucket",
            "--bet-sizing", "full",
            "--iterations", "12",
            "--batch-size", "12",
            "--output", str(path),
        ]
    )

    return load_service(path, solution="tiny", iterations=12)


def bfs_paths(service, limit):
    queue = deque([""])
    seen = []

    while queue and len(seen) < limit:
        path = queue.popleft()
        navigator, _ = walk(service.setup, path)
        seen.append((path, navigator))

        if navigator.is_terminal:
            continue

        for action in legal_public_actions(navigator.game, service.setup):
            token = action_token(action)
            queue.append(f"{path}/{token}" if path else token)

    return seen


def test_tokens_are_unique_and_walk_back(service) -> None:
    for path, navigator in bfs_paths(service, 400):
        if navigator.is_terminal:
            continue

        actions = legal_public_actions(navigator.game, service.setup)
        tokens = [action_token(action) for action in actions]

        assert len(tokens) == len(set(tokens))

        for token in tokens:
            child = f"{path}/{token}" if path else token
            _, decisions = walk(service.setup, child)
            assert "/".join(d.token for d in decisions) == child


def test_illegal_path_reports_legal_tokens(service) -> None:
    with pytest.raises(IllegalPath) as error:
        walk(service.setup, "R51")

    assert error.value.at == "R51"
    assert "R50" in error.value.legal


def test_positions_follow_training_seats(service) -> None:
    assert service.node("")["actor"] == "BTN"
    assert service.node("R50")["actor"] == "BB"
    # The big blind draws first, the button second.
    assert service.node("R50/C")["actor"] == "BB"
    assert service.node("R50/C/D1")["actor"] == "BTN"
    assert service.node("R50/C/D1/D2")["actor"] == "BB"


def test_every_stored_strategy_maps_to_public_actions(service) -> None:
    index = service.strategy_index
    checked = 0

    for _, navigator in bfs_paths(service, 600):
        if navigator.is_terminal:
            continue

        node = navigator.public_node()
        actions = legal_public_actions(navigator.game, service.setup)
        table = index._by_public_node.get((node, navigator.acting_seat), {})

        for strategy in table.values():
            frequencies = public_frequencies(strategy, actions)
            assert sum(frequencies.values()) == pytest.approx(1.0)
            checked += 1

    assert checked > 0


def test_hand_key_matches_information_state(service) -> None:
    rng = random.Random(4)

    for deal in range(30):
        game = SingleDrawGame(
            config=service.setup.game_config,
            button_seat=0,
            deck_seed=1000 + deal,
        )
        navigator = PublicNodeNavigator.from_game(game)

        for _ in range(8):
            if navigator.is_terminal:
                break

            seat = navigator.acting_seat
            state = InformationState.from_game(
                navigator.game,
                observer_seat=seat,
                abstraction="bucket",
            )

            assert hand_key_for(
                navigator.game.hands[seat],
                state.phase,
            ) == state.own_hand_key

            action = rng.choice(
                legal_public_actions(navigator.game, service.setup)
            )

            if isinstance(action, PublicDrawAction):
                navigator.apply_draw(
                    discard_indices=tuple(range(action.draw_count))
                )
            else:
                navigator.apply_betting(
                    action.action_type,
                    raise_to=action.raise_to,
                )


def test_root_range_is_every_hand(service) -> None:
    ranges = service.node("")["ranges"]
    expected = combination_counts("postdraw")

    for position in ("BTN", "BB"):
        summary = ranges[position]

        assert summary["available"]
        assert summary["combos"] == pytest.approx(TOTAL_HANDS)

        for row in summary["classes"]:
            assert row["combos"] == pytest.approx(expected[row["key"]])

    overall = ranges["BTN"]["overall"]
    assert sum(overall.values()) == pytest.approx(1.0)


def test_range_is_conditioned_on_own_actions(service) -> None:
    node = service.node("R50")
    root, _ = walk(service.setup, "")
    root_node = root.public_node()

    raise_action = next(
        action
        for action in legal_public_actions(root.game, service.setup)
        if action_token(action) == "R50"
    )
    target = solver_action(raise_action)

    expected = 0.0

    for bucket, types in bucket_combos().items():
        strategy = service.strategy_index.strategy_for_hand(
            public_node=root_node,
            observer_seat=0,
            hand_key=bucket,
        )
        reach = (
            1.0 / 8
            if strategy is None
            else strategy.get(target, 0.0)
        )
        expected += reach * sum(types.values())

    assert node["ranges"]["BTN"]["combos"] == pytest.approx(
        expected, rel=1e-9
    )
    # BB has not acted yet.
    assert node["ranges"]["BB"]["combos"] == pytest.approx(TOTAL_HANDS)


def test_range_unavailable_after_own_draw(service) -> None:
    ranges = service.node("R50/C/D1")["ranges"]

    assert ranges["BB"]["available"] is False
    assert ranges["BTN"]["available"] is True


def find_draw_hand(service):
    """A draw node and a hand whose bucket has a stored strategy."""
    rng = random.Random(5)
    deck = [rank + suit for rank in "23456789TJQKA" for suit in "shdc"]

    for path, navigator in bfs_paths(service, 300):
        if navigator.is_terminal or navigator.public_node().phase != "draw":
            continue

        table = service.strategy_index._by_public_node.get(
            (navigator.public_node(), navigator.acting_seat), {}
        )

        if not table:
            continue

        for _ in range(20000):
            cards = rng.sample(deck, 5)

            if draw_hand_bucket(Hand.from_strings(*cards)) in table:
                return path, "".join(cards)

    raise AssertionError("no draw node with a stored strategy")


def test_hand_mode_on_a_draw_node(service) -> None:
    path, cards = find_draw_hand(service)
    result = service.hand(path, cards)

    assert result["phase"] == "draw"
    assert result["status"] != "missing"
    assert sum(result["frequencies"].values()) == pytest.approx(1.0)

    by_count = {}

    for row in result["discards"]:
        assert len(row["throw"]) == row["draw_count"]
        assert set(row["throw"]) <= set(result["cards"])
        by_count[row["draw_count"]] = (
            by_count.get(row["draw_count"], 0.0) + row["probability"]
        )

    for count, probability in by_count.items():
        assert result["frequencies"][f"D{count}"] == pytest.approx(
            probability
        )

    # A hand with no stored strategy reports missing, not uniform.
    missing = service.hand("R50/C/D1/D2", "7s5h4d3c2s")
    if missing["status"] == "missing":
        assert missing["frequencies"] is None


def test_bucket_combos_data() -> None:
    combos = bucket_combos()

    assert sum(
        sum(types.values()) for types in combos.values()
    ) == TOTAL_HANDS

    rng = random.Random(8)
    deck = [rank + suit for rank in "23456789TJQKA" for suit in "shdc"]

    for _ in range(2000):
        hand = Hand.from_strings(*rng.sample(deck, 5))
        assert postdraw_class(hand).key in combos[draw_hand_bucket(hand)]


def test_http_layer(service) -> None:
    client = TestClient(create_app({("tiny", 12): service}))

    response = client.get("/v0/solutions")
    assert response.status_code == 200
    assert response.json()["solutions"][0]["id"] == "tiny"

    response = client.get("/v0/solutions/tiny/12/node", params={"path": "R50/C"})
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "draw"
    assert [row["token"] for row in body["actions"]][0] == "D0"

    response = client.get("/v0/solutions/tiny/12/node", params={"path": "R51"})
    assert response.status_code == 404
    assert response.json()["error"] == "illegal_action"

    response = client.get(
        "/v0/solutions/tiny/12/hand",
        params={"path": "", "cards": "7s7s4d3c2s"},
    )
    assert response.status_code == 400

    response = client.get("/v0/solutions/other/1/node")
    assert response.status_code == 404
    assert response.json()["error"] == "unknown_solution"
