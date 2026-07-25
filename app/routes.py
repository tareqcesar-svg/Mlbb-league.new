from flask import Blueprint, current_app, request, jsonify
from bson import ObjectId
from datetime import datetime

from app import models

bp = Blueprint("main", __name__)


def db():
    return current_app.config["DB"]


# ---------------- Public endpoints ----------------

@bp.route("/api/standings/<season_id>")
def standings(season_id):
    rows = models.get_standings(db(), season_id)
    out = [{
        "rank": i + 1,
        "name": r["name"],
        "games": r["wins"] + r["losses"] + r["draws"],
        "wins": r["wins"],
        "losses": r["losses"],
        "draws": r["draws"],
        "kills_for": r["kills_for"],
        "kills_against": r["kills_against"],
        "diff": r["diff"],
        "points": r["points"],
    } for i, r in enumerate(rows)]
    return jsonify(out)


@bp.route("/api/schedule/<season_id>")
def schedule(season_id):
    rounds = list(db().rounds.find({"season_id": ObjectId(season_id)}).sort("round_number", 1))
    out = []
    for rnd in rounds:
        matches = list(db().matches.find({"round_id": rnd["_id"]}))
        match_list = []
        for m in matches:
            p1 = db().players.find_one({"_id": m["player1_id"]})
            p2 = db().players.find_one({"_id": m["player2_id"]})
            match_list.append({
                "match_id": str(m["_id"]),
                "player1": p1["name"] if p1 else "؟",
                "player2": p2["name"] if p2 else "؟",
                "match_time": m["match_time"],
                "referee_telegram_id": m["referee_telegram_id"],
                "status": m["status"],
                "player1_kills": m["player1_kills"],
                "player2_kills": m["player2_kills"],
            })
        out.append({
            "round_number": rnd["round_number"],
            "date": rnd["date"],
            "matches": match_list,
        })
    return jsonify(out)


@bp.route("/api/my-matches/<season_id>/<telegram_id>")
def my_matches(season_id, telegram_id):
    player = db().players.find_one({"telegram_id": telegram_id})
    if not player:
        return jsonify({"error": "player not found"}), 404

    matches = list(db().matches.find({
        "season_id": ObjectId(season_id),
        "$or": [{"player1_id": player["_id"]}, {"player2_id": player["_id"]}],
    }))

    out = []
    for m in matches:
        opponent_id = m["player2_id"] if m["player1_id"] == player["_id"] else m["player1_id"]
        opponent = db().players.find_one({"_id": opponent_id})
        out.append({
            "match_id": str(m["_id"]),
            "opponent": opponent["name"] if opponent else "؟",
            "match_time": m["match_time"],
            "status": m["status"],
            "my_kills": m["player1_kills"] if m["player1_id"] == player["_id"] else m["player2_kills"],
            "opponent_kills": m["player2_kills"] if m["player1_id"] == player["_id"] else m["player1_kills"],
        })
    return jsonify(out)


# ---------------- Admin endpoints ----------------
# NOTE: these have no auth check yet — before going live, protect these
# routes (e.g. check the caller's Telegram id against your own admin id).

@bp.route("/api/admin/add-player", methods=["POST"])
def admin_add_player():
    data = request.get_json()
    player_id = models.add_player(db(), data["telegram_id"], data["name"])
    return jsonify({"player_id": str(player_id)})


@bp.route("/api/admin/create-season", methods=["POST"])
def admin_create_season():
    data = request.get_json()
    player_ids = [ObjectId(pid) for pid in data["player_ids"]]
    season_id = models.create_season(
        db(),
        season_number=data["season_number"],
        player_ids=player_ids,
        is_free=data.get("is_free", False),
        entry_fee=data.get("entry_fee", 0),
    )
    return jsonify({"season_id": str(season_id)})


@bp.route("/api/admin/schedule-match", methods=["POST"])
def admin_schedule_match():
    data = request.get_json()
    match_time = datetime.fromisoformat(data["match_time"])
    models.set_match_schedule(db(), data["match_id"], match_time, data["referee_telegram_id"])
    return jsonify({"ok": True})


@bp.route("/api/admin/submit-result", methods=["POST"])
def admin_submit_result():
    data = request.get_json()
    models.submit_result(db(), data["match_id"], data["player1_kills"], data["player2_kills"])
    return jsonify({"ok": True})
