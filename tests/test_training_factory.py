from solver.game_state import GameConfig
from solver.training_factory import TrainingGameFactory


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