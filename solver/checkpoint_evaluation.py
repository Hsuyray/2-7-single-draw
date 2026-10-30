"""
Checkpoint-only evaluation (workstream A2).

Everything here evaluates the StrategyIndex stored in a
checkpoint. Nothing retrains. The game rules and action
abstraction are rebuilt from the checkpoint metadata, and
play goes through the same solver-action path as training
(StrategyProfileEvaluator, which reuses CFRTrainer).

Determinism: every section draws its RNG seed and its deck
seeds from (seed, section label) only, so enabling or
disabling one section never changes another. Deck seeds
start at EVALUATION_DECK_SEED_BASE, far above the training
seeds (42 + game counter), so evaluation deals never reuse
training deals.

See docs/A2_DESIGN.md.
"""

import hashlib
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from statistics import median
from time import perf_counter

from solver.best_response import (
    SampledBestResponse,
)
from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.game_state import (
    CHIP_EPSILON,
    GameConfig,
)
from solver.information_state import (
    AbstractionMode,
    InformationState,
)
from solver.legal_actions import (
    DrawActionMode,
    SolverAction,
)
from solver.postdraw_strength_bucket import (
    postdraw_bucket_count,
)
from solver.public_state import (
    PublicNodeKey,
)
from solver.response_grouping import (
    coarse_grouping,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_checkpoint import (
    StrategyCheckpointMetadata,
)
from solver.strategy_index import (
    Strategy,
    StrategyIndex,
)
from solver.strategy_profile_evaluator import (
    CallStationPolicy,
    HeadToHeadEvaluator,
    StrategyIndexPolicy,
    StrategyProfileEvaluator,
    UniformPolicy,
    standard_error,
)


EVALUATION_DECK_SEED_BASE = 1_000_000_000

PHASES = (
    "predraw_betting",
    "draw",
    "postdraw_betting",
)

NEAR_UNIFORM_TOLERANCE = 1e-6
DETERMINISTIC_THRESHOLD = 0.999
STRATEGY_SUM_TOLERANCE = 1e-9

# Metadata fields that define the game and the
# action abstraction. Two checkpoints can only
# be compared head-to-head when all are equal.
CONFIG_FIELDS = (
    "abstraction",
    "max_draw",
    "draw_action_mode",
    "raise_sizes",
    "bet_sizing_mode",
    "bet_pot_fractions",
    "bet_include_all_in",
    "bet_all_in_threshold",
    "bet_chip_increment",
    "player_count",
    "starting_stack",
    "starting_stacks",
    "small_blind",
    "big_blind",
    "big_blind_ante",
    "postdraw_bucket_count",
)


class CheckpointConfigError(ValueError):
    pass


# ----------------------------------------------------------------
# Seeds and deals
# ----------------------------------------------------------------


def derive_seed(
    seed: int,
    *labels: object,
) -> int:
    """
    Stable 31-bit seed from a base seed and labels.

    Uses sha256, not hash(), so it does not depend
    on PYTHONHASHSEED.
    """
    text = repr(
        (seed,)
        + labels
    )

    digest = hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).digest()

    return int.from_bytes(
        digest[:4],
        "big",
    ) & 0x7FFFFFFF


def deck_seed_base(
    seed: int,
    *labels: object,
) -> int:
    return (
        EVALUATION_DECK_SEED_BASE
        + derive_seed(
            seed,
            "deck",
            *labels,
        )
    )


def make_deal_factory(
    game_config: GameConfig,
    *,
    first_deck_seed: int,
    button_seat: int = 0,
) -> Callable[[], SingleDrawGame]:
    """
    Sequential deck seeds, fixed button.

    Training always uses button_seat=0 and
    PublicNodeKey stores the absolute button seat,
    so button 0 is the training distribution.
    """
    counter = 0

    def factory() -> SingleDrawGame:
        nonlocal counter

        game = SingleDrawGame(
            config=game_config,
            button_seat=button_seat,
            deck_seed=(
                first_deck_seed
                + counter
            ),
        )

        counter += 1

        return game

    return factory


# ----------------------------------------------------------------
# Rebuilding the game from metadata
# ----------------------------------------------------------------


@dataclass(frozen=True)
class AssumedGameConfig:
    """
    Explicit values for checkpoints whose metadata
    predates the v3 game-config fields.
    """

    starting_stack: float
    small_blind: float
    big_blind: float
    big_blind_ante: float


