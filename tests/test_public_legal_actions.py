from solver.bet_sizing import (
    BetSizingPolicy,
)
from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.public_legal_actions import (
    PublicBettingAction,
    PublicDrawAction,
    PublicLegalActionSnapshot,
    public_legal_actions,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


def _make_game(
    *,
    starting_stack: float = 20.0,
) -> SingleDrawGame:
    config = GameConfig(
        player_count=2,
        starting_stack=starting_stack,
        small_blind=1.0,
        big_blind=2.0,
        big_blind_ante=0.0,
    )

    return SingleDrawGame(
        config=config,
        button_seat=0,
        deck_seed=42,
    )


def _advance_to_draw(
    game: SingleDrawGame,
) -> None:
    while (
        game.phase
        == GamePhase.PREDRAW_BETTING
    ):
        state = game.betting_state
        acting_seat = state.acting_seat

        if acting_seat is None:
            raise RuntimeError(
                "Expected a pre-draw actor."
            )

        amount_to_call = (
            state.amount_to_call(
                acting_seat
            )
        )

        if amount_to_call > 0:
            game.apply_betting_action(
                ActionType.CALL
            )
        else:
            game.apply_betting_action(
                ActionType.CHECK
            )

    if game.phase != GamePhase.DRAW:
        raise RuntimeError(
            "Expected draw phase."
        )


def test_snapshot_records_acting_seat() -> None:
    game = _make_game()

    snapshot = public_legal_actions(
        game,
        raise_sizes=(),
    )

    assert snapshot is not None

    assert (
        snapshot.acting_seat
        == game.acting_seat
    )


def test_snapshot_action_count_matches_actions() -> None:
    game = _make_game()

    snapshot = public_legal_actions(
        game,
        raise_sizes=(),
    )

    assert snapshot is not None

    assert (
        snapshot.action_count
        == len(snapshot.actions)
    )


def test_betting_phase_returns_public_betting_actions() -> None:
    game = _make_game()

    snapshot = public_legal_actions(
        game,
        raise_sizes=(),
    )

    assert snapshot is not None

    assert snapshot.actions

    assert all(
        isinstance(
            action,
            PublicBettingAction,
        )
        for action in snapshot.actions
    )


def test_empty_raise_sizes_disable_raises() -> None:
    game = _make_game()

    snapshot = public_legal_actions(
        game,
        raise_sizes=(),
    )

    assert snapshot is not None

    assert all(
        action.action_type
        != ActionType.RAISE
        for action
        in snapshot.betting_actions
    )


def test_policy_generates_fraction_labels() -> None:
    game = _make_game(
        starting_stack=20.0,
    )

    policy = BetSizingPolicy(
        pot_fractions=(
            0.50,
            1.00,
        ),
        include_all_in=True,
    )

    snapshot = public_legal_actions(
        game,
        raise_sizes=None,
        bet_sizing_policy=policy,
    )

    assert snapshot is not None

    raise_actions = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    labels = {
        action.label
        for action in raise_actions
    }

    assert (
        "50% Pot" in labels
        or "100% Pot" in labels
    )


def test_policy_generates_all_in_label() -> None:
    game = _make_game()

    snapshot = public_legal_actions(
        game,
        raise_sizes=None,
    )

    assert snapshot is not None

    all_in_actions = [
        action
        for action
        in snapshot.betting_actions
        if action.is_all_in
    ]

    assert len(all_in_actions) == 1

    assert (
        all_in_actions[0].label
        == "All-in"
    )


def test_policy_raise_has_execution_value() -> None:
    game = _make_game()

    snapshot = public_legal_actions(
        game,
        raise_sizes=None,
    )

    assert snapshot is not None

    raise_actions = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    assert raise_actions

    assert all(
        action.raise_to is not None
        for action in raise_actions
    )


def test_explicit_raise_uses_generic_label() -> None:
    game = _make_game()

    snapshot = public_legal_actions(
        game,
        raise_sizes=(
            6.0,
        ),
    )

    assert snapshot is not None

    raises = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    assert raises == [
        PublicBettingAction(
            action_type=(
                ActionType.RAISE
            ),
            label="Raise to 6",
            raise_to=6.0,
            pot_fraction=None,
            is_all_in=False,
        )
    ]


def test_explicit_all_in_uses_all_in_label() -> None:
    game = _make_game()

    acting_seat = (
        game.betting_state.acting_seat
    )

    if acting_seat is None:
        raise RuntimeError(
            "Expected acting player."
        )

    maximum_raise_to = (
        game.betting_state
        .maximum_raise_to(
            acting_seat
        )
    )

    snapshot = public_legal_actions(
        game,
        raise_sizes=(
            maximum_raise_to,
        ),
    )

    assert snapshot is not None

    raises = [
        action
        for action
        in snapshot.betting_actions
        if (
            action.action_type
            == ActionType.RAISE
        )
    ]

    assert raises == [
        PublicBettingAction(
            action_type=(
                ActionType.RAISE
            ),
            label="All-in",
            raise_to=(
                maximum_raise_to
            ),
            pot_fraction=None,
            is_all_in=True,
        )
    ]


def test_draw_phase_returns_public_draw_actions() -> None:
    game = _make_game()

    _advance_to_draw(
        game
    )

    snapshot = public_legal_actions(
        game,
        max_draw=1,
        draw_action_mode="candidate",
    )

    assert snapshot is not None
    assert snapshot.draw_actions

    assert all(
        isinstance(
            action,
            PublicDrawAction,
        )
        for action
        in snapshot.draw_actions
    )


def test_draw_phase_has_no_betting_actions() -> None:
    game = _make_game()

    _advance_to_draw(
        game
    )

    snapshot = public_legal_actions(
        game,
        max_draw=1,
        draw_action_mode="candidate",
    )

    assert snapshot is not None

    assert (
        snapshot.betting_actions
        == ()
    )


def test_snapshot_properties_separate_action_types() -> None:
    betting_action = PublicBettingAction(
        action_type=ActionType.CHECK,
        label="Check",
    )

    snapshot = PublicLegalActionSnapshot(
        acting_seat=0,
        actions=(
            betting_action,
        ),
    )

    assert (
        snapshot.betting_actions
        == (
            betting_action,
        )
    )

    assert snapshot.draw_actions == ()


def test_public_raise_requires_raise_to() -> None:
    try:
        PublicBettingAction(
            action_type=ActionType.RAISE,
            label="Raise",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_non_raise_rejects_raise_metadata() -> None:
    try:
        PublicBettingAction(
            action_type=ActionType.CALL,
            label="Call",
            raise_to=2.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_private_discard_patterns_collapse_by_draw_count() -> None:
    game = _make_game()

    _advance_to_draw(
        game
    )

    snapshot = public_legal_actions(
        game,
        max_draw=1,
        draw_action_mode="full",
    )

    assert snapshot is not None

    assert snapshot.draw_actions == (
        PublicDrawAction(
            draw_count=0
        ),
        PublicDrawAction(
            draw_count=1
        ),
    )


def test_public_draw_action_exposes_label() -> None:
    assert (
        PublicDrawAction(
            draw_count=0
        ).label
        == "Stand Pat"
    )

    assert (
        PublicDrawAction(
            draw_count=1
        ).label
        == "Draw 1"
    )

    assert (
        PublicDrawAction(
            draw_count=3
        ).label
        == "Draw 3"
    )


def test_public_draw_action_does_not_expose_indices() -> None:
    action = PublicDrawAction(
        draw_count=2
    )

    assert not hasattr(
        action,
        "discard_indices",
    )


def test_public_draw_count_cannot_be_negative() -> None:
    try:
        PublicDrawAction(
            draw_count=-1
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_public_draw_count_cannot_exceed_five() -> None:
    try:
        PublicDrawAction(
            draw_count=6
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_snapshot_separates_public_draw_actions() -> None:
    draw_action = PublicDrawAction(
        draw_count=2
    )

    snapshot = PublicLegalActionSnapshot(
        acting_seat=0,
        actions=(
            draw_action,
        ),
    )

    assert snapshot.betting_actions == ()

    assert snapshot.draw_actions == (
        draw_action,
    )