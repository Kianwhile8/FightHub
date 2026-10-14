"""Rankings and headline stats.

  GET /api/<sport>/rankings   every fighter in the sport, highest Elo first
  GET /api/stats              fighter counts per sport

Matchmaking (/api/<sport>/fighters/<id>/matches) lives in fighters.py.
"""

from flask import Blueprint, jsonify, current_app
from ..helpers import (
    VALID_SPORTS, get_db, err, current_user, login_required, _apply_privacy
)
from ..services.matchmaker import elo_band

rankings_bp = Blueprint("rankings", __name__, url_prefix="/api")


@rankings_bp.route("/<sport>/rankings", methods=["GET"])
@login_required
def get_rankings(sport):
    """Every fighter in the sport, ranked by Elo (hidden records masked)."""
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    try:
        with get_db(sport) as db:
            fighters    = db.get_all_fighters()
            elo_ratings = db.elo_pool()

        if not fighters:
            return jsonify({"sport": sport, "rankings": []})
        ranked = sorted(
            [{**f, "elo": elo_ratings.get(f["id"], 0.0),
              "elo_band": elo_band(elo_ratings.get(f["id"], 0.0))}
             for f in fighters],
            key=lambda x: x["elo"], reverse=True
        )
        ranked = _apply_privacy(ranked, sport, current_user())
        for i, f in enumerate(ranked):
            f["rank"] = i + 1
        return jsonify({"sport": sport, "rankings": ranked})
    except Exception:
        # Log the detail; never send raw exception text to the client.
        current_app.logger.exception("rankings failed for sport=%s", sport)
        return err("Could not build the rankings just now.", 500)


@rankings_bp.route("/stats", methods=["GET"])
@login_required
def stats():
    """{sport: fighter count, ..., "total": n}."""
    totals = {}
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            totals[sport] = len(db.get_all_fighters())
    totals["total"] = sum(totals.values())
    return jsonify(totals)