@dataclass(frozen=True)
class EvaluationSetup:
    game_config: GameConfig
    abstraction: AbstractionMode
    max_draw: int
    raise_sizes: (
        tuple[float, ...]
        | None
    )
    bet_sizing_policy: (
        BetSizingPolicy
        | None
    )
    draw_action_mode: DrawActionMode

    # Values filled in from AssumedGameConfig
    # rather than read from the metadata.
    assumed_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        config = self.game_config

        policy = self.bet_sizing_policy

        return {
            "abstraction": self.abstraction,
            "max_draw": self.max_draw,
            "draw_action_mode": (
                self.draw_action_mode
            ),
            "raise_sizes": _jsonable(
                self.raise_sizes
            ),
            "bet_sizing_policy": (
                None
                if policy is None
                else {
                    "pot_fractions": list(
                        policy.pot_fractions
                    ),
                    "include_all_in": (
                        policy.include_all_in
                    ),
                    "all_in_threshold": (
                        policy.all_in_threshold
                    ),
                    "chip_increment": (
                        policy.chip_increment
                    ),
                }
            ),
            "game_config": {
                "player_count": (
                    config.player_count
                ),
                "starting_stack": (
                    config.starting_stack
                ),
                "starting_stacks": _jsonable(
                    config.starting_stacks
                ),
                "small_blind": (
                    config.small_blind
                ),
                "big_blind": config.big_blind,
                "big_blind_ante": (
                    config.big_blind_ante
                ),
            },
            "assumed_fields": list(
                self.assumed_fields
            ),
        }


def setup_from_metadata(
    metadata: StrategyCheckpointMetadata,
    *,
    assumed: (
        AssumedGameConfig
        | None
    ) = None,
) -> EvaluationSetup:
    """
    Rebuild game config and action abstraction.

    Missing game-config fields are an error unless
    `assumed` supplies them: silently defaulting
    would evaluate a different game.
    """
    if (
        metadata.player_count is not None
        and metadata.player_count != 2
    ):
        raise CheckpointConfigError(
            "Only heads-up checkpoints are "
            "supported."
        )

    assumed_fields: list[str] = []

    def required(
        name: str,
    ) -> float:
        value = getattr(
            metadata,
            name,
        )

        if value is not None:
            return value

        if assumed is None:
            raise CheckpointConfigError(
                f"Checkpoint metadata has no "
                f"{name} (format version "
                f"{metadata.format_version}); "
                "pass an assumed game config."
            )

        assumed_fields.append(
            name
        )

        return getattr(
            assumed,
            name,
        )

    game_config = GameConfig(
        player_count=2,
        starting_stack=required(
            "starting_stack"
        ),
        starting_stacks=(
            metadata.starting_stacks
        ),
        small_blind=required(
            "small_blind"
        ),
        big_blind=required(
            "big_blind"
        ),
        big_blind_ante=required(
            "big_blind_ante"
        ),
    )

    mode = metadata.bet_sizing_mode

    if mode == "none":
        raise_sizes: (
            tuple[float, ...]
            | None
        ) = ()
        policy = None

    elif mode == "fixed":
        if not metadata.raise_sizes:
            raise CheckpointConfigError(
                "Fixed bet sizing without "
                "raise sizes."
            )

        raise_sizes = tuple(
            metadata.raise_sizes
        )
        policy = None

    elif mode == "policy":
        fields = (
            metadata.bet_pot_fractions,
            metadata.bet_include_all_in,
            metadata.bet_all_in_threshold,
            metadata.bet_chip_increment,
        )

        if any(
            value is None
            for value in fields
        ):
            raise CheckpointConfigError(
                "Policy bet sizing with "
                "incomplete policy metadata."
            )

        raise_sizes = None
        policy = BetSizingPolicy(
            pot_fractions=tuple(
                metadata.bet_pot_fractions
            ),
            include_all_in=(
                metadata.bet_include_all_in
            ),
            all_in_threshold=(
                metadata.bet_all_in_threshold
            ),
            chip_increment=(
                metadata.bet_chip_increment
            ),
        )

    else:
        raise CheckpointConfigError(
            f"Unknown bet sizing mode "
            f"{mode!r}."
        )

    if metadata.draw_action_mode not in {
        "full",
        "candidate",
    }:
        raise CheckpointConfigError(
            f"Unknown draw action mode "
            f"{metadata.draw_action_mode!r}."
        )

    if (
        metadata.abstraction == "bucket"
        and metadata.postdraw_bucket_count
        is not None
        and metadata.postdraw_bucket_count
        != postdraw_bucket_count()
    ):
        raise CheckpointConfigError(
            "Checkpoint postdraw bucket count "
            f"{metadata.postdraw_bucket_count} "
            "differs from the code's "
            f"{postdraw_bucket_count()}."
        )

    return EvaluationSetup(
        game_config=game_config,
        abstraction=metadata.abstraction,
        max_draw=metadata.max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=policy,
        draw_action_mode=(
            metadata.draw_action_mode
        ),
        assumed_fields=tuple(
            assumed_fields
        ),
    )


