from dataclasses import dataclass

from solver.actions import (
    DiscardAction,
)
from solver.bet_sizing import (
    BetSize,
    BetSizingPolicy,
)
from solver.game_state import (
    ActionType,
)
from solver.legal_actions import (
    BettingAction,
    DrawActionMode,
    legal_actions,
)
from solver.single_draw_game import (
    SingleDrawGame,
)


@dataclass(frozen=True)
class PublicBettingAction:
    """
    UI-facing representation of one legal
    betting action.
    """

    action_type: ActionType
    label: str
    raise_to: float | None = None
    pot_fraction: float | None = None
    is_all_in: bool = False

    def __post_init__(self) -> None:
        if (
            self.action_type
            == ActionType.RAISE
        ):
            if self.raise_to is None:
                raise ValueError(
                    "Public raise action must "
                    "include raise_to."
                )

            return

        if self.raise_to is not None:
            raise ValueError(
                "Only raise actions may "
                "include raise_to."
            )

        if self.pot_fraction is not None:
            raise ValueError(
                "Only raise actions may "
                "include pot_fraction."
            )

        if self.is_all_in:
            raise ValueError(
                "Only raise actions may "
                "be marked all-in."
            )


@dataclass(frozen=True)
class PublicDrawAction:
    """
    Public representation of a draw action.

    Only the number of cards drawn is public.
    Exact discarded card indices remain
    private information.
    """

    draw_count: int

    def __post_init__(self) -> None:
        if not (
            0
            <= self.draw_count
            <= 5
        ):
            raise ValueError(
                "Public draw count must be "
                "between zero and five."
            )

    @property
    def label(self) -> str:
        if self.draw_count == 0:
            return "Stand Pat"

        return (
            f"Draw {self.draw_count}"
        )


PublicSolverAction = (
    PublicBettingAction
    | PublicDrawAction
)


@dataclass(frozen=True)
class PublicLegalActionSnapshot:
    """
    Public-facing legal actions available
    at the current decision node.
    """

    acting_seat: int

    actions: tuple[
        PublicSolverAction,
        ...,
    ]

    @property
    def action_count(self) -> int:
        return len(
            self.actions
        )

    @property
    def betting_actions(
        self,
    ) -> tuple[
        PublicBettingAction,
        ...,
    ]:
        return tuple(
            action
            for action in self.actions
            if isinstance(
                action,
                PublicBettingAction,
            )
        )

    @property
    def draw_actions(
        self,
    ) -> tuple[
        PublicDrawAction,
        ...,
    ]:
        return tuple(
            action
            for action in self.actions
            if isinstance(
                action,
                PublicDrawAction,
            )
        )


def public_legal_actions(
    game: SingleDrawGame,
    *,
    max_draw: int = 3,
    raise_sizes: (
        tuple[float, ...]
        | None
    ) = None,
    bet_sizing_policy: (
        BetSizingPolicy
        | None
    ) = None,
    draw_action_mode: (
        DrawActionMode
    ) = "full",
) -> PublicLegalActionSnapshot | None:
    """
    Return one UI-facing snapshot of the
    current legal actions.

    Private discard combinations are grouped
    by public draw count.
    """
    acting_seat = game.acting_seat

    if acting_seat is None:
        return None

    policy = (
        bet_sizing_policy
        if bet_sizing_policy is not None
        else BetSizingPolicy()
    )

    solver_actions = legal_actions(
        game,
        max_draw=max_draw,
        raise_sizes=raise_sizes,
        bet_sizing_policy=policy,
        draw_action_mode=(
            draw_action_mode
        ),
    )

    public_actions = (
        _to_public_actions(
            game,
            solver_actions=solver_actions,
            raise_sizes=raise_sizes,
            policy=policy,
        )
    )

    return PublicLegalActionSnapshot(
        acting_seat=acting_seat,
        actions=public_actions,
    )


