import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solver.action_executor import apply_solver_action  # noqa: E402
from solver.bet_sizing import FULL_BET_SIZING  # noqa: E402
from solver.game_state import GameConfig  # noqa: E402
from solver.legal_actions import legal_actions  # noqa: E402
from solver.single_draw_game import SingleDrawGame  # noqa: E402


DEPTH_LIMIT = 40
NODE_LIMIT = 200_000

found_deep_path = False
nodes_visited = 0


def describe_state(game, action_count, chosen):
    state = (
        game.betting_state
        if hasattr(game, "betting_state")
        else None
    )

    return (
        f"[{action_count}] phase={game.phase} "
        f"acting_seat={getattr(state, 'acting_seat', None)} "
        f"current_bet={getattr(state, 'current_bet', None)} "
        f"min_raise_size={getattr(state, 'minimum_raise_size', None)} "
        f"chosen={chosen}"
    )


def dfs(game, depth, history, deck_seed):
    global found_deep_path, nodes_visited

    if found_deep_path:
        return

    nodes_visited += 1

    if nodes_visited % 5000 == 0:
        print(f"...visited {nodes_visited} nodes so far")

    if nodes_visited > NODE_LIMIT:
        print(
            f"NODE LIMIT REACHED ({NODE_LIMIT}) "
            f"without finding a deep path or "
            f"finishing the search."
        )
        found_deep_path = True
        return

    if game.phase.name == "COMPLETE":
        return

    if depth > DEPTH_LIMIT:
        print(f"DEEP PATH FOUND, deck_seed={deck_seed}")
        for line in history:
            print(line)
        found_deep_path = True
        return

    actions = legal_actions(
        game,
        max_draw=1,
        raise_sizes=None,
        bet_sizing_policy=FULL_BET_SIZING,
    )

    if not actions:
        return

    for action in actions:
        if found_deep_path:
            return

        next_game = apply_solver_action(game, action)

        history.append(
            describe_state(game, depth, action)
        )

        dfs(next_game, depth + 1, history, deck_seed)

        history.pop()


def search(deck_seeds):

    for deck_seed in deck_seeds:
        if found_deep_path:
            return

        print(f"Searching deck_seed={deck_seed}...")

        game = SingleDrawGame(
            config=GameConfig(
                player_count=2,
                starting_stack=20.0,
                small_blind=1.0,
                big_blind=2.0,
                big_blind_ante=1.5,
            ),
            button_seat=0,
            deck_seed=deck_seed,
        )

        dfs(game, 0, [], deck_seed)

    if not found_deep_path:
        print(
            "No path exceeding depth "
            f"{DEPTH_LIMIT} found."
        )


if __name__ == "__main__":
    search(range(0, 3))