def incompatible_fields(
    first: StrategyCheckpointMetadata,
    second: StrategyCheckpointMetadata,
) -> list[str]:
    """
    CONFIG_FIELDS whose values differ. Floats are
    compared with CHIP_EPSILON, never exactly.
    """
    return [
        name
        for name in CONFIG_FIELDS
        if not _values_match(
            getattr(
                first,
                name,
            ),
            getattr(
                second,
                name,
            ),
        )
    ]


def _values_match(
    first: object,
    second: object,
) -> bool:
    if isinstance(
        first,
        tuple,
    ) and isinstance(
        second,
        tuple,
    ):
        return len(first) == len(
            second
        ) and all(
            _values_match(
                left,
                right,
            )
            for left, right in zip(
                first,
                second,
            )
        )

    if (
        isinstance(
            first,
            float,
        )
        or isinstance(
            second,
            float,
        )
    ) and not isinstance(
        first,
        bool,
    ) and not isinstance(
        second,
        bool,
    ):
        if first is None or second is None:
            return first is second

        return abs(
            float(first)
            - float(second)
        ) <= CHIP_EPSILON

    return first == second


def make_profile_evaluator(
    strategy_index: StrategyIndex,
    setup: EvaluationSetup,
    *,
    random_seed: int,
) -> StrategyProfileEvaluator:
    return StrategyProfileEvaluator(
        strategy_index=strategy_index,
        abstraction=setup.abstraction,
        max_draw=setup.max_draw,
        raise_sizes=setup.raise_sizes,
        bet_sizing_policy=(
            setup.bet_sizing_policy
        ),
        draw_action_mode=(
            setup.draw_action_mode
        ),
        random_seed=random_seed,
    )


# ----------------------------------------------------------------
# Static statistics
# ----------------------------------------------------------------


def _stored_strategies(
    strategy_index: StrategyIndex,
) -> dict[
    InformationState,
    Strategy,
]:
    # Read-only access to the stored mapping.
    # StrategyIndex.strategies() makes a deep
    # defensive copy, which for a ~1M-state
    # checkpoint roughly doubles memory.
    return strategy_index._strategies


def static_statistics(
    strategy_index: StrategyIndex,
) -> dict:
    per_phase: dict[
        str,
        dict,
    ] = {}

    public_nodes: dict[
        str,
        set,
    ] = {}

    invalid_examples: list[str] = []

    for (
        state,
        strategy,
    ) in _stored_strategies(
        strategy_index
    ).items():
        phase = state.phase

        stats = per_phase.setdefault(
            phase,
            {
                "information_states": 0,
                "single_action": 0,
                "near_uniform": 0,
                "deterministic": 0,
                "invalid": 0,
            },
        )

        stats["information_states"] += 1

        public_nodes.setdefault(
            phase,
            set(),
        ).add(
            state.public_node
        )

        probabilities = [
            float(value)
            for value in strategy.values()
        ]

        total = sum(
            probabilities
        )

        if (
            not probabilities
            or any(
                not math.isfinite(value)
                or value < 0.0
                for value in probabilities
            )
            or abs(total - 1.0)
            > STRATEGY_SUM_TOLERANCE
        ):
            stats["invalid"] += 1

            if len(invalid_examples) < 5:
                invalid_examples.append(
                    repr(state)[:300]
                )

            continue

        if len(probabilities) == 1:
            stats["single_action"] += 1
            continue

        if _is_near_uniform(strategy):
            stats["near_uniform"] += 1

        if (
            max(probabilities)
            >= DETERMINISTIC_THRESHOLD
        ):
            stats["deterministic"] += 1

    for (
        phase,
        stats,
    ) in per_phase.items():
        stats["public_nodes"] = len(
            public_nodes[phase]
        )

        multi_action = (
            stats["information_states"]
            - stats["single_action"]
            - stats["invalid"]
        )

        stats["multi_action"] = multi_action

        stats["near_uniform_fraction"] = (
            stats["near_uniform"]
            / multi_action
            if multi_action
            else 0.0
        )

        stats["deterministic_fraction"] = (
            stats["deterministic"]
            / multi_action
            if multi_action
            else 0.0
        )

    return {
        "information_states": len(
            strategy_index
        ),
        "invalid_strategies": sum(
            stats["invalid"]
            for stats in per_phase.values()
        ),
        "invalid_examples": (
            invalid_examples
        ),
        "near_uniform_tolerance": (
            NEAR_UNIFORM_TOLERANCE
        ),
        "deterministic_threshold": (
            DETERMINISTIC_THRESHOLD
        ),
        "by_phase": {
            phase: per_phase[phase]
            for phase in _ordered_phases(
                per_phase
            )
        },
    }


