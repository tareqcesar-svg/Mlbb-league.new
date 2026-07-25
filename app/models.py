from datetime import datetime, timezone
from bson import ObjectId
from app.scheduler import generate_round_robin


def now_utc():
    return datetime.now(timezone.utc)


# ---------- Players ----------

def add_player(db, telegram_id, name):
    """Admin adds a player (registration happens via DM, not in-app)."""
    existing = db.players.find_one({"telegram_id": telegram_id})
    if existing:
        return existing["_id"]
    result = db.players.insert_one({
        "telegram_id": telegram_id,
        "name": name,
        "joined_at": now_utc(),
    })
    return result.inserted_id


# ---------- Seasons ----------

def create_season(db, season_number, player_ids, is_free=False, entry_fee=0):
    """
    Creates a season, generates the full round-robin schedule up front
    (rounds + matches, without time/referee assigned yet), and initializes
    each player's standings row at zero.
    """
    if len(player_ids) != 10:
        raise ValueError("This league format requires exactly 10 players")

    season_id = db.seasons.insert_one({
        "season_number": season_number,
        "status": "active",
        "is_free": is_free,
        "entry_fee": entry_fee,
        "created_at": now_utc(),
    }).inserted_id

    # initialize standings rows
    for pid in player_ids:
        db.season_players.insert_one({
            "season_id": season_id,
            "player_id": pid,
            "points": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "kills_for": 0,
            "kills_against": 0,
        })

    # generate the 9-round schedule (pairings only; time/referee set later per round)
    schedule = generate_round_robin(player_ids)
    for round_num, pairs in enumerate(schedule, start=1):
        round_id = db.rounds.insert_one({
            "season_id": season_id,
            "round_number": round_num,
            "date": None,  # set by admin when scheduling the round
        }).inserted_id

        for player1_id, player2_id in pairs:
            db.matches.insert_one({
                "round_id": round_id,
                "season_id": season_id,
                "player1_id": player1_id,
                "player2_id": player2_id,
                "match_time": None,          # set by admin
                "referee_telegram_id": None,  # set by admin
                "status": "unscheduled",      # unscheduled -> scheduled -> played
                "player1_kills": None,
                "player2_kills": None,
                "winner_id": None,            # None means draw, once played
            })

    return season_id


# ---------- Admin: schedule a match ----------

def set_match_schedule(db, match_id, match_time, referee_telegram_id):
    db.matches.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {
            "match_time": match_time,
            "referee_telegram_id": referee_telegram_id,
            "status": "scheduled",
        }}
    )


# ---------- Admin: submit a result ----------

def submit_result(db, match_id, player1_kills, player2_kills):
    match = db.matches.find_one({"_id": ObjectId(match_id)})
    if match is None:
        raise ValueError("Match not found")
    if match["status"] == "played":
        raise ValueError("Result already submitted for this match")

    if player1_kills > player2_kills:
        winner_id = match["player1_id"]
    elif player2_kills > player1_kills:
        winner_id = match["player2_id"]
    else:
        winner_id = None  # draw

    db.matches.update_one(
        {"_id": match["_id"]},
        {"$set": {
            "player1_kills": player1_kills,
            "player2_kills": player2_kills,
            "winner_id": winner_id,
            "status": "played",
        }}
    )

    _apply_result_to_standings(db, match, player1_kills, player2_kills, winner_id)


def _apply_result_to_standings(db, match, p1_kills, p2_kills, winner_id):
    season_id = match["season_id"]
    p1_id = match["player1_id"]
    p2_id = match["player2_id"]

    if winner_id == p1_id:
        p1_delta = {"points": 3, "wins": 1, "losses": 0, "draws": 0}
        p2_delta = {"points": 0, "wins": 0, "losses": 1, "draws": 0}
    elif winner_id == p2_id:
        p1_delta = {"points": 0, "wins": 0, "losses": 1, "draws": 0}
        p2_delta = {"points": 3, "wins": 1, "losses": 0, "draws": 0}
    else:
        p1_delta = {"points": 1, "wins": 0, "losses": 0, "draws": 1}
        p2_delta = {"points": 1, "wins": 0, "losses": 0, "draws": 1}

    db.season_players.update_one(
        {"season_id": season_id, "player_id": p1_id},
        {"$inc": {
            "points": p1_delta["points"],
            "wins": p1_delta["wins"],
            "losses": p1_delta["losses"],
            "draws": p1_delta["draws"],
            "kills_for": p1_kills,
            "kills_against": p2_kills,
        }}
    )
    db.season_players.update_one(
        {"season_id": season_id, "player_id": p2_id},
        {"$inc": {
            "points": p2_delta["points"],
            "wins": p2_delta["wins"],
            "losses": p2_delta["losses"],
            "draws": p2_delta["draws"],
            "kills_for": p2_kills,
            "kills_against": p1_kills,
        }}
    )


# ---------- Standings ----------

def get_standings(db, season_id):
    rows = list(db.season_players.find({"season_id": ObjectId(season_id)}))
    for row in rows:
        player = db.players.find_one({"_id": row["player_id"]})
        row["name"] = player["name"] if player else "؟"
        row["diff"] = row["kills_for"] - row["kills_against"]

    # sort: points desc, then kill differential desc (tiebreaker), as decided
    rows.sort(key=lambda r: (-r["points"], -r["diff"]))
    return rows
