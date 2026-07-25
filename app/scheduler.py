"""
Round-robin schedule generator using the classic 'circle method'.

For N players (N must be even here, 10 in our case):
- Produces N-1 rounds
- Each round has N/2 matches
- Every player faces every other player exactly once across all rounds
"""


def generate_round_robin(player_ids):
    """
    player_ids: list of player identifiers (e.g. MongoDB _id strings), length must be even.

    Returns: list of rounds, where each round is a list of (player_a, player_b) tuples.
    Example return shape for 4 players:
        [
          [(p1, p4), (p2, p3)],   # round 1
          [(p1, p3), (p4, p2)],   # round 2
          [(p1, p2), (p3, p4)],   # round 3
        ]
    """
    players = list(player_ids)
    n = len(players)

    if n % 2 != 0:
        raise ValueError("Round-robin here requires an even number of players (got %d)" % n)

    num_rounds = n - 1
    half = n // 2

    # Fix the first player in place, rotate the rest
    fixed = players[0]
    rotating = players[1:]

    rounds = []
    for round_num in range(num_rounds):
        round_order = [fixed] + rotating
        pairs = []
        for i in range(half):
            a = round_order[i]
            b = round_order[n - 1 - i]
            pairs.append((a, b))
        rounds.append(pairs)

        # rotate the 'rotating' list by one position
        rotating = [rotating[-1]] + rotating[:-1]

    return rounds


if __name__ == "__main__":
    # quick manual check with 10 sample players
    sample_players = [f"P{i}" for i in range(1, 11)]
    schedule = generate_round_robin(sample_players)

    print(f"Generated {len(schedule)} rounds for {len(sample_players)} players\n")
    for idx, round_matches in enumerate(schedule, start=1):
        print(f"Round {idx}:")
        for a, b in round_matches:
            print(f"  {a}  vs  {b}")
        print()

    # sanity check: every player should appear exactly once per round,
    # and every pair should appear exactly once across the whole schedule
    all_pairs = set()
    for round_matches in schedule:
        seen_this_round = set()
        for a, b in round_matches:
            assert a not in seen_this_round and b not in seen_this_round, "player double-booked in a round"
            seen_this_round.add(a)
            seen_this_round.add(b)
            pair_key = tuple(sorted([a, b]))
            assert pair_key not in all_pairs, f"duplicate pairing: {pair_key}"
            all_pairs.add(pair_key)

    expected_pairs = len(sample_players) * (len(sample_players) - 1) // 2
    assert len(all_pairs) == expected_pairs, "pair count mismatch"
    print(f"Sanity check passed: {len(all_pairs)} unique pairings across {len(schedule)} rounds.")
