import pytest

from solver.game_state import ActionType, GameConfig
from solver.hand import Hand
from solver.single_draw_game import (
    GamePhase,
    SingleDrawGame,
)
from solver.pots import Pot


def create_three_player_game() -> SingleDrawGame:
    return SingleDrawGame(
        config=GameConfig(player_count=3),
        button_seat=0,
        shuffle_deck=False,
    )


def complete_predraw_betting(
    game: SingleDrawGame,
) -> None:
    game.apply_betting_action(ActionType.CALL)
    game.apply_betting_action(ActionType.CALL)
    game.apply_betting_action(ActionType.CHECK)


def complete_draw_with_stand_pat(
    game: SingleDrawGame,
) -> None:
    while game.phase == GamePhase.DRAW:
        seat = game.draw_acting_seat
        assert seat is not None

        game.submit_draw(
            seat=seat,
            discard_indices=[],
        )


def test_game_deals_five_cards_to_each_player() -> None:
    game = create_three_player_game()

    assert all(
        hand is not None and len(hand.cards) == 5
        for hand in game.hands
    )


def test_dealt_cards_are_unique() -> None:
    game = create_three_player_game()

    all_cards = [
        card
        for hand in game.hands
        if hand is not None
        for card in hand.cards
    ]

    assert len(all_cards) == 15
    assert len(set(all_cards)) == 15


def test_dealing_removes_cards_from_deck() -> None:
    game = create_three_player_game()

    assert len(game.deck) == 37


def test_game_starts_in_predraw_betting() -> None:
    game = create_three_player_game()

    assert game.phase == GamePhase.PREDRAW_BETTING
    assert game.acting_seat == 0


def test_completed_predraw_betting_starts_draw() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    assert game.phase == GamePhase.DRAW
    assert game.draw_acting_seat == 1


def test_draw_order_starts_left_of_button() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    assert game.draw_order == [1, 2, 0]


def test_stand_pat_advances_draw_action() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    game.submit_draw(
        seat=1,
        discard_indices=[],
    )

    assert game.draw_acting_seat == 2


def test_player_can_replace_one_card() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    original_hand = game.hands[1]
    assert original_hand is not None

    replacement_card = game.deck.stock[-1]
    game.deck.stock = [replacement_card]

    result = game.submit_draw(
        seat=1,
        discard_indices=[4],
    )

    assert len(result.discarded_cards) == 1
    assert result.drawn_cards == (replacement_card,)
    assert replacement_card in result.final_hand.cards
    assert result.discarded_cards[0] not in result.final_hand.cards
    assert game.hands[1] == result.final_hand
    assert len(result.final_hand.cards) == 5
    assert len(set(result.final_hand.cards)) == 5


def test_cannot_draw_out_of_turn() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    with pytest.raises(ValueError):
        game.submit_draw(
            seat=2,
            discard_indices=[],
        )


def test_all_players_drawing_starts_postdraw_betting() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    assert game.phase == GamePhase.POSTDRAW_BETTING
    assert game.acting_seat == 1
    assert game.betting_state.current_bet == 0.0


def test_postdraw_betting_starts_with_check() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    assert ActionType.CHECK in (
        game.betting_state.legal_actions()
    )


def test_postdraw_checks_lead_to_showdown() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)

    assert game.phase == GamePhase.COMPLETE
    assert len(game.winner_seats) >= 1


def test_best_low_hand_wins_showdown() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "8s",
        "6h",
        "4c",
        "3d",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "9s",
        "7h",
        "5d",
        "3s",
        "2c",
    )

    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)

    assert game.phase == GamePhase.COMPLETE
    assert game.winner_seats == (0,)


def test_identical_rank_hands_split_showdown() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "7h",
        "5d",
        "4c",
        "3s",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "9s",
        "8h",
        "6d",
        "4s",
        "2c",
    )

    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)

    assert game.winner_seats == (0, 1)


def test_everyone_folding_ends_hand_before_draw() -> None:
    game = create_three_player_game()

    game.apply_betting_action(ActionType.FOLD)
    game.apply_betting_action(ActionType.FOLD)

    assert game.phase == GamePhase.COMPLETE
    assert game.winner_seats == (
        game.betting_state.big_blind_seat,
    )


def test_betting_action_is_rejected_during_draw() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    with pytest.raises(RuntimeError):
        game.apply_betting_action(ActionType.CHECK)


def test_draw_is_rejected_during_betting() -> None:
    game = create_three_player_game()

    with pytest.raises(RuntimeError):
        game.submit_draw(
            seat=0,
            discard_indices=[],
        )


