"""
Query service for the D1 API (docs/API.md). Framework-free: takes a
path (and cards) and returns the JSON-ready dicts of section 4.

Slice 1 (day69): node and hand queries, discard advice on the actual
cards, and ranges conditioned on the action path for both players
while they still hold their starting hands (predraw betting and the
draw before that player's own draw). Ranges after a player's draw need
the draw transition and are reported as unavailable (next slice, the
former D2 scope). Strategies are read from a StrategyIndex; the SQLite
store for v2-scale checkpoints is the next slice as well.
"""

from dataclasses import dataclass

from solver.actions import DiscardAction
from solver.bucket_hand_codec import actual_discard_action_for_bucket_hand
from solver.checkpoint_evaluation import EvaluationSetup, setup_from_metadata
from solver.draw_hand_bucket import draw_hand_bucket
from solver.hand import Hand
from solver.hand_classes import POSTDRAW_CLASSES, postdraw_class
from solver.postdraw_strength_bucket import postdraw_strength_bucket
from solver.public_legal_actions import PublicDrawAction

from product.api.hand_data import bucket_combos
from product.api.paths import (
    POSITIONS,
    IllegalPath,
    action_token,
    legal_public_actions,
    solver_action,
    walk,
)


API_VERSION = "0.2-draft"

# Range summaries group hands by the made-hand type of the cards held
# (D3 postdraw classes). Splitting each type by the probability of
# making a good hand (D3 v1, docs/HAND_TAXONOMY.md 6.3) comes later.
TAXONOMY_VERSION = "d3-v1-types"

# Provisional: normalized distance from uniform below this counts as
# near uniform. Normalizing by the maximum, 1 - 1/n, makes nodes with
# 2 and 32 actions comparable (docs/API.md 9.1); the threshold itself
# is to be set from convergence data.
NEAR_UNIFORM_NORMALIZED = 0.05

TYPE_LABELS = {
    hand_class.key: hand_class.label
    for hand_class in POSTDRAW_CLASSES
}

TYPE_ORDER = [hand_class.key for hand_class in POSTDRAW_CLASSES]


class BadHand(ValueError):
    pass


def round_chips(value: float) -> float:
    return round(value + 0.0, 1)


def normalized_distance_from_uniform(strategy: dict) -> float:
    count = len(strategy)

    if count <= 1:
        return 0.0

    uniform = 1.0 / count

    distance = 0.5 * sum(
        abs(probability - uniform)
        for probability in strategy.values()
    )

    return distance / (1.0 - uniform)


def strategy_status(strategy: dict | None) -> str:
    if strategy is None:
        return "missing"

    if (
        len(strategy) > 1
        and normalized_distance_from_uniform(strategy)
        < NEAR_UNIFORM_NORMALIZED
    ):
        return "near_uniform"

    return "trained"


def hand_key_for(hand: Hand, phase: str):
    """Same dispatch as InformationState for the bucket abstraction."""
    if phase == "postdraw_betting":
        return postdraw_strength_bucket(hand)

    return draw_hand_bucket(hand)


def public_frequencies(strategy: dict, actions) -> dict[str, float]:
    """
    Solver-action probabilities folded into public action tokens:
    betting actions one to one, discards summed by draw count.
    """
    frequencies = {action_token(action): 0.0 for action in actions}

    for action, probability in strategy.items():
        if isinstance(action, DiscardAction):
            frequencies[f"D{action.draw_count}"] += probability
        else:
            for public in actions:
                if (
                    not isinstance(public, PublicDrawAction)
                    and solver_action(public) == action
                ):
                    frequencies[action_token(public)] += probability
                    break
            else:
                raise ValueError(
                    f"Strategy action {action} is not a legal "
                    "public action here."
                )

    return frequencies


def parse_cards(cards: str | list[str]) -> Hand:
    items = (
        [card for card in cards.replace(",", " ").split() if card]
        if isinstance(cards, str)
        else list(cards)
    )

    if len(items) != 5 and isinstance(cards, str) and len(cards) == 10:
        items = [cards[index:index + 2] for index in range(0, 10, 2)]

    if len(items) != 5:
        raise BadHand("Give exactly five cards, e.g. 7s5h4d3c2s.")

    try:
        hand = Hand.from_strings(*items)
    except ValueError as error:
        raise BadHand(str(error)) from error

    return hand


