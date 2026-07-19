from dataclasses import dataclass, field
from enum import Enum

from solver.cards import Card
from solver.draw_deck import DrawDeck
from solver.draw import DrawResult, draw_cards
from solver.game_state import ActionType, GameConfig, GameState
from solver.hand import Hand
from solver.pots import Pot, build_pots


class GamePhase(str, Enum):
    PREDRAW_BETTING = "predraw_betting"
    DRAW = "draw"
    POSTDRAW_BETTING = "postdraw_betting"
    COMPLETE = "complete"

@dataclass(frozen=True)
class PotAward:
    pot: Pot
    winner_seats: tuple[int, ...]
    amount_per_winner: float

@dataclass
class SingleDrawGame:
    config: GameConfig
    button_seat: int = 0
    shuffle_deck: bool = True
    deck: DrawDeck = field(init=False)
    betting_state: GameState = field(init=False)
    hands: list[Hand | None] = field(init=False)
    phase: GamePhase = field(init=False)
    draw_order: list[int] = field(
        init=False,
        default_factory=list,
    )
    draw_index: int = field(
        init=False,
        default=0,
    )
    draw_results: dict[int, DrawResult] = field(
        init=False,
        default_factory=dict,
    )
    winner_seats: tuple[int, ...] = field(
        init=False,
        default=(),
    )
    payouts: dict[int, float] = field(
        init=False,
        default_factory=dict,
    )
    pot_awards: list[PotAward] = field(
        init=False,
        default_factory=list,
    )
    pot_awarded: bool = field(
        init=False,
        default=False,
    )

    def __post_init__(self) -> None:
        self.deck = DrawDeck(
            shuffle=self.shuffle_deck,
        )

        self.betting_state = GameState(
            config=self.config,
            button_seat=self.button_seat,
        )

        self.hands = [
            None
            for _ in range(self.config.player_count)
        ]

        self._deal_starting_hands()
        self.phase = GamePhase.PREDRAW_BETTING

    @property
    def acting_seat(self) -> int | None:
        if self.phase == GamePhase.DRAW:
            return self.draw_acting_seat

        return self.betting_state.acting_seat

    @property
    def draw_acting_seat(self) -> int | None:
        if self.phase != GamePhase.DRAW:
            return None

        if self.draw_index >= len(self.draw_order):
            return None

        return self.draw_order[self.draw_index]

    @property
    def pot(self) -> float:
        return self.betting_state.pot

    def _next_seat(self, seat: int) -> int:
        return (seat + 1) % self.config.player_count

    def _deal_starting_hands(self) -> None:
        dealt_cards: list[list[Card]] = [
            []
            for _ in range(self.config.player_count)
        ]

        first_dealt_seat = self._next_seat(
            self.button_seat
        )

        for _ in range(5):
            seat = first_dealt_seat

            for _ in range(self.config.player_count):
                dealt_cards[seat].extend(
                    self.deck.draw(1)
                )
                seat = self._next_seat(seat)

        for seat, cards in enumerate(dealt_cards):
            self.hands[seat] = Hand(tuple(cards))

    def apply_betting_action(
        self,
        action: ActionType,
        *,
        raise_to: float | None = None,
    ) -> None:
        if self.phase not in {
            GamePhase.PREDRAW_BETTING,
            GamePhase.POSTDRAW_BETTING,
        }:
            raise RuntimeError(
                "Betting actions are not allowed "
                f"during the {self.phase.value} phase."
            )

        self.betting_state.apply_action(
            action,
            raise_to=raise_to,
        )

        if self.betting_state.hand_complete:
            winner = self.betting_state.winner_seat

            if winner is None:
                raise RuntimeError(
                    "Completed hand has no winner."
                )

            self.winner_seats = (winner,)
            self.phase = GamePhase.COMPLETE
            self._award_pots()
            return

        if not self.betting_state.betting_round_complete:
            return

        if self.phase == GamePhase.PREDRAW_BETTING:
            self._start_draw_phase()
            return

        self._resolve_showdown()

    def _start_draw_phase(self) -> None:
        self.phase = GamePhase.DRAW
        self.draw_order = []
        self.draw_index = 0

        seat = self._next_seat(self.button_seat)

        for _ in range(self.config.player_count):
            player = self.betting_state.players[seat]

            if not player.has_folded:
                self.draw_order.append(seat)

            seat = self._next_seat(seat)

        if not self.draw_order:
            raise RuntimeError(
                "No players remain for the draw phase."
            )

    def submit_draw(
        self,
        seat: int,
        discard_indices: list[int],
    ) -> DrawResult:
        if self.phase != GamePhase.DRAW:
            raise RuntimeError(
                "Cards can only be drawn during "
                "the draw phase."
            )

        if seat != self.draw_acting_seat:
            raise ValueError(
                f"It is not seat {seat}'s turn to draw."
            )

        hand = self.hands[seat]

        if hand is None:
            raise RuntimeError(
                f"Seat {seat} does not have a hand."
            )

        result = draw_cards(
            hand=hand,
            deck=self.deck,
            discard_indices=discard_indices,
        )

        self.hands[seat] = result.final_hand
        self.draw_results[seat] = result
        self.draw_index += 1

        if self.draw_index >= len(self.draw_order):
            self._start_postdraw_betting()

        return result

    def _start_postdraw_betting(self) -> None:
        eligible_seats = [
            player.seat
            for player in self.betting_state.players
            if (
                not player.has_folded
                and not player.is_all_in
            )
        ]

        if len(eligible_seats) <= 1:
            self._resolve_showdown()
            return

        first_acting_seat = self._find_first_postdraw_actor()

        self.betting_state.start_new_betting_round(
            first_acting_seat=first_acting_seat,
        )

        self.phase = GamePhase.POSTDRAW_BETTING

    def _find_first_postdraw_actor(self) -> int:
        seat = self._next_seat(self.button_seat)

        for _ in range(self.config.player_count):
            player = self.betting_state.players[seat]

            if (
                not player.has_folded
                and not player.is_all_in
            ):
                return seat

            seat = self._next_seat(seat)

        raise RuntimeError(
            "No eligible post-draw actor exists."
        )

    def _resolve_showdown(self) -> None:
        remaining_seats = [
            player.seat
            for player in self.betting_state.players
            if not player.has_folded
        ]

        if not remaining_seats:
            raise RuntimeError(
                "Cannot resolve showdown without players."
            )

        for seat in remaining_seats:
            if self.hands[seat] is None:
                raise RuntimeError(
                    f"Seat {seat} does not have a hand."
                )

        self.phase = GamePhase.COMPLETE
        self.betting_state.hand_complete = True
        self.betting_state.betting_round_complete = True
        self.betting_state.acting_seat = None

        self._award_pots()

    def _award_pots(self) -> None:
        if self.pot_awarded:
            raise RuntimeError(
                "The pot has already been awarded."
            )

        commitments = [
            (
                player.committed_total
                - player.dead_money_committed
            )
            for player in self.betting_state.players
        ]

        total_dead_money = sum(
            player.dead_money_committed
            for player in self.betting_state.players
        )

        folded_seats = {
            player.seat
            for player in self.betting_state.players
            if player.has_folded
        }

        pots = build_pots(
            commitments=commitments,
            folded_seats=folded_seats,
        )
        
        if total_dead_money > 0:
            if not pots:
                eligible_seats = tuple(
                    player.seat
                    for player in self.betting_state.players
                    if not player.has_folded
                )

                pots = [
                    Pot(
                        amount=total_dead_money,
                        eligible_seats=eligible_seats,
                    )
                ]
            else:
                main_pot = pots[0]

                pots[0] = Pot(
                    amount=(
                        main_pot.amount
                        + total_dead_money
                    ),
                    eligible_seats=main_pot.eligible_seats,
                )
        calculated_total = sum(
            pot.amount
            for pot in pots
        )

        if abs(calculated_total - self.betting_state.pot) > 1e-9:
            raise RuntimeError(
                "Pot total does not match player commitments."
            )

        self.payouts = {}
        self.pot_awards = []

        all_winning_seats: set[int] = set()

        for pot in pots:
            winners = self._find_pot_winners(pot)

            amount_per_winner = (
                pot.amount / len(winners)
            )

            for seat in winners:
                player = self.betting_state.players[seat]
                player.stack += amount_per_winner

                self.payouts[seat] = (
                    self.payouts.get(seat, 0.0)
                    + amount_per_winner
                )

                all_winning_seats.add(seat)

            self.pot_awards.append(
                PotAward(
                    pot=pot,
                    winner_seats=winners,
                    amount_per_winner=amount_per_winner,
                )
            )

        self.winner_seats = tuple(
            sorted(all_winning_seats)
        )

        self.betting_state.pot = 0.0
        self.pot_awarded = True

        if len(self.winner_seats) == 1:
            self.betting_state.winner_seat = (
                self.winner_seats[0]
            )
        else:
            self.betting_state.winner_seat = None

    def _find_pot_winners(
        self,
        pot: Pot,
    ) -> tuple[int, ...]:
        if not pot.eligible_seats:
            raise RuntimeError(
                "A pot has no eligible players."
            )

        if len(pot.eligible_seats) == 1:
            return pot.eligible_seats

        scores: dict[int, tuple[int, ...]] = {}

        for seat in pot.eligible_seats:
            hand = self.hands[seat]

            if hand is None:
                raise RuntimeError(
                    f"Seat {seat} does not have a hand."
                )

            scores[seat] = hand.score

        best_score = min(scores.values())

        return tuple(
            seat
            for seat, score in scores.items()
            if score == best_score
        )