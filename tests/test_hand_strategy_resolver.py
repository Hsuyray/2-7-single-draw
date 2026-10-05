from solver.draw_hand_bucket import (
    DrawHandBucket,
)
from solver.hand import Hand
from solver.hand_abstraction import (
    ExactHandKey,
)
from solver.hand_strategy_resolver import (
    HandStrategyResolver,
)
from solver.postdraw_strength_bucket import (
    PostdrawStrengthBucket,
)
from solver.single_draw_game import (
    GamePhase,
)


def make_hand() -> Hand:
    return Hand.from_strings(
        "2c",
        "3d",
        "4h",
        "5s",
        "Kc",
    )


def test_exact_abstraction_returns_exact_key() -> None:
    resolver = HandStrategyResolver(
        abstraction="exact"
    )

    result = resolver.resolve(
        hand=make_hand(),
        phase=GamePhase.DRAW,
    )

    assert isinstance(
        result,
        ExactHandKey,
    )


def test_bucket_predraw_returns_draw_bucket() -> None:
    resolver = HandStrategyResolver(
        abstraction="bucket"
    )

    result = resolver.resolve(
        hand=make_hand(),
        phase=GamePhase.PREDRAW_BETTING,
    )

    assert isinstance(
        result,
        DrawHandBucket,
    )


def test_bucket_draw_phase_returns_draw_bucket() -> None:
    resolver = HandStrategyResolver(
        abstraction="bucket"
    )

    result = resolver.resolve(
        hand=make_hand(),
        phase=GamePhase.DRAW,
    )

    assert isinstance(
        result,
        DrawHandBucket,
    )


def test_bucket_postdraw_returns_postdraw_strength_bucket() -> None:
    resolver = HandStrategyResolver(
        abstraction="bucket"
    )

    result = resolver.resolve(
        hand=make_hand(),
        phase=GamePhase.POSTDRAW_BETTING,
    )

    assert isinstance(
        result,
        PostdrawStrengthBucket,
    )


def test_exact_key_does_not_depend_on_phase() -> None:
    resolver = HandStrategyResolver(
        abstraction="exact"
    )

    hand = make_hand()

    predraw = resolver.resolve(
        hand=hand,
        phase=GamePhase.PREDRAW_BETTING,
    )

    draw = resolver.resolve(
        hand=hand,
        phase=GamePhase.DRAW,
    )

    postdraw = resolver.resolve(
        hand=hand,
        phase=GamePhase.POSTDRAW_BETTING,
    )

    assert predraw == draw
    assert draw == postdraw