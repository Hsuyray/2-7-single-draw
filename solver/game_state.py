from dataclasses import dataclass, field
from enum import Enum


MIN_PLAYERS = 2
MAX_PLAYERS = 6
CHIP_EPSILON = 1e-9


class ActionType(str, Enum):
    FOLD = "fold"
    CALL = "call"
    CHECK = "check"
    RAISE = "raise"


@dataclass(frozen=True)
class GameConfig:
    player_count: int
    starting_stack: float = 100.0
    starting_stacks: tuple[float, ...] | None = None
    small_blind: float = 0.5
    big_blind: float = 1.0
    big_blind_ante: float = 1.5

    def __post_init__(self) -> None:
        if not MIN_PLAYERS <= self.player_count <= MAX_PLAYERS:
            raise ValueError("Player count must be between 2 and 6.")

        if self.starting_stack <= 0:
            raise ValueError("Starting stack must be positive.")

        if self.starting_stacks is not None:
            if len(self.starting_stacks) != self.player_count:
                raise ValueError(
                    "Starting stacks must match player count."
                )

            if any(
                stack <= 0
                for stack in self.starting_stacks
            ):
                raise ValueError(
                    "Every starting stack must be positive."
                )

        if self.small_blind <= 0:
            raise ValueError("Small blind must be positive.")

        if self.big_blind <= self.small_blind:
            raise ValueError(
                "Big blind must be greater than small blind."
            )

        if self.big_blind_ante < 0:
            raise ValueError(
                "Big blind ante cannot be negative."
            )

    def stack_for_seat(self, seat: int) -> float:
        if self.starting_stacks is None:
            return self.starting_stack

        return self.starting_stacks[seat]


@dataclass
class PlayerState:
    seat: int
    stack: float
    committed_this_round: float = 0.0
    committed_total: float = 0.0
    dead_money_committed: float = 0.0
    has_folded: bool = False
    is_all_in: bool = False
    has_acted_since_last_raise: bool = False
    
    def post_forced_bet(
        self,
        amount: float,
        *,
        counts_toward_current_bet: bool,
    ) -> float:
        return self.commit_chips(
            amount,
            counts_toward_current_bet=counts_toward_current_bet,
        )

    def commit_chips(
        self,
        amount: float,
        *,
        counts_toward_current_bet: bool = True,
    ) -> float:
        if amount < 0:
            raise ValueError("Chip amount cannot be negative.")

        paid = min(amount, self.stack)

        self.stack -= paid
        self.committed_total += paid

        if counts_toward_current_bet:
            self.committed_this_round += paid
        else:
            self.dead_money_committed += paid

        if self.stack == 0:
            self.is_all_in = True

        return paid


