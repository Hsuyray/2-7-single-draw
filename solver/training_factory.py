import random
from dataclasses import dataclass

from solver.action_executor import apply_solver_action
from solver.cards import Card, RANKS, SUITS
from solver.canonical_hand import canonicalize_hand
from solver.draw_deck import DrawDeck
from solver.game_state import GameConfig
from solver.hand import Hand
from solver.legal_actions import (
    ActionType,
    BettingAction,
    legal_actions,
)
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)


@dataclass
class TrainingGameFactory:
    config: GameConfig
    button_seat: int = 0
    initial_seed: int = 0
    alternate_button: bool = False
    games_created: int = 0

    def __call__(self) -> SingleDrawGame:
        seed = (
            self.initial_seed
            + self.games_created
        )

        button_seat = self.button_seat

        if self.alternate_button:
            button_seat = (
                self.button_seat
                + self.games_created
            ) % self.config.player_count

        game = SingleDrawGame(
            config=self.config,
            button_seat=button_seat,
            shuffle_deck=True,
            deck_seed=seed,
        )

        self.games_created += 1

        return game


@dataclass
class FixedTrainingGameFactory:
    config: GameConfig
    button_seat: int = 0
    deck_seed: int = 0
    games_created: int = 0

    def __call__(self) -> SingleDrawGame:
        game = SingleDrawGame(
            config=self.config,
            button_seat=self.button_seat,
            shuffle_deck=True,
            deck_seed=self.deck_seed,
        )

        self.games_created += 1

        return game


@dataclass
class FixedDrawTrainingGameFactory:
    config: GameConfig
    button_seat: int = 0
    deck_seed: int = 0
    games_created: int = 0

    def __call__(self) -> SingleDrawGame:
        game = SingleDrawGame(
            config=self.config,
            button_seat=self.button_seat,
            shuffle_deck=True,
            deck_seed=self.deck_seed,
        )

        game = _advance_to_draw_phase(game)

        self.games_created += 1

        return game


@dataclass
class FixedHandsDrawTrainingGameFactory:
    config: GameConfig
    fixed_hands: tuple[Hand, Hand]
    button_seat: int = 0
    initial_seed: int = 0
    games_created: int = 0

    def __post_init__(self) -> None:
        if self.config.player_count != 2:
            raise ValueError(
                "FixedHandsDrawTrainingGameFactory "
                "currently supports heads-up only."
            )

        if len(self.fixed_hands) != 2:
            raise ValueError(
                "Exactly two fixed hands are required."
            )

        all_cards = [
            card
            for hand in self.fixed_hands
            for card in hand.cards
        ]

        if len(all_cards) != 10:
            raise ValueError(
                "Each fixed hand must contain "
                "five cards."
            )

        if len(set(all_cards)) != 10:
            raise ValueError(
                "Fixed hands cannot contain "
                "duplicate cards."
            )

    def __call__(self) -> SingleDrawGame:
        seed = (
            self.initial_seed
            + self.games_created
        )

        game = SingleDrawGame(
            config=self.config,
            button_seat=self.button_seat,
            shuffle_deck=False,
        )

        canonical_hands = tuple(
            canonicalize_hand(hand)
            for hand in self.fixed_hands
        )

        used_cards = {
            card
            for hand in canonical_hands
            for card in hand.cards
        }

        remaining_cards = [
            Card(rank, suit)
            for rank in RANKS
            for suit in SUITS
            if Card(rank, suit)
            not in used_cards
        ]

        game.hands = [
            canonical_hands[0],
            canonical_hands[1],
        ]

        game.deck = DrawDeck(
            cards=remaining_cards,
            shuffle=True,
            seed=seed,
        )

        game = _advance_to_draw_phase(game)

        self.games_created += 1

        return game


@dataclass
class FixedHeroDrawTrainingGameFactory:
    config: GameConfig
    hero_hand: Hand
    hero_seat: int = 0
    button_seat: int = 1
    initial_seed: int = 0
    games_created: int = 0

    def __post_init__(self) -> None:
        if self.config.player_count != 2:
            raise ValueError(
                "FixedHeroDrawTrainingGameFactory "
                "currently supports heads-up only."
            )

        if self.hero_seat not in {0, 1}:
            raise ValueError(
                "Hero seat must be 0 or 1."
            )

        if len(self.hero_hand.cards) != 5:
            raise ValueError(
                "Hero hand must contain "
                "exactly five cards."
            )

        if (
            len(set(self.hero_hand.cards))
            != 5
        ):
            raise ValueError(
                "Hero hand cannot contain "
                "duplicate cards."
            )

    def __call__(self) -> SingleDrawGame:
        seed = (
            self.initial_seed
            + self.games_created
        )

        random_generator = random.Random(seed)

        game = SingleDrawGame(
            config=self.config,
            button_seat=self.button_seat,
            shuffle_deck=False,
        )

        hero_hand = canonicalize_hand(
            self.hero_hand
        )

        remaining_cards = [
            Card(rank, suit)
            for rank in RANKS
            for suit in SUITS
            if Card(rank, suit)
            not in hero_hand.cards
        ]

        random_generator.shuffle(
            remaining_cards
        )

        opponent_cards = tuple(
            remaining_cards[:5]
        )

        deck_cards = (
            remaining_cards[5:]
        )

        opponent_hand = canonicalize_hand(
            Hand(cards=opponent_cards)
        )

        hands = [
            opponent_hand,
            opponent_hand,
        ]

        hands[self.hero_seat] = hero_hand
        hands[1 - self.hero_seat] = (
            opponent_hand
        )

        game.hands = hands

        game.deck = DrawDeck(
            cards=deck_cards,
            shuffle=False,
        )

        game = _advance_to_draw_phase(game)

        if game.acting_seat != self.hero_seat:
            raise RuntimeError(
                "Hero is not first to act "
                "during the draw phase. "
                "Adjust button_seat or hero_seat."
            )

        self.games_created += 1

        return game


def _advance_to_draw_phase(
    game: SingleDrawGame,
) -> SingleDrawGame:
    while (
        game.phase
        == GamePhase.PREDRAW_BETTING
    ):
        actions = legal_actions(
            game,
            max_draw=1,
            raise_sizes=(),
        )

        action = _find_call_or_check(
            actions
        )

        if action is None:
            raise RuntimeError(
                "Could not advance training "
                "game to the draw phase."
            )

        game = apply_solver_action(
            game,
            action,
        )

    if game.phase != GamePhase.DRAW:
        raise RuntimeError(
            "Training game did not reach "
            "the draw phase."
        )

    return game


def _find_call_or_check(
    actions: tuple | list,
) -> BettingAction | None:
    for preferred_type in (
        ActionType.CALL,
        ActionType.CHECK,
    ):
        for action in actions:
            if (
                isinstance(
                    action,
                    BettingAction,
                )
                and action.action_type
                == preferred_type
            ):
                return action

    return None