# ----------------------------------------------------------------
# Coverage (self-play)
# ----------------------------------------------------------------


class CoverageObserver:
    """
    Collects per-decision statistics during
    StrategyProfileEvaluator.evaluate.
    """

    def __init__(self) -> None:
        self.matched: Counter = Counter()
        self.missing: Counter = Counter()

        # Phase of the first miss in each deal.
        self.first_miss: Counter = Counter()
        self.deals = 0

        self.missing_public_nodes: Counter = (
            Counter()
        )
        self.missing_hand_keys: Counter = (
            Counter()
        )

        # Matched decisions per information
        # state: a sampled estimate of the
        # profile's own reach.
        self.visits: Counter = Counter()

        # Matched multi-action decisions, and
        # those whose stored strategy is near
        # uniform (likely never really trained).
        self.multi_action: Counter = Counter()
        self.near_uniform: Counter = Counter()

        self.action_mismatches = 0
        self.action_mismatch_examples: list[
            dict
        ] = []

        self._missed_this_deal = False

    def on_deal_start(
        self,
        deal_index: int,
    ) -> None:
        self.deals += 1
        self._missed_this_deal = False

    def on_decision(
        self,
        *,
        game: SingleDrawGame,
        information_state: InformationState,
        actions: tuple[
            SolverAction,
            ...,
        ],
        strategy: Strategy | None,
    ) -> None:
        phase = information_state.phase

        if strategy is None:
            self.missing[phase] += 1

            if not self._missed_this_deal:
                self.first_miss[phase] += 1
                self._missed_this_deal = True

            self.missing_public_nodes[
                information_state.public_node
            ] += 1

            self.missing_hand_keys[
                (
                    phase,
                    information_state
                    .own_hand_key,
                )
            ] += 1

            return

        self.matched[phase] += 1

        self.visits[
            information_state
        ] += 1

        if len(strategy) > 1:
            self.multi_action[phase] += 1

            if _is_near_uniform(strategy):
                self.near_uniform[phase] += 1

        if set(strategy) != set(actions):
            self.action_mismatches += 1

            if (
                len(
                    self.action_mismatch_examples
                )
                < 5
            ):
                self.action_mismatch_examples.append(
                    {
                        "phase": phase,
                        "legal_actions": sorted(
                            repr(action)
                            for action in actions
                        ),
                        "strategy_actions": sorted(
                            repr(action)
                            for action in strategy
                        ),
                    }
                )

    def on_deal_end(
        self,
        *,
        seat_0_utility: float,
        seat_1_utility: float,
    ) -> None:
        pass