def _to_public_actions(
    game: SingleDrawGame,
    *,
    solver_actions: tuple[
        BettingAction | DiscardAction,
        ...,
    ],
    raise_sizes: (
        tuple[float, ...]
        | None
    ),
    policy: BetSizingPolicy,
) -> tuple[
    PublicSolverAction,
    ...,
]:
    public_actions: list[
        PublicSolverAction
    ] = []

    draw_counts: set[
        int
    ] = set()

    for action in solver_actions:
        if isinstance(
            action,
            DiscardAction,
        ):
            draw_counts.add(
                len(
                    action.discard_indices
                )
            )
            continue

        public_actions.append(
            _to_public_betting_action(
                game,
                action=action,
                raise_sizes=raise_sizes,
                policy=policy,
            )
        )

    public_actions.extend(
        PublicDrawAction(
            draw_count=draw_count
        )
        for draw_count
        in sorted(draw_counts)
    )

    return tuple(
        public_actions
    )


def _to_public_betting_action(
    game: SingleDrawGame,
    *,
    action: BettingAction,
    raise_sizes: (
        tuple[float, ...]
        | None
    ),
    policy: BetSizingPolicy,
) -> PublicBettingAction:
    if (
        action.action_type
        != ActionType.RAISE
    ):
        return PublicBettingAction(
            action_type=(
                action.action_type
            ),
            label=_non_raise_label(
                action.action_type
            ),
        )

    if action.raise_to is None:
        raise RuntimeError(
            "Legal raise action is "
            "missing raise_to."
        )

    metadata = _bet_size_metadata(
        game,
        raise_sizes=raise_sizes,
        policy=policy,
    )

    bet_size = metadata.get(
        action.raise_to
    )

    if bet_size is not None:
        return PublicBettingAction(
            action_type=(
                ActionType.RAISE
            ),
            label=bet_size.label,
            raise_to=(
                bet_size.raise_to
            ),
            pot_fraction=(
                bet_size.pot_fraction
            ),
            is_all_in=(
                bet_size.is_all_in
            ),
        )

    return _explicit_raise_action(
        game,
        raise_to=action.raise_to,
    )


def _bet_size_metadata(
    game: SingleDrawGame,
    *,
    raise_sizes: (
        tuple[float, ...]
        | None
    ),
    policy: BetSizingPolicy,
) -> dict[
    float,
    BetSize,
]:
    """
    Return policy metadata only when the
    policy generated the raise sizes.
    """
    if raise_sizes is not None:
        return {}

    state = game.betting_state
    acting_seat = state.acting_seat

    if acting_seat is None:
        return {}

    player = state.players[
        acting_seat
    ]

    sizes = policy.bet_size_candidates(
        pot=game.pot,
        committed_this_round=(
            player.committed_this_round
        ),
        stack=player.stack,
        amount_to_call=(
            state.amount_to_call(
                acting_seat
            )
        ),
        minimum_raise_to=(
            state.minimum_raise_to()
        ),
        maximum_raise_to=(
            state.maximum_raise_to(
                acting_seat
            )
        ),
    )

    return {
        size.raise_to: size
        for size in sizes
    }


def _explicit_raise_action(
    game: SingleDrawGame,
    *,
    raise_to: float,
) -> PublicBettingAction:
    state = game.betting_state
    acting_seat = state.acting_seat

    if acting_seat is None:
        raise RuntimeError(
            "Cannot format raise without "
            "an acting player."
        )

    maximum_raise_to = (
        state.maximum_raise_to(
            acting_seat
        )
    )

    is_all_in = (
        raise_to
        == maximum_raise_to
    )

    label = (
        "All-in"
        if is_all_in
        else f"Raise to {raise_to:g}"
    )

    return PublicBettingAction(
        action_type=ActionType.RAISE,
        label=label,
        raise_to=raise_to,
        pot_fraction=None,
        is_all_in=is_all_in,
    )


def _non_raise_label(
    action_type: ActionType,
) -> str:
    labels = {
        ActionType.FOLD: "Fold",
        ActionType.CHECK: "Check",
        ActionType.CALL: "Call",
    }

    try:
        return labels[
            action_type
        ]
    except KeyError as error:
        raise ValueError(
            "Unsupported non-raise "
            f"action type: {action_type}"
        ) from error