@dataclass
class QueryService:
    strategy_index: object
    metadata: object
    solution: str
    iterations: int

    def __post_init__(self) -> None:
        if self.metadata.abstraction != "bucket":
            raise ValueError("The API supports bucket checkpoints only.")

        self.setup: EvaluationSetup = setup_from_metadata(self.metadata)
        self.combos = bucket_combos()

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _strategy(self, public_node, seat: int, hand_key):
        return self.strategy_index.strategy_for_hand(
            public_node=public_node,
            observer_seat=seat,
            hand_key=hand_key,
        )

    def _header(self, path, navigator, decisions) -> dict:
        game = navigator.game
        node = navigator.public_node()
        actor = navigator.acting_seat

        stacks = {
            POSITIONS[player.seat]: round_chips(player.stack)
            for player in node.players
        }

        to_call = 0.0

        if actor is not None and node.phase != "draw":
            committed = {
                player.seat: player.committed_this_round
                for player in node.players
            }
            to_call = max(0.0, node.current_bet - committed[actor])

        return {
            "api_version": API_VERSION,
            "taxonomy_version": TAXONOMY_VERSION,
            "solution": self.solution,
            "iterations": self.iterations,
            "path": "/".join(decision.token for decision in decisions),
            "history": [
                {
                    "position": POSITIONS[decision.seat],
                    "token": decision.token,
                    "label": decision.action.label,
                }
                for decision in decisions
            ],
            "phase": node.phase,
            "actor": None if actor is None else POSITIONS[actor],
            "terminal": navigator.is_terminal,
            "pot": round_chips(node.pot),
            "to_call": round_chips(to_call),
            "stacks": stacks,
            "_game": game,
            "_node": node,
            "_actor": actor,
        }

    @staticmethod
    def _action_rows(actions) -> list[dict]:
        rows = []

        for action in actions:
            row = {
                "token": action_token(action),
                "label": action.label,
            }

            if isinstance(action, PublicDrawAction):
                row.update(kind="draw", draw_count=action.draw_count)
            else:
                row["kind"] = action.action_type.value

                if action.raise_to is not None:
                    row.update(
                        raise_to=round_chips(action.raise_to),
                        pot_fraction=action.pot_fraction,
                        is_all_in=action.is_all_in,
                    )

            rows.append(row)

        return rows

    # ------------------------------------------------------------
    # Ranges conditioned on the path
    # ------------------------------------------------------------

    def _range_weights(self, seat: int, decisions) -> dict | None:
        """
        {bucket: reach probability of the seat's own actions on the
        path}, or None once the seat has drawn (its holding changed).
        """
        own = [decision for decision in decisions if decision.seat == seat]

        if any(decision.phase == "draw" for decision in own):
            return None

        weights = {}

        for bucket in self.combos:
            reach = 1.0

            for decision in own:
                strategy = self._strategy(
                    decision.public_node, seat, bucket
                )
                target = solver_action(decision.action)

                if strategy is None:
                    # Same uniform fallback as the evaluator.
                    reach *= 1.0 / decision.legal_count
                else:
                    reach *= strategy.get(target, 0.0)

                if reach == 0.0:
                    break

            weights[bucket] = reach

        return weights

    def _range_summary(self, seat, weights, actor_strategy=None, actions=None):
        if weights is None:
            return {
                "available": False,
                "reason": (
                    "the player has drawn; ranges after the draw need "
                    "the draw transition (next slice)"
                ),
            }

        by_type: dict[str, dict] = {}
        total = 0.0

        for bucket, reach in weights.items():
            if reach == 0.0:
                continue

            strategy = (
                actor_strategy(bucket) if actor_strategy else None
            )

            for type_key, combos in self.combos[bucket].items():
                weight = reach * combos
                total += weight

                row = by_type.setdefault(
                    type_key,
                    {
                        "weight": 0.0,
                        "frequencies": None if actions is None else {
                            action_token(action): 0.0
                            for action in actions
                        },
                        "trained": 0.0,
                    },
                )
                row["weight"] += weight

                if actions is not None:
                    if strategy is None:
                        share = 1.0 / len(actions)
                        for token in row["frequencies"]:
                            row["frequencies"][token] += weight * share
                    else:
                        for token, probability in public_frequencies(
                            strategy, actions
                        ).items():
                            row["frequencies"][token] += weight * probability

                        if strategy_status(strategy) == "trained":
                            row["trained"] += weight

        classes = []
        overall = (
            None
            if actions is None
            else {action_token(action): 0.0 for action in actions}
        )

        for type_key in TYPE_ORDER:
            row = by_type.get(type_key)

            if row is None:
                continue

            entry = {
                "key": type_key,
                "label": TYPE_LABELS[type_key],
                "combos": round(row["weight"], 3),
                "share": row["weight"] / total if total else 0.0,
            }

            if actions is not None:
                entry["frequencies"] = {
                    token: value / row["weight"]
                    for token, value in row["frequencies"].items()
                }
                entry["trained_share"] = row["trained"] / row["weight"]

                for token, value in row["frequencies"].items():
                    overall[token] += value / total

            classes.append(entry)

        summary = {
            "available": True,
            "position": POSITIONS[seat],
            "weighting": "conditioned_on_path",
            "types": "made_hand_type",
            "combos": round(total, 3),
            "classes": classes,
        }

        if overall is not None:
            summary["overall"] = overall

        return summary

    # ------------------------------------------------------------
    # Public queries
    # ------------------------------------------------------------

    def node(self, path: str) -> dict:
        navigator, decisions = walk(self.setup, path)
        header = self._header(path, navigator, decisions)

        game = header.pop("_game")
        node = header.pop("_node")
        actor = header.pop("_actor")

        actions = (
            ()
            if navigator.is_terminal
            else legal_public_actions(game, self.setup)
        )

        header["actions"] = self._action_rows(actions)

        ranges = {}

        for seat in (0, 1):
            weights = self._range_weights(seat, decisions)

            is_actor = seat == actor

            ranges[POSITIONS[seat]] = self._range_summary(
                seat,
                weights,
                actor_strategy=(
                    (lambda bucket: self._strategy(node, seat, bucket))
                    if is_actor
                    else None
                ),
                actions=actions if is_actor else None,
            )

        header["ranges"] = ranges

        return header

    def hand(self, path: str, cards) -> dict:
        hand = parse_cards(cards)
        navigator, decisions = walk(self.setup, path)

        if navigator.is_terminal:
            raise IllegalPath("(end)", [])

        header = self._header(path, navigator, decisions)
        game = header.pop("_game")
        node = header.pop("_node")
        actor = header.pop("_actor")

        actions = legal_public_actions(game, self.setup)
        hand_key = hand_key_for(hand, node.phase)
        strategy = self._strategy(node, actor, hand_key)

        result = {
            **header,
            "cards": [card.rank + card.suit for card in hand.cards],
            "hand_type": {
                "key": postdraw_class(hand).key,
                "label": postdraw_class(hand).label,
            },
            "hand_key": f"{type(hand_key).__name__}:{hand_key!r}",
            "status": strategy_status(strategy),
            "distance_from_uniform": (
                None
                if strategy is None
                else normalized_distance_from_uniform(strategy)
            ),
            "frequencies": (
                None
                if strategy is None
                else public_frequencies(strategy, actions)
            ),
            "ev": None,
        }

        if node.phase == "draw" and strategy is not None:
            discards = []

            for action, probability in strategy.items():
                physical = actual_discard_action_for_bucket_hand(
                    hand=hand,
                    action=action,
                )

                discards.append(
                    {
                        "draw_count": action.draw_count,
                        "throw": [
                            hand.cards[index].rank + hand.cards[index].suit
                            for index in physical.discard_indices
                        ],
                        "probability": probability,
                    }
                )

            discards.sort(
                key=lambda row: (-row["probability"], row["throw"])
            )

            result["discards"] = discards

        return result
