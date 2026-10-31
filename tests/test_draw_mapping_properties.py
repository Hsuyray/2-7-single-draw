"""
B2: property tests for the draw-action mapping between physical
Hand.cards indices and bucket-canonical indices, and for the draw
count that reaches the postdraw public key.
"""

import random
from collections import Counter

import pytest

from scripts.inspect_draw_decisions import (
    action_flags,
    hand_category,
)
from solver.actions import (
    DiscardAction,
)
from solver.bucket_hand_codec import (
    actual_discard_action_for_bucket_hand,
    bucket_discard_action_for_hand,
)
from solver.cards import (
    Card,
)
from solver.cfr_trainer import (
    CFRTrainer,
)
from solver.discard_actions import (
    generate_discard_actions,
)
from solver.draw_hand_bucket import (
    draw_hand_bucket,
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
from solver.legal_actions import (
    BettingAction,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


RANKS = "23456789TJQKA"
SUITS = "shdc"

ALL_ACTIONS = generate_discard_actions(
    hand_size=5,
    max_draw=5,
)


def random_hands(
    count: int,
    seed: int,
) -> list[Hand]:
    rng = random.Random(seed)
    deck = [
        rank + suit
        for rank in RANKS
        for suit in SUITS
    ]

    return [
        Hand.from_strings(*rng.sample(deck, 5))
        for _ in range(count)
    ]


def relabel(
    hand: Hand,
    rng: random.Random,
) -> tuple[Hand, dict[str, str]]:
    """Same hand with permuted suits and card order."""
    shuffled_suits = list(SUITS)
    rng.shuffle(shuffled_suits)
    suit_map = dict(zip(SUITS, shuffled_suits))

    cards = [
        f"{card.rank}{suit_map[card.suit]}"
        for card in hand.cards
    ]
    rng.shuffle(cards)

    return Hand.from_strings(*cards), suit_map


def kept_signature(
    hand: Hand,
    physical: DiscardAction,
) -> tuple:
    kept = [
        card
        for index, card in enumerate(hand.cards)
        if index not in physical.discard_indices
    ]

    suit_counts = Counter(card.suit for card in hand.cards)
    dominant, dominant_count = max(
        suit_counts.items(),
        key=lambda item: (item[1], item[0]),
    )

    flush_cards = (
        sum(1 for card in kept if card.suit == dominant)
        if dominant_count >= 4
        else 0
    )

    return (
        tuple(sorted(card.rank for card in kept)),
        flush_cards,
    )


def test_mapping_is_a_bijection_per_hand() -> None:
    for hand in random_hands(400, seed=1):
        bucket_actions = set()

        for action in ALL_ACTIONS:
            bucket_action = bucket_discard_action_for_hand(
                hand=hand,
                action=action,
            )

            assert bucket_action.draw_count == action.draw_count

            assert actual_discard_action_for_bucket_hand(
                hand=hand,
                action=bucket_action,
            ) == action

            bucket_actions.add(bucket_action)

        assert len(bucket_actions) == len(ALL_ACTIONS)


def test_same_bucket_action_keeps_equivalent_cards() -> None:
    """
    Relabelling suits and shuffling card order gives a
    strategically identical hand. It must land in the same
    bucket, and every bucket action must keep the same ranks
    (and the same number of flush-suit cards) in both.
    """
    rng = random.Random(7)

    for hand in random_hands(400, seed=2):
        other, _ = relabel(hand, rng)

        assert draw_hand_bucket(other) == draw_hand_bucket(hand)

        for bucket_action in ALL_ACTIONS:
            assert kept_signature(
                hand,
                actual_discard_action_for_bucket_hand(
                    hand=hand,
                    action=bucket_action,
                ),
            ) == kept_signature(
                other,
                actual_discard_action_for_bucket_hand(
                    hand=other,
                    action=bucket_action,
                ),
            )


def test_canonical_positions_are_sorted_by_rank() -> None:
    for hand in random_hands(400, seed=3):
        bucket = draw_hand_bucket(hand)

        assert list(bucket.rank_classes) == sorted(
            bucket.rank_classes
        )


def bucket_of(*cards: str):
    return draw_hand_bucket(Hand.from_strings(*cards))


def discard(*positions: int) -> DiscardAction:
    return DiscardAction(tuple(sorted(positions)))


def test_mistake_classification_examples() -> None:
    made_seven = bucket_of("7s", "5h", "4d", "3c", "2s")
    assert hand_category(made_seven) == "made_7_or_better"
    assert not any(
        action_flags(made_seven, discard()).values()
    )
    assert action_flags(made_seven, discard(4))[
        "break_made_low"
    ]

    # 2-2-5-7-8: canonical positions 0,1 are the deuces.
    pair = bucket_of("2s", "2h", "5d", "7c", "8s")
    assert hand_category(pair) == "one_pair"
    assert action_flags(pair, discard(4))["keep_pair"]
    assert not action_flags(pair, discard(0))["keep_pair"]
    assert action_flags(pair, discard())["snow"]

    # K-8-5-3-2: throwing the 2 and keeping the K is dominated.
    # Same bucket, different right answer: the bucket
    # cannot see straight-draw structure.
    assert bucket_of("3s", "4h", "5d", "6c", "8s") == bucket_of(
        "2s", "4h", "5d", "7c", "8s"
    )

    high = bucket_of("Ks", "8h", "5d", "3c", "2s")
    assert action_flags(high, discard(0))["keep_high"]
    assert not action_flags(high, discard(4))["keep_high"]


def play_to_draw(seed: int) -> tuple[SingleDrawGame, CFRTrainer]:
    trainer = CFRTrainer(
        max_draw=5,
        raise_sizes=(),
        abstraction="bucket",
        traversal_mode="external_sampling",
        draw_action_mode="full",
        random_seed=0,
    )

    game = SingleDrawGame(
        config=GameConfig(
            player_count=2,
            starting_stack=20.0,
            small_blind=1.0,
            big_blind=2.0,
            big_blind_ante=1.5,
        ),
        button_seat=0,
        deck_seed=seed,
    )

    while game.phase == GamePhase.PREDRAW_BETTING:
        actions = trainer._legal_actions(game)

        action = next(
            candidate
            for candidate in actions
            if candidate
            in (
                BettingAction(ActionType.CALL),
                BettingAction(ActionType.CHECK),
            )
        )

        game = trainer._apply_node_action(
            game=game,
            action=action,
        )

    return game, trainer


@pytest.mark.parametrize("draw_count", [0, 1, 3, 5])
def test_draw_count_reaches_the_public_key(draw_count) -> None:
    game, trainer = play_to_draw(seed=11 + draw_count)

    assert game.phase == GamePhase.DRAW

    while game.phase == GamePhase.DRAW:
        seat = game.acting_seat

        action = next(
            candidate
            for candidate in trainer._legal_actions(game)
            if candidate.draw_count == draw_count
        )

        game = trainer._apply_node_action(
            game=game,
            action=action,
        )

        assert game.draw_results[seat].action.draw_count == (
            draw_count
        )

    state = InformationState.from_game(
        game,
        observer_seat=game.acting_seat,
        abstraction="bucket",
    )

    assert state.phase == "postdraw_betting"

    draw_actions = [
        action
        for action in state.public_node.action_history
        if action.phase == "draw"
    ]

    assert [action.draw_count for action in draw_actions] == [
        draw_count,
        draw_count,
    ]

    assert all(
        player.draw_count == draw_count
        for player in state.public_node.players
    )


def test_unavoidable_keep_pair_is_not_a_mistake() -> None:
    from scripts.inspect_draw_decisions import strategy_masses

    # max_draw=1: two pair can only throw one card,
    # so every action keeps a pair.
    two_pair = bucket_of("2s", "2h", "5d", "5c", "Ks")
    strategy = {
        discard(): 0.5,
        discard(4): 0.5,
    }

    masses = strategy_masses(two_pair, strategy)
    assert masses["keep_pair"] == 0.0
    assert masses["any_mistake"] == 0.0

    # With a five-card action set it is avoidable.
    masses = strategy_masses(
        two_pair,
        {
            discard(4): 0.5,
            discard(1, 3, 4): 0.5,
        },
    )
    assert masses["keep_pair"] == pytest.approx(0.5)
