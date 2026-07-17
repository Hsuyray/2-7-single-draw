from collections import Counter

from solver.cards import Card


RANK_VALUES = {
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
}


def evaluate_hand(cards: list[Card]) -> tuple[int, ...]:
    """
    Return a comparable score for a five-card 2-7 lowball hand.

    Lower tuples represent better hands.
    """

    if len(cards) != 5:
        raise ValueError("A hand must contain exactly five cards.")

    if len(set(cards)) != 5:
        raise ValueError("A hand cannot contain duplicate cards.")

    ranks = [RANK_VALUES[card.rank] for card in cards]
    suits = [card.suit for card in cards]

    rank_counts = Counter(ranks)
    count_pattern = sorted(rank_counts.values(), reverse=True)

    is_flush = len(set(suits)) == 1

    unique_ranks = sorted(set(ranks))
    is_straight = (
        len(unique_ranks) == 5
        and unique_ranks[-1] - unique_ranks[0] == 4
    )

    ranks_descending = sorted(ranks, reverse=True)

    # Category order for 2-7 lowball:
    # 0 = high card
    # 1 = one pair
    # 2 = two pair
    # 3 = three of a kind
    # 4 = straight
    # 5 = flush
    # 6 = full house
    # 7 = four of a kind
    # 8 = straight flush

    if is_straight and is_flush:
        return (8, max(ranks))

    if count_pattern == [4, 1]:
        four_rank = max(
            rank for rank, count in rank_counts.items() if count == 4
        )
        kicker = max(
            rank for rank, count in rank_counts.items() if count == 1
        )
        return (7, four_rank, kicker)

    if count_pattern == [3, 2]:
        trip_rank = max(
            rank for rank, count in rank_counts.items() if count == 3
        )
        pair_rank = max(
            rank for rank, count in rank_counts.items() if count == 2
        )
        return (6, trip_rank, pair_rank)

    if is_flush:
        return (5, *ranks_descending)

    if is_straight:
        return (4, max(ranks))

    if count_pattern == [3, 1, 1]:
        trip_rank = max(
            rank for rank, count in rank_counts.items() if count == 3
        )
        kickers = sorted(
            (
                rank
                for rank, count in rank_counts.items()
                if count == 1
            ),
            reverse=True,
        )
        return (3, trip_rank, *kickers)

    if count_pattern == [2, 2, 1]:
        pair_ranks = sorted(
            (
                rank
                for rank, count in rank_counts.items()
                if count == 2
            ),
            reverse=True,
        )
        kicker = max(
            rank for rank, count in rank_counts.items() if count == 1
        )
        return (2, *pair_ranks, kicker)

    if count_pattern == [2, 1, 1, 1]:
        pair_rank = max(
            rank for rank, count in rank_counts.items() if count == 2
        )
        kickers = sorted(
            (
                rank
                for rank, count in rank_counts.items()
                if count == 1
            ),
            reverse=True,
        )
        return (1, pair_rank, *kickers)

    return (0, *ranks_descending)


def compare_hands(
    first_hand: list[Card],
    second_hand: list[Card],
) -> int:
    """
    Return:
    -1 if the first hand is better
     0 if the hands tie
     1 if the second hand is better
    """

    first_score = evaluate_hand(first_hand)
    second_score = evaluate_hand(second_hand)

    if first_score < second_score:
        return -1

    if first_score > second_score:
        return 1

    return 0