def test_single_winner_receives_entire_pot() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "8s",
        "6h",
        "4c",
        "3d",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "9s",
        "7h",
        "5d",
        "3s",
        "2c",
    )

    pot_before_showdown = game.pot
    winner_stack_before = (
        game.betting_state.players[0].stack
    )

    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)

    winner = game.betting_state.players[0]

    assert game.winner_seats == (0,)
    assert game.payouts == {
        0: pot_before_showdown,
    }
    assert winner.stack == (
        winner_stack_before + pot_before_showdown
    )
    assert game.pot == 0.0
    assert game.pot_awarded


def test_tied_players_split_pot_evenly() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "7h",
        "5d",
        "4c",
        "3s",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "9s",
        "8h",
        "6d",
        "4s",
        "2c",
    )

    pot_before_showdown = game.pot
    first_stack_before = (
        game.betting_state.players[0].stack
    )
    second_stack_before = (
        game.betting_state.players[1].stack
    )

    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)

    expected_share = pot_before_showdown / 2

    assert game.winner_seats == (0, 1)
    assert game.payouts == {
        0: expected_share,
        1: expected_share,
    }
    assert game.betting_state.players[0].stack == (
        first_stack_before + expected_share
    )
    assert game.betting_state.players[1].stack == (
        second_stack_before + expected_share
    )
    assert game.pot == 0.0


def test_fold_winner_receives_pot() -> None:
    game = create_three_player_game()

    winner_seat = game.betting_state.big_blind_seat
    winner_stack_before = (
        game.betting_state.players[winner_seat].stack
    )
    pot_before_folds = game.pot

    game.apply_betting_action(ActionType.FOLD)
    game.apply_betting_action(ActionType.FOLD)

    assert game.phase == GamePhase.COMPLETE
    assert game.winner_seats == (winner_seat,)
    assert game.payouts == {
        winner_seat: pot_before_folds,
    }
    assert (
        game.betting_state.players[winner_seat].stack
        == winner_stack_before + pot_before_folds
    )
    assert game.pot == 0.0


def test_pot_cannot_be_awarded_twice() -> None:
    game = create_three_player_game()

    game.apply_betting_action(ActionType.FOLD)
    game.apply_betting_action(ActionType.FOLD)

    with pytest.raises(RuntimeError):
        game._award_pots()


def test_different_players_can_win_main_and_side_pots() -> None:
    game = create_three_player_game()

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "9s",
        "8h",
        "6d",
        "4c",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "8s",
        "6h",
        "5d",
        "3s",
        "2c",
    )

    commitments = [5.0, 10.0, 10.0]

    for player, commitment in zip(
        game.betting_state.players,
        commitments,
        strict=True,
    ):
        player.committed_total = commitment
        player.dead_money_committed = 0.0
        player.stack = 100.0 - commitment

    game.betting_state.pot = sum(commitments)

    game._award_pots()

    assert game.payouts == {
        0: 15.0,
        2: 10.0,
    }

    assert game.winner_seats == (0, 2)

    assert game.pot_awards[0].pot == Pot(
        amount=15.0,
        eligible_seats=(0, 1, 2),
    )
    assert game.pot_awards[0].winner_seats == (0,)

    assert game.pot_awards[1].pot == Pot(
        amount=10.0,
        eligible_seats=(1, 2),
    )
    assert game.pot_awards[1].winner_seats == (2,)

    assert game.betting_state.players[0].stack == 110.0
    assert game.betting_state.players[2].stack == 100.0
    assert game.pot == 0.0


def test_tied_main_pot_and_single_side_pot_winner() -> None:
    game = create_three_player_game()

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "7h",
        "5d",
        "4c",
        "3s",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "8s",
        "6h",
        "5d",
        "3c",
        "2c",
    )

    commitments = [5.0, 10.0, 10.0]

    for player, commitment in zip(
        game.betting_state.players,
        commitments,
        strict=True,
    ):
        player.committed_total = commitment
        player.dead_money_committed = 0.0
        player.stack = 100.0 - commitment

    game.betting_state.pot = sum(commitments)

    game._award_pots()

    assert game.payouts == {
        0: 7.5,
        1: 17.5,
    }

    assert game.winner_seats == (0, 1)
    assert len(game.pot_awards) == 2

    assert game.pot_awards[0].winner_seats == (0, 1)
    assert game.pot_awards[0].amount_per_winner == 7.5

    assert game.pot_awards[1].winner_seats == (1,)
    assert game.pot_awards[1].amount_per_winner == 10.0


def test_folded_player_funds_pot_but_cannot_win() -> None:
    game = create_three_player_game()

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "8s",
        "6h",
        "4c",
        "3d",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "9s",
        "7h",
        "5d",
        "3s",
        "2c",
    )

    commitments = [10.0, 10.0, 10.0]

    for player, commitment in zip(
        game.betting_state.players,
        commitments,
        strict=True,
    ):
        player.committed_total = commitment
        player.stack = 100.0 - commitment

    game.betting_state.players[0].has_folded = True
    game.betting_state.pot = 30.0

    game._award_pots()

    assert game.payouts == {
        1: 30.0,
    }
    assert game.winner_seats == (1,)


