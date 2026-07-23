from solver.canonical_hand import canonicalize_hand
from solver.game_state import GameConfig
from solver.hand import Hand
from solver.single_draw_game import GamePhase
from solver.training_factory import (
    FixedDrawTrainingGameFactory,
    FixedHandsDrawTrainingGameFactory,
    FixedTrainingGameFactory,
    TrainingGameFactory,
)


def make_config(
    *,
    player_count: int = 2,
) -> GameConfig:
    return GameConfig(
        player_count=player_count,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )


def test_factory_creates_game() -> None:
    factory = TrainingGameFactory(
        config=make_config(),
        initial_seed=42,
    )

    game = factory()

    assert game.config.player_count == 2
    assert game.deck_seed == 42
    assert factory.games_created == 1


def test_factory_increments_seed() -> None:
    factory = TrainingGameFactory(
        config=make_config(),
        initial_seed=42,
    )

    first_game = factory()
    second_game = factory()
    third_game = factory()

    assert first_game.deck_seed == 42
    assert second_game.deck_seed == 43
    assert third_game.deck_seed == 44
    assert factory.games_created == 3


def test_different_seeds_produce_different_deals() -> None:
    factory = TrainingGameFactory(
        config=make_config(),
        initial_seed=42,
    )

    first_game = factory()
    second_game = factory()

    assert first_game.hands != second_game.hands


def test_same_initial_seed_is_reproducible() -> None:
    first_factory = TrainingGameFactory(
        config=make_config(),
        initial_seed=42,
    )

    second_factory = TrainingGameFactory(
        config=make_config(),
        initial_seed=42,
    )

    first_sequence = [
        first_factory().hands
        for _ in range(5)
    ]

    second_sequence = [
        second_factory().hands
        for _ in range(5)
    ]

    assert first_sequence == second_sequence


def test_factory_uses_fixed_button_by_default() -> None:
    factory = TrainingGameFactory(
        config=make_config(),
        button_seat=1,
        initial_seed=42,
    )

    games = [
        factory()
        for _ in range(3)
    ]

    assert all(
        game.button_seat == 1
        for game in games
    )


def test_factory_can_alternate_heads_up_button() -> None:
    factory = TrainingGameFactory(
        config=make_config(),
        button_seat=0,
        initial_seed=42,
        alternate_button=True,
    )

    games = [
        factory()
        for _ in range(4)
    ]

    assert [
        game.button_seat
        for game in games
    ] == [0, 1, 0, 1]


def test_factory_can_rotate_multiplayer_button() -> None:
    factory = TrainingGameFactory(
        config=make_config(
            player_count=3,
        ),
        button_seat=1,
        initial_seed=42,
        alternate_button=True,
    )

    games = [
        factory()
        for _ in range(5)
    ]

    assert [
        game.button_seat
        for game in games
    ] == [1, 2, 0, 1, 2]


def test_factory_does_not_reuse_game_objects() -> None:
    factory = TrainingGameFactory(
        config=make_config(),
        initial_seed=42,
    )

    first_game = factory()
    second_game = factory()

    assert first_game is not second_game
    assert first_game.deck is not second_game.deck
    assert first_game.betting_state is not (
        second_game.betting_state
    )


def test_fixed_factory_reuses_same_deal() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    factory = FixedTrainingGameFactory(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    first_game = factory()
    second_game = factory()

    assert first_game.hands == second_game.hands
    assert first_game.button_seat == second_game.button_seat
    assert first_game.acting_seat == second_game.acting_seat
    assert first_game.phase == second_game.phase
    assert factory.games_created == 2


def test_fixed_factory_does_not_alternate_button() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    factory = FixedTrainingGameFactory(
        config=config,
        button_seat=1,
        deck_seed=42,
    )

    first_game = factory()
    second_game = factory()

    assert first_game.button_seat == 1
    assert second_game.button_seat == 1


def test_different_fixed_seeds_create_different_deals() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    first_factory = FixedTrainingGameFactory(
        config=config,
        deck_seed=42,
    )

    second_factory = FixedTrainingGameFactory(
        config=config,
        deck_seed=43,
    )

    first_game = first_factory()
    second_game = second_factory()

    assert first_game.hands != second_game.hands


def test_fixed_draw_factory_reuses_same_draw_state() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    factory = FixedDrawTrainingGameFactory(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    first_game = factory()
    second_game = factory()

    assert first_game.phase == GamePhase.DRAW
    assert second_game.phase == GamePhase.DRAW
    assert first_game.hands == second_game.hands
    assert first_game.acting_seat == second_game.acting_seat
    assert factory.games_created == 2


def test_fixed_draw_factory_starts_in_draw_phase() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    factory = FixedDrawTrainingGameFactory(
        config=config,
        button_seat=0,
        deck_seed=42,
    )

    game = factory()

    assert game.phase == GamePhase.DRAW
    assert game.acting_seat is not None
    assert factory.games_created == 1


def test_fixed_hands_factory_preserves_starting_hands() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    first_hand = Hand.from_strings(
        "3c",
        "4s",
        "5c",
        "Td",
        "Kc",
    )

    second_hand = Hand.from_strings(
        "2h",
        "3d",
        "5d",
        "6h",
        "Qs",
    )

    factory = FixedHandsDrawTrainingGameFactory(
        config=config,
        fixed_hands=(
            first_hand,
            second_hand,
        ),
        initial_seed=42,
    )

    game = factory()

    assert game.phase == GamePhase.DRAW
    assert game.hands[0] == canonicalize_hand(
        first_hand
    )
    assert game.hands[1] == canonicalize_hand(
        second_hand
    )


def test_fixed_hands_factory_randomizes_remaining_deck() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    fixed_hands = (
        Hand.from_strings(
            "3c",
            "4s",
            "5c",
            "Td",
            "Kc",
        ),
        Hand.from_strings(
            "2h",
            "3d",
            "5d",
            "6h",
            "Qs",
        ),
    )

    factory = FixedHandsDrawTrainingGameFactory(
        config=config,
        fixed_hands=fixed_hands,
        initial_seed=42,
    )

    first_game = factory()
    second_game = factory()

    assert first_game.hands == second_game.hands
    assert first_game.deck.stock != second_game.deck.stock
    assert first_game.phase == GamePhase.DRAW
    assert second_game.phase == GamePhase.DRAW
    assert factory.games_created == 2


def test_fixed_cards_are_removed_from_remaining_deck() -> None:
    config = GameConfig(
        player_count=2,
        starting_stack=100.0,
        small_blind=1.0,
        big_blind=2.0,
    )

    fixed_hands = (
        Hand.from_strings(
            "3c",
            "4s",
            "5c",
            "Td",
            "Kc",
        ),
        Hand.from_strings(
            "2h",
            "3d",
            "5d",
            "6h",
            "Qs",
        ),
    )

    factory = FixedHandsDrawTrainingGameFactory(
        config=config,
        fixed_hands=fixed_hands,
        initial_seed=42,
    )

    game = factory()

    fixed_cards = {
        card
        for hand in fixed_hands
        for card in hand.cards
    }

    remaining_cards = set(game.deck.stock)

    assert fixed_cards.isdisjoint(
        remaining_cards
    )
    assert len(game.deck.stock) == 42