@dataclass
class GameState:
    config: GameConfig
    button_seat: int = 0
    players: list[PlayerState] = field(init=False)
    small_blind_seat: int = field(init=False)
    big_blind_seat: int = field(init=False)
    acting_seat: int | None = field(init=False)
    pot: float = field(init=False, default=0.0)
    current_bet: float = field(init=False, default=0.0)
    minimum_raise_size: float = field(init=False)
    betting_round_complete: bool = field(
        init=False,
        default=False,
    )
    hand_complete: bool = field(
        init=False,
        default=False,
    )
    winner_seat: int | None = field(
        init=False,
        default=None,
    )
    action_history: list[
        tuple[int, ActionType, float]
    ] = field(
        init=False,
        default_factory=list,
    )

    def __post_init__(self) -> None:
        if not 0 <= self.button_seat < self.config.player_count:
            raise ValueError("Button seat is outside the table.")

        self.players = [
            PlayerState(
                seat=seat,
                stack=self.config.stack_for_seat(seat),
            )
            for seat in range(self.config.player_count)
        ]

        self.small_blind_seat = self._find_small_blind_seat()
        self.big_blind_seat = self._next_seat(
            self.small_blind_seat
        )

        self._post_forced_bets()

        self.current_bet = self.players[
            self.big_blind_seat
        ].committed_this_round

        self.minimum_raise_size = self.config.big_blind
        self.acting_seat = self._find_first_predraw_actor()

    @property
    def acting_player(self) -> PlayerState:
        if self.acting_seat is None:
            raise RuntimeError("No player is currently acting.")

        return self.players[self.acting_seat]

    def _next_seat(self, seat: int) -> int:
        return (seat + 1) % self.config.player_count

    def _find_small_blind_seat(self) -> int:
        if self.config.player_count == 2:
            return self.button_seat

        return self._next_seat(self.button_seat)

    def _find_first_predraw_actor(self) -> int:
        if self.config.player_count == 2:
            return self.button_seat

        return self._next_seat(self.big_blind_seat)

    def _post_forced_bets(self) -> None:
        small_blind_player = self.players[
            self.small_blind_seat
        ]
        big_blind_player = self.players[
            self.big_blind_seat
        ]

        self.pot += small_blind_player.post_forced_bet(
            self.config.small_blind,
            counts_toward_current_bet=True,
        )

        self.pot += big_blind_player.post_forced_bet(
            self.config.big_blind,
            counts_toward_current_bet=True,
        )

        self.pot += big_blind_player.post_forced_bet(
            self.config.big_blind_ante,
            counts_toward_current_bet=False,
        )

    def amount_to_call(self, seat: int) -> float:
        player = self.players[seat]

        return max(
            0.0,
            self.current_bet - player.committed_this_round,
        )

    def minimum_raise_to(self) -> float:
        return self.current_bet + self.minimum_raise_size

    def maximum_raise_to(self, seat: int) -> float:
        player = self.players[seat]

        return player.committed_this_round + player.stack

    def legal_actions(self) -> set[ActionType]:
        if (
            self.betting_round_complete
            or self.hand_complete
            or self.acting_seat is None
        ):
            return set()

        player = self.acting_player

        if player.has_folded or player.is_all_in:
            return set()

        to_call = self.amount_to_call(self.acting_seat)
        actions: set[ActionType] = set()

        if to_call == 0:
            actions.add(ActionType.CHECK)
        else:
            actions.add(ActionType.FOLD)
            actions.add(ActionType.CALL)

        maximum_raise_to = self.maximum_raise_to(
            self.acting_seat
        )

        if maximum_raise_to > self.current_bet:
            actions.add(ActionType.RAISE)

        return actions

    def apply_action(
        self,
        action: ActionType,
        *,
        raise_to: float | None = None,
    ) -> None:
        if action not in self.legal_actions():
            action_name = action.value

            raise ValueError(
                f"Illegal action {action_name} for seat "
                f"{self.acting_seat}."
            )

        player = self.acting_player
        acting_seat = player.seat
        amount_paid = 0.0

        if action == ActionType.FOLD:
            player.has_folded = True
            player.has_acted_since_last_raise = True

        elif action == ActionType.CALL:
            amount_paid = player.commit_chips(
                self.amount_to_call(acting_seat)
            )
            self.pot += amount_paid
            player.has_acted_since_last_raise = True

        elif action == ActionType.CHECK:
            player.has_acted_since_last_raise = True

        elif action == ActionType.RAISE:
            amount_paid = self._apply_raise(
                player=player,
                raise_to=raise_to,
            )

        self.action_history.append(
            (acting_seat, action, amount_paid)
        )

        self._update_game_progress(
            previous_acting_seat=acting_seat
        )

    def _apply_raise(
        self,
        *,
        player: PlayerState,
        raise_to: float | None,
    ) -> float:
        if raise_to is None:
            raise ValueError(
                "raise_to is required for a raise."
            )

        if raise_to <= self.current_bet:
            raise ValueError(
                "Raise-to amount must exceed the current bet."
            )

        maximum_raise_to = self.maximum_raise_to(player.seat)

        if raise_to > maximum_raise_to:
            raise ValueError(
                "Player does not have enough chips."
            )

        raise_size = raise_to - self.current_bet
        is_all_in = (
            abs(raise_to - maximum_raise_to)
            <= CHIP_EPSILON
        )

        if (
            raise_size
            < self.minimum_raise_size - CHIP_EPSILON
            and not is_all_in
        ):
            raise ValueError(
                "Raise is smaller than the minimum raise."
            )
        amount_needed = (
            raise_to - player.committed_this_round
        )

        amount_paid = player.commit_chips(amount_needed)
        self.pot += amount_paid

        if raise_size >= self.minimum_raise_size:
            self.minimum_raise_size = raise_size

        self.current_bet = raise_to

        for other_player in self.players:
            if (
                other_player.seat != player.seat
                and not other_player.has_folded
                and not other_player.is_all_in
            ):
                other_player.has_acted_since_last_raise = False

        player.has_acted_since_last_raise = True

        return amount_paid

    def _update_game_progress(
        self,
        *,
        previous_acting_seat: int,
    ) -> None:
        active_players = [
            player
            for player in self.players
            if not player.has_folded
        ]

        if len(active_players) == 1:
            self.hand_complete = True
            self.betting_round_complete = True
            self.winner_seat = active_players[0].seat
            self.acting_seat = None
            return

        if self._is_betting_round_complete():
            self.betting_round_complete = True
            self.acting_seat = None
            return

        self.acting_seat = self._find_next_actor(
            previous_acting_seat
        )

    def _is_betting_round_complete(self) -> bool:
        eligible_players = [
            player
            for player in self.players
            if not player.has_folded and not player.is_all_in
        ]

        if len(eligible_players) <= 1:
            return True

        for player in eligible_players:
            if not player.has_acted_since_last_raise:
                return False

            if (
                abs(
                    player.committed_this_round
                    - self.current_bet
                )
                > CHIP_EPSILON
            ):
                return False

        return True

    def _find_next_actor(
        self,
        current_seat: int,
    ) -> int:
        seat = self._next_seat(current_seat)

        for _ in range(self.config.player_count):
            player = self.players[seat]

            if (
                not player.has_folded
                and not player.is_all_in
            ):
                return seat

            seat = self._next_seat(seat)

        raise RuntimeError(
            "No eligible player available to act."
        )

    def start_new_betting_round(
        self,
        *,
        first_acting_seat: int,
    ) -> None:
        if self.hand_complete:
            raise RuntimeError(
                "Cannot start a new betting round after the hand is complete."
            )

        if not 0 <= first_acting_seat < self.config.player_count:
            raise ValueError(
                "First acting seat is outside the table."
            )

        first_player = self.players[first_acting_seat]

        if first_player.has_folded:
            raise ValueError(
                "A folded player cannot act first."
            )

        if first_player.is_all_in:
            raise ValueError(
                "An all-in player cannot act first."
            )

        for player in self.players:
            player.committed_this_round = 0.0
            player.has_acted_since_last_raise = False

        self.current_bet = 0.0
        self.minimum_raise_size = self.config.big_blind
        self.betting_round_complete = False
        self.acting_seat = first_acting_seat


