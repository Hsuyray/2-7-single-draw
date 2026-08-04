import pytest

from solver.actions import (
    DiscardAction,
)
from solver.cards import (
    Card,
)
from solver.game_state import (
    ActionType,
    GameConfig,
)
from solver.hand import (
    Hand,
)
from solver.information_state import (
    InformationState,
)
from solver.public_node_navigator import (
    PublicNodeNavigator,
)
from solver.range_tracker import (
    RangeTracker,
)
from solver.single_draw_game import (
    SingleDrawGame,
)
from solver.strategy_browser import (
    StrategyBrowser,
)
from solver.strategy_index import (
    StrategyIndex,
)


def make_game() -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=100.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=42,
    )


def replace_hand_and_rebuild_deck(
    *,
    game: SingleDrawGame,
    seat: int,
    new_hand: Hand,
) -> None:
    """
    Replace one player's hand and rebuild all
    remaining card locations consistently.

    If the custom hand contains cards that were
    originally held by another player, that
    other player receives replacement cards
    from the remaining physical deck.
    """
    all_cards: set[Card] = set(
        game.deck.stock
    )

    all_cards.update(
        game.deck.muck
    )

    for hand in game.hands:
        if hand is None:
            continue

        all_cards.update(
            hand.cards
        )

    if len(all_cards) != 52:
        raise RuntimeError(
            "The game does not currently "
            "contain exactly 52 unique cards."
        )

    new_hand_cards = set(
        new_hand.cards
    )

    if not new_hand_cards.issubset(
        all_cards
    ):
        raise RuntimeError(
            "Custom hand contains cards that "
            "are not present in the game."
        )

    remaining_cards = [
        card
        for card in all_cards
        if card not in new_hand_cards
    ]

    rebuilt_hands: list[
        Hand | None
    ] = [
        None
        for _ in game.hands
    ]

    rebuilt_hands[
        seat
    ] = new_hand

    used_cards = set(
        new_hand.cards
    )

    for other_seat, old_hand in enumerate(
        game.hands
    ):
        if other_seat == seat:
            continue

        if old_hand is None:
            continue

        preserved_cards = [
            card
            for card in old_hand.cards
            if card not in used_cards
        ]

        needed = (
            5
            - len(preserved_cards)
        )

        replacement_cards: list[
            Card
        ] = []

        for card in remaining_cards:
            if card in used_cards:
                continue

            if card in preserved_cards:
                continue

            replacement_cards.append(
                card
            )

            if (
                len(replacement_cards)
                == needed
            ):
                break

        if (
            len(replacement_cards)
            != needed
        ):
            raise RuntimeError(
                "Unable to rebuild another "
                "player's hand."
            )

        rebuilt_cards = tuple(
            preserved_cards
            + replacement_cards
        )

        rebuilt_hand = Hand(
            rebuilt_cards
        )

        rebuilt_hands[
            other_seat
        ] = rebuilt_hand

        used_cards.update(
            rebuilt_hand.cards
        )

    game.hands = rebuilt_hands

    game.deck.stock = [
        card
        for card in all_cards
        if card not in used_cards
    ]

    game.deck.muck = []

    assert_card_locations_are_valid(
        game
    )


def assert_card_locations_are_valid(
    game: SingleDrawGame,
) -> None:
    """
    Verify every physical card exists in only
    one location:

    - one player hand
    - stock
    - muck
    """
    located_cards: list[
        Card
    ] = []

    for hand in game.hands:
        if hand is None:
            continue

        located_cards.extend(
            hand.cards
        )

    located_cards.extend(
        game.deck.stock
    )

    located_cards.extend(
        game.deck.muck
    )

    assert len(
        located_cards
    ) == 52

    assert len(
        set(located_cards)
    ) == 52