def test_pot_total_must_match_commitments() -> None:
    game = create_three_player_game()

    for player in game.betting_state.players:
        player.committed_total = 10.0

    game.betting_state.pot = 25.0

    with pytest.raises(RuntimeError):
        game._award_pots()


def test_big_blind_ante_is_dead_money_in_main_pot() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)
    complete_draw_with_stand_pat(game)

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "8s",
        "6h",
        "4c",
        "3d",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "9s",
        "7h",
        "5d",
        "3s",
        "2c",
    )

    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)
    game.apply_betting_action(ActionType.CHECK)

    assert game.winner_seats == (0,)
    assert len(game.pot_awards) == 1
    assert game.pot_awards[0].winner_seats == (0,)


def test_different_starting_stacks_create_real_side_pots() -> None:
    game = SingleDrawGame(
        config=GameConfig(
            player_count=3,
            starting_stacks=(5.0, 10.0, 10.0),
            big_blind_ante=0.0,
        ),
        button_seat=0,
        shuffle_deck=False,
    )

    game.hands[0] = Hand.from_strings(
        "7s",
        "5h",
        "4d",
        "3c",
        "2s",
    )
    game.hands[1] = Hand.from_strings(
        "9s",
        "8h",
        "6d",
        "4c",
        "2h",
    )
    game.hands[2] = Hand.from_strings(
        "8s",
        "6h",
        "5d",
        "3s",
        "2c",
    )

    game.betting_state.players[0].committed_total = 5.0
    game.betting_state.players[0].stack = 0.0
    game.betting_state.players[0].is_all_in = True

    game.betting_state.players[1].committed_total = 10.0
    game.betting_state.players[1].stack = 0.0
    game.betting_state.players[1].is_all_in = True

    game.betting_state.players[2].committed_total = 10.0
    game.betting_state.players[2].stack = 0.0
    game.betting_state.players[2].is_all_in = True

    for player in game.betting_state.players:
        player.dead_money_committed = 0.0

    game.betting_state.pot = 25.0

    game._award_pots()

    assert game.payouts == {
        0: 15.0,
        2: 10.0,
    }

    assert game.betting_state.players[0].stack == 15.0
    assert game.betting_state.players[1].stack == 0.0
    assert game.betting_state.players[2].stack == 10.0


def test_discarded_cards_enter_game_muck() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    acting_seat = game.draw_acting_seat
    assert acting_seat is not None

    original_hand = game.hands[acting_seat]
    assert original_hand is not None

    discarded_card = original_hand.cards[4]

    game.submit_draw(
        seat=acting_seat,
        discard_indices=[4],
    )

    assert discarded_card in game.deck.muck


def test_player_cannot_immediately_redraw_discarded_card() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    acting_seat = game.draw_acting_seat
    assert acting_seat is not None

    original_hand = game.hands[acting_seat]
    assert original_hand is not None

    discarded_card = original_hand.cards[4]
    replacement_card = game.deck.stock[-1]

    result = game.submit_draw(
        seat=acting_seat,
        discard_indices=[4],
    )

    assert result.drawn_cards == (replacement_card,)
    assert discarded_card not in result.drawn_cards
    assert discarded_card in game.deck.muck


def test_later_player_can_draw_from_previous_players_muck() -> None:
    game = create_three_player_game()

    complete_predraw_betting(game)

    first_seat = game.draw_acting_seat
    assert first_seat is not None

    first_hand = game.hands[first_seat]
    assert first_hand is not None

    first_discard = first_hand.cards[4]

    # Leave exactly one card in stock for the first player.
    first_replacement = game.deck.stock[-1]
    game.deck.stock = [first_replacement]

    game.submit_draw(
        seat=first_seat,
        discard_indices=[4],
    )

    assert game.deck.stock_size == 0
    assert first_discard in game.deck.muck

    second_seat = game.draw_acting_seat
    assert second_seat is not None

    result = game.submit_draw(
        seat=second_seat,
        discard_indices=[4],
    )

    assert result.drawn_cards == (first_discard,)
    assert game.deck.muck_size == 1


def test_starting_hands_are_canonicalized() -> None:
    game = create_three_player_game()

    for hand in game.hands:
        assert hand is not None

        ranks = [
            card.rank
            for card in hand.cards
        ]

        rank_values = [
            {
                "2": 2,
                "3": 3,
                "4": 4,
                "5": 5,
                "6": 6,
                "7": 7,
                "8": 8,
                "9": 9,
                "T": 10,
                "J": 11,
                "Q": 12,
                "K": 13,
                "A": 14,
            }[rank]
            for rank in ranks
        ]

        assert rank_values == sorted(rank_values)