def evaluate_coverage(
    strategy_index: StrategyIndex,
    setup: EvaluationSetup,
    *,
    deals: int,
    seed: int,
    top: int,
    button_seat: int = 0,
    label: str = "coverage",
) -> tuple[
    dict,
    Counter,
]:
    """
    Self-play coverage. Returns the report section
    and the matched-visit counter (used for
    reach-weighted distances).
    """
    first_deck_seed = deck_seed_base(
        seed,
        label,
    )

    evaluator = make_profile_evaluator(
        strategy_index,
        setup,
        random_seed=derive_seed(
            seed,
            label,
            "policy",
        ),
    )

    observer = CoverageObserver()

    result = evaluator.evaluate(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=(
                first_deck_seed
            ),
            button_seat=button_seat,
        ),
        deals=deals,
        observer=observer,
    )

    phases = _ordered_phases(
        set(observer.matched)
        | set(observer.missing)
    )

    by_phase = {}

    for phase in phases:
        matched = observer.matched[phase]
        missing = observer.missing[phase]

        by_phase[phase] = _rate(
            matched,
            matched + missing,
        ) | {
            "matched": matched,
            "missing": missing,
            "near_uniform_played": (
                _rate(
                    observer.near_uniform[phase],
                    observer.multi_action[phase],
                )["rate"]
            ),
        }

    deals_with_miss = sum(
        observer.first_miss.values()
    )

    section = {
        "deals": deals,
        "button_seat": button_seat,
        "first_deck_seed": first_deck_seed,
        "policy_seed": derive_seed(
            seed,
            label,
            "policy",
        ),
        "overall": _rate(
            result.strategy_decisions,
            result.total_decisions,
        )
        | {
            "matched": (
                result.strategy_decisions
            ),
            "missing": (
                result
                .missing_strategy_decisions
            ),
        },
        "by_phase": by_phase,
        "first_miss": {
            "deals_with_miss": (
                deals_with_miss
            ),
            "rate": _rate(
                deals_with_miss,
                deals,
            )["rate"],
            "by_phase": {
                phase: observer.first_miss[
                    phase
                ]
                for phase in _ordered_phases(
                    observer.first_miss
                )
            },
        },
        "near_uniform_played": _rate(
            sum(
                observer.near_uniform.values()
            ),
            sum(
                observer.multi_action.values()
            ),
        ),
        "action_space_mismatches": (
            observer.action_mismatches
        ),
        "action_space_mismatch_examples": (
            observer
            .action_mismatch_examples
        ),
        "distinct_visited_states": len(
            observer.visits
        ),
        "top_missing_public_nodes": [
            describe_public_node(node)
            | {"count": count}
            for node, count in _top(
                observer.missing_public_nodes,
                top,
            )
        ],
        "top_missing_hand_keys": [
            {
                "phase": phase,
                "hand_key": repr(hand_key),
                "count": count,
            }
            for (
                phase,
                hand_key,
            ), count in _top(
                observer.missing_hand_keys,
                top,
            )
        ],
        "self_play": {
            "seat_0_utility": (
                result.seat_0_utility
            ),
            "seat_0_standard_error": (
                result.seat_0_standard_error
            ),
            "seat_1_utility": (
                result.seat_1_utility
            ),
            "seat_1_standard_error": (
                result.seat_1_standard_error
            ),
            "max_zero_sum_error": (
                result.max_zero_sum_error
            ),
        },
    }

    return (
        section,
        observer.visits,
    )


def describe_public_node(
    node: PublicNodeKey,
) -> dict:
    return {
        "phase": node.phase,
        "acting_seat": node.acting_seat,
        "button_seat": node.button_seat,
        "history_length": len(
            node.action_history
        ),
        "history": format_action_history(
            node
        ),
        "pot": node.pot,
        "current_bet": node.current_bet,
    }


PHASE_SHORT = {
    "predraw_betting": "pre",
    "draw": "draw",
    "postdraw_betting": "post",
}


def format_action_history(
    node: PublicNodeKey,
) -> str:
    """
    Compact history, e.g.
    "pre: s0 call, s1 raise 6 | draw: s1 draw 2".
    """
    groups: list[
        tuple[
            str,
            list[str],
        ]
    ] = []

    for action in node.action_history:
        if (
            not groups
            or groups[-1][0]
            != action.phase
        ):
            groups.append(
                (
                    action.phase,
                    [],
                )
            )

        token = (
            f"s{action.seat} "
            f"{action.action_type}"
        )

        if action.amount is not None:
            token += f" {action.amount:g}"

        if action.draw_count is not None:
            token += f" {action.draw_count}"

        groups[-1][1].append(
            token
        )

    return " | ".join(
        f"{PHASE_SHORT.get(phase, phase)}: "
        + ", ".join(tokens)
        for phase, tokens in groups
    )


# ----------------------------------------------------------------
# Distance to a previous checkpoint
# ----------------------------------------------------------------


