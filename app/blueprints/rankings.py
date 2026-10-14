from flask import Blueprint, jsonify, current_app
from ..helpers import (
    VALID_SPORTS, get_db, err, current_user, login_required, _apply_privacy
)

rankings_bp = Blueprint("rankings", __name__, url_prefix="/api")

# Removed from this module: a second registration of
# /api/<sport>/fighters/<id>/matches, which carried no @login_required. The
# same rule is registered in fighters.py *with* authentication, and because
# fighters_bp is registered first in the app factory that protected handler is
# the one Flask matched — so this copy was unreachable. It was still a hazard:
# swapping two register_blueprint lines would have silently made the
# unauthenticated version live. The route continues to be served by
# fighters.py.


@rankings_bp.route("/<sport>/rankings", methods=["GET"])
@login_required
def get_rankings(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    try:
        from ..services.matchmaker import elo_band
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
        # Was `return err(str(e))`, which handed the caller the raw exception
        # text — table names, column names and occasionally a connection string
        # fragment. The detail belongs in the log, not in the response.
        current_app.logger.exception("rankings failed for sport=%s", sport)
        return err("Could not build the rankings just now.", 500)


@rankings_bp.route("/stats", methods=["GET"])
@login_required
def stats():
    totals = {}
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            totals[sport] = len(db.get_all_fighters())
    totals["total"] = sum(totals.values())
    return jsonify(totals)