def make_draw_browser() -> tuple[
    StrategyBrowser,
    InformationState,
]:
    game = make_game()

    game.apply_betting_action(
        ActionType.CALL
    )

    game.apply_betting_action(
        ActionType.CHECK
    )

    acting_seat = game.acting_seat

    assert acting_seat is not None

    custom_hand = Hand.from_strings(
        "2s",
        "4s",
        "6s",
        "7d",
        "7s",
    )

    replace_hand_and_rebuild_deck(
        game=game,
        seat=acting_seat,
        new_hand=custom_hand,
    )

    state = InformationState.from_game(
        game,
        observer_seat=acting_seat,
        abstraction="exact",
    )

    index = StrategyIndex.from_strategies(
        {
            state: {
                DiscardAction(
                    ()
                ): 0.0,
                DiscardAction(
                    (3,)
                ): 1.0,
            },
        }
    )

    tracker = RangeTracker()

    tracker.weights[
        acting_seat
    ] = {
        state.own_hand_key: 1.0,
    }

    browser = StrategyBrowser(
        navigator=(
            PublicNodeNavigator.from_game(
                game
            )
        ),
        strategy_index=index,
        range_tracker=tracker,
        max_draw=1,
        draw_action_mode="full",
        raise_sizes=(),
    )

    return (
        browser,
        state,
    )


def test_replaced_hand_is_removed_from_deck() -> None:
    (
        browser,
        _,
    ) = make_draw_browser()

    acting_seat = browser.acting_seat

    assert acting_seat is not None

    hand = browser.game.hands[
        acting_seat
    ]

    assert hand is not None

    for card in hand.cards:
        assert (
            card
            not in browser.game.deck.stock
        )

        assert (
            card
            not in browser.game.deck.muck
        )

    assert_card_locations_are_valid(
        browser.game
    )


def test_browser_maps_canonical_discard_index_to_actual_card() -> None:
    (
        browser,
        _,
    ) = make_draw_browser()

    acting_seat = browser.acting_seat

    assert acting_seat is not None

    hand_before = browser.game.hands[
        acting_seat
    ]

    assert hand_before is not None

    assert str(
        hand_before.cards[3]
    ) == "7d"

    assert str(
        hand_before.cards[4]
    ) == "7s"

    legal = (
        browser.current_legal_actions()
    )

    assert legal is not None

    draw_one = next(
        action
        for action
        in legal.draw_actions
        if action.draw_count == 1
    )

    browser.apply_public_action(
        draw_one,
        discard_indices=(
            3,
        ),
    )

    result = (
        browser.game.draw_results[
            acting_seat
        ]
    )

    assert result.action == (
        DiscardAction(
            (4,)
        )
    )

    assert tuple(
        str(card)
        for card
        in result.discarded_cards
    ) == (
        "7s",
    )


def test_browser_does_not_discard_wrong_pair_card() -> None:
    (
        browser,
        _,
    ) = make_draw_browser()

    acting_seat = browser.acting_seat

    assert acting_seat is not None

    legal = (
        browser.current_legal_actions()
    )

    assert legal is not None

    draw_one = next(
        action
        for action
        in legal.draw_actions
        if action.draw_count == 1
    )

    browser.apply_public_action(
        draw_one,
        discard_indices=(
            3,
        ),
    )

    result = (
        browser.game.draw_results[
            acting_seat
        ]
    )

    discarded = {
        str(card)
        for card
        in result.discarded_cards
    }

    assert "7s" in discarded
    assert "7d" not in discarded


def test_browser_keeps_range_normalized_after_mapped_draw() -> None:
    (
        browser,
        _,
    ) = make_draw_browser()

    acting_seat = browser.acting_seat

    assert acting_seat is not None

    legal = (
        browser.current_legal_actions()
    )

    assert legal is not None

    draw_one = next(
        action
        for action
        in legal.draw_actions
        if action.draw_count == 1
    )

    browser.apply_public_action(
        draw_one,
        discard_indices=(
            3,
        ),
    )

    assert (
        browser.range_tracker
        is not None
    )

    post_draw_range = (
        browser.range_tracker
        .range_for_seat(
            acting_seat
        )
    )

    assert post_draw_range

    assert (
        sum(post_draw_range.values())
        == pytest.approx(1.0)
    )


def test_browser_rejects_invalid_canonical_discard_index() -> None:
    (
        browser,
        _,
    ) = make_draw_browser()

    legal = (
        browser.current_legal_actions()
    )

    assert legal is not None

    draw_one = next(
        action
        for action
        in legal.draw_actions
        if action.draw_count == 1
    )

    with pytest.raises(
        ValueError,
        match=(
            "Discard index is outside "
            "the hand"
        ),
    ):
        browser.apply_public_action(
            draw_one,
            discard_indices=(
                99,
            ),
        )