def strategy_distance(
    current: StrategyIndex,
    previous: StrategyIndex,
    *,
    visits: Counter,
) -> dict:
    """
    L1 distance between average strategies on
    shared information states.

    Weighted by the current checkpoint's sampled
    self-play visits (checkpoints carry no strategy
    sums, so training weights are unavailable), and
    also unweighted over all shared states.
    """
    current_strategies = _stored_strategies(
        current
    )
    previous_strategies = _stored_strategies(
        previous
    )

    unweighted: dict[
        str,
        list[float],
    ] = {}

    action_set_mismatches = 0
    only_current = 0

    for (
        state,
        strategy,
    ) in current_strategies.items():
        other = previous_strategies.get(
            state
        )

        if other is None:
            only_current += 1
            continue

        distance = _l1(
            strategy,
            other,
        )

        if distance is None:
            action_set_mismatches += 1
            continue

        unweighted.setdefault(
            state.phase,
            [],
        ).append(
            distance
        )

    only_previous = sum(
        1
        for state in previous_strategies
        if state not in current_strategies
    )

    weighted: dict[
        str,
        list[float],
    ] = {}

    unmatched_visits: Counter = Counter()

    for (
        state,
        count,
    ) in visits.items():
        other = previous_strategies.get(
            state
        )

        distance = (
            None
            if other is None
            else _l1(
                current_strategies[state],
                other,
            )
        )

        if distance is None:
            unmatched_visits[
                state.phase
            ] += count
            continue

        sums = weighted.setdefault(
            state.phase,
            [0.0, 0.0],
        )

        sums[0] += distance * count
        sums[1] += count

    phases = _ordered_phases(
        set(unweighted)
        | set(weighted)
        | set(unmatched_visits)
    )

    by_phase = {}

    for phase in phases:
        values = sorted(
            unweighted.get(
                phase,
                [],
            )
        )

        sums = weighted.get(
            phase,
            [0.0, 0.0],
        )

        by_phase[phase] = {
            "shared_states": len(values),
            "mean_l1": (
                sum(values) / len(values)
                if values
                else None
            ),
            "median_l1": (
                median(values)
                if values
                else None
            ),
            "p90_l1": _percentile(
                values,
                0.9,
            ),
            "visit_weighted_l1": (
                sums[0] / sums[1]
                if sums[1]
                else None
            ),
            "weighted_visits": int(
                sums[1]
            ),
            "visits_not_in_previous": (
                unmatched_visits[phase]
            ),
        }

    total_weight = sum(
        sums[1]
        for sums in weighted.values()
    )

    return {
        "only_in_current": only_current,
        "only_in_previous": only_previous,
        "action_set_mismatches": (
            action_set_mismatches
        ),
        "visit_weighted_l1": (
            sum(
                sums[0]
                for sums in weighted.values()
            )
            / total_weight
            if total_weight
            else None
        ),
        "by_phase": by_phase,
    }


def _l1(
    first: Strategy,
    second: Strategy,
) -> float | None:
    if set(first) != set(second):
        return None

    return sum(
        abs(
            first[action]
            - second[action]
        )
        for action in first
    )


# ----------------------------------------------------------------
# Sampled best response (proxy, not exploitability)
# ----------------------------------------------------------------


# "coarse" = grouped SBR (A2_DESIGN 12.1): passed the
# v1 power test for both seats; "none" = the original
# per-information-set SBR, which failed it for seat 1.
SBR_GROUPINGS = {
    "none": None,
    "coarse": coarse_grouping,
}


def evaluate_sampled_best_response(
    strategy_index: StrategyIndex,
    setup: EvaluationSetup,
    *,
    seed: int,
    repeats: int,
    response_deals: int,
    validation_deals: int,
    sweeps: int,
    grouping: str = "none",
    progress: (
        Callable[[str], None]
        | None
    ) = None,
) -> tuple[
    dict,
    dict,
]:
    """
    Runs SampledBestResponse (grouping per
    SBR_GROUPINGS) `repeats` times per seat with independent
    response seeds and deals. The validation deals
    are the same for every run, so runs differ only
    in what the response learned.

    Returns (section, timing).
    """
    validation_first_seed = deck_seed_base(
        seed,
        "sbr",
        "validation",
    )

    runs: dict[
        int,
        list[dict],
    ] = {0: [], 1: []}

    timing: dict[
        str,
        float,
    ] = {}

    for repeat in range(repeats):
        for seat in (0, 1):
            response_first_seed = deck_seed_base(
                seed,
                "sbr",
                "response",
                seat,
                repeat,
            )

            policy_seed = derive_seed(
                seed,
                "sbr",
                "policy",
                seat,
                repeat,
            )

            optimizer = SampledBestResponse(
                strategy_index=strategy_index,
                abstraction=setup.abstraction,
                responder_seat=seat,
                max_draw=setup.max_draw,
                raise_sizes=setup.raise_sizes,
                bet_sizing_policy=(
                    setup.bet_sizing_policy
                ),
                draw_action_mode=(
                    setup.draw_action_mode
                ),
                random_seed=policy_seed,
                response_grouping=(
                    SBR_GROUPINGS[grouping]
                ),
            )

            started = perf_counter()

            result = optimizer.optimize(
                make_deal_factory(
                    setup.game_config,
                    first_deck_seed=(
                        response_first_seed
                    ),
                ),
                deals=response_deals,
                max_sweeps=sweeps,
                validation_game_factory=(
                    make_deal_factory(
                        setup.game_config,
                        first_deck_seed=(
                            validation_first_seed
                        ),
                    )
                ),
                validation_deals=(
                    validation_deals
                ),
            )

            elapsed = perf_counter() - started

            timing[
                f"seat{seat}_repeat{repeat}"
            ] = elapsed

            runs[seat].append(
                {
                    "repeat": repeat,
                    "response_first_deck_seed": (
                        response_first_seed
                    ),
                    "policy_seed": policy_seed,
                    "sweeps_completed": (
                        result.sweeps
                    ),
                    "baseline_value": (
                        result.baseline_value
                    ),
                    "baseline_standard_error": (
                        result
                        .baseline_standard_error
                    ),
                    "response_value": (
                        result.response_value
                    ),
                    "gain": result.improvement,
                    "gain_standard_error": (
                        result
                        .improvement_standard_error
                    ),
                    "information_states": (
                        result.information_states
                    ),
                    "changed_actions": (
                        result.changed_actions
                    ),
                    "opponent_strategy_coverage": (
                        result
                        .opponent_strategy_coverage
                    ),
                    "response_fallback_share": (
                        result
                        .response_fallback_share
                    ),
                    "response_fallback_tie_decisions": (
                        result
                        .response_fallback_tie_decisions
                    ),
                    "response_decisions": (
                        result
                        .response_policy_decisions
                        + result
                        .response_fallback_decisions
                    ),
                }
            )

            if progress is not None:
                progress(
                    f"  SBR seat {seat} "
                    f"repeat {repeat}: "
                    f"gain {result.improvement:+.4f} "
                    f"(se {result.improvement_standard_error:.4f}) "
                    f"in {elapsed:.1f}s"
                )

    seat_summaries = {
        f"seat_{seat}": _summary(
            [
                run["gain"]
                for run in runs[seat]
            ]
        )
        for seat in (0, 1)
    }

    # Per repeat: the mean of both seats' gains,
    # the usual exploitability-style aggregate.
    paired = [
        (
            runs[0][repeat]["gain"]
            + runs[1][repeat]["gain"]
        )
        / 2.0
        for repeat in range(repeats)
    ]

    section = {
        "grouping": grouping,
        "note": (
            "Lower-bound proxy, not exact "
            "exploitability. Gain = held-out "
            "response value minus held-out "
            "profile value for the responder "
            "seat. grouping 'coarse' learns one "
            "action per (seat, public node, "
            "coarse hand class) and plays the "
            "profile elsewhere; 'none' is the "
            "original per-state SBR, which is "
            "sample-starved (A2_DESIGN 11-12)."
        ),
        "repeats": repeats,
        "response_deals": response_deals,
        "validation_deals": validation_deals,
        "max_sweeps": sweeps,
        "validation_first_deck_seed": (
            validation_first_seed
        ),
        "runs": {
            f"seat_{seat}": runs[seat]
            for seat in (0, 1)
        },
        "gain_by_seat": seat_summaries,
        "mean_seat_gain": _summary(
            paired
        ),
    }

    return (
        section,
        timing,
    )


# ----------------------------------------------------------------
# Matches: fixed baselines and previous checkpoint
# ----------------------------------------------------------------


def make_head_to_head_evaluator(
    setup: EvaluationSetup,
    *,
    random_seed: int,
) -> HeadToHeadEvaluator:
    return HeadToHeadEvaluator(
        abstraction=setup.abstraction,
        max_draw=setup.max_draw,
        raise_sizes=setup.raise_sizes,
        bet_sizing_policy=(
            setup.bet_sizing_policy
        ),
        draw_action_mode=(
            setup.draw_action_mode
        ),
        random_seed=random_seed,
    )


BASELINE_OPPONENTS = {
    "uniform": UniformPolicy,
    "call_station": CallStationPolicy,
}


def evaluate_baselines(
    strategy_index: StrategyIndex,
    setup: EvaluationSetup,
    *,
    seed: int,
    deal_pairs: int,
) -> dict:
    section = {
        "deal_pairs": deal_pairs,
        "format": (
            "duplicate: each deck played twice "
            "with seats swapped; utility is the "
            "profile's chips per deal"
        ),
        "opponents": {},
    }

    for (
        name,
        opponent_type,
    ) in BASELINE_OPPONENTS.items():
        section["opponents"][name] = (
            _match(
                strategy_index,
                opponent_type(),
                setup,
                seed=seed,
                label=(
                    "baseline",
                    name,
                ),
                deal_pairs=deal_pairs,
            )
        )

    return section


def evaluate_head_to_head(
    current: StrategyIndex,
    previous: StrategyIndex,
    setup: EvaluationSetup,
    *,
    seed: int,
    deal_pairs: int,
) -> dict:
    return _match(
        current,
        StrategyIndexPolicy(previous),
        setup,
        seed=seed,
        label=("head_to_head",),
        deal_pairs=deal_pairs,
    )


def _match(
    strategy_index: StrategyIndex,
    opponent,
    setup: EvaluationSetup,
    *,
    seed: int,
    label: tuple[str, ...],
    deal_pairs: int,
) -> dict:
    first_deck_seed = deck_seed_base(
        seed,
        *label,
    )

    policy_seed = derive_seed(
        seed,
        *label,
        "policy",
    )

    result = make_head_to_head_evaluator(
        setup,
        random_seed=policy_seed,
    ).evaluate(
        make_deal_factory(
            setup.game_config,
            first_deck_seed=first_deck_seed,
        ),
        first=StrategyIndexPolicy(
            strategy_index
        ),
        second=opponent,
        deal_pairs=deal_pairs,
    )

    return {
        "deal_pairs": deal_pairs,
        "first_deck_seed": first_deck_seed,
        "policy_seed": policy_seed,
        "utility": result.first_utility,
        "standard_error": (
            result.first_standard_error
        ),
        "profile_coverage": (
            result.first_coverage
        ),
        "opponent_coverage": (
            result.second_coverage
        ),
        "max_zero_sum_error": (
            result.max_zero_sum_error
        ),
    }


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------


def _is_near_uniform(
    strategy: Strategy,
) -> bool:
    uniform = 1.0 / len(
        strategy
    )

    return all(
        abs(
            float(value)
            - uniform
        )
        <= NEAR_UNIFORM_TOLERANCE
        for value in strategy.values()
    )


def _ordered_phases(
    phases,
) -> list[str]:
    phases = set(phases)

    return [
        phase
        for phase in PHASES
        if phase in phases
    ] + sorted(
        phases
        - set(PHASES)
    )


def _rate(
    hits: int,
    total: int,
) -> dict:
    if total == 0:
        return {
            "rate": None,
            "standard_error": None,
            "total": 0,
        }

    rate = hits / total

    return {
        "rate": rate,
        # Binomial; decisions within a deal are
        # correlated, so this understates the
        # true error somewhat.
        "standard_error": math.sqrt(
            rate
            * (1.0 - rate)
            / total
        ),
        "total": total,
    }


def _top(
    counter: Counter,
    count: int,
) -> list:
    # Ties broken by repr so the order does not
    # depend on insertion or hash order.
    return sorted(
        counter.items(),
        key=lambda item: (
            -item[1],
            repr(item[0]),
        ),
    )[:count]


def _percentile(
    sorted_values: list[float],
    fraction: float,
) -> float | None:
    if not sorted_values:
        return None

    index = min(
        len(sorted_values) - 1,
        int(
            fraction
            * len(sorted_values)
        ),
    )

    return sorted_values[index]


def _summary(
    values: list[float],
) -> dict:
    count = len(values)

    if count == 0:
        return {
            "count": 0,
        }

    mean = sum(values) / count

    return {
        "count": count,
        "mean": mean,
        "sd": (
            math.sqrt(
                sum(
                    (value - mean) ** 2
                    for value in values
                )
                / (count - 1)
            )
            if count > 1
            else 0.0
        ),
        "standard_error": standard_error(
            mean=mean,
            sum_squares=sum(
                value * value
                for value in values
            ),
            count=count,
        ),
        "min": min(values),
        "max": max(values),
    }


def _jsonable(
    value,
):
    if isinstance(
        value,
        tuple,
    ):
        return [
            _jsonable(item)
            for item in value
        ]

    return value
