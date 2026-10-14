from flask import Blueprint, jsonify, request, current_app
from ..helpers import (
    VALID_SPORTS, get_db, err, require_json, current_user,
    login_required, roles_required, subscription_required, _apply_privacy
)

gyms_bp = Blueprint("gyms", __name__, url_prefix="/api/gyms")


@gyms_bp.route("", methods=["GET"])
@login_required
def list_gyms():
    """All gyms, or just the caller's own with ?mine=1.

    Coaches used to be served only their own gyms here, which meant the one
    role that most needs to see the wider scene — to find opponents, or to know
    which gyms are nearby — was the only role that could not. The listing now
    returns everything and the client separates "my gyms" from the rest;
    ?mine=1 is for places that genuinely need only the caller's own, such as
    the gym picker on the new-fighter form.
    """
    user   = current_user()
    county = request.args.get("county", "").strip() or None
    mine   = request.args.get("mine", "").lower() in ("1", "true", "yes")
    if mine and user["role"] == "coach":
        gyms = current_app.auth_db.get_all_gyms_by_coach(user["id"], county)
    else:
        gyms = current_app.auth_db.get_all_gyms(county)
    return jsonify({"gyms": gyms})


@gyms_bp.route("", methods=["POST"])
@roles_required("coach", "admin")
@subscription_required
def create_gym():
    data, error = require_json("name")
    if error:
        return error
    try:
        gym = current_app.auth_db.create_gym(
            name=data["name"],
            coach_id=current_user()["id"],
            location=data.get("location", ""),
            county=data.get("county") or None,
        )
        return jsonify({"gym": gym}), 201
    except ValueError as e:
        return err(str(e))


@gyms_bp.route("/<int:gym_id>", methods=["GET"])
@login_required
def get_gym(gym_id):
    gym = current_app.auth_db.get_gym(gym_id)
    if not gym:
        return err("Gym not found.", 404)
    return jsonify({"gym": gym})


@gyms_bp.route("/<int:gym_id>", methods=["PUT"])
@roles_required("coach", "admin")
@subscription_required
def update_gym(gym_id):
    data = request.get_json(silent=True) or {}
    try:
        gym = current_app.auth_db.update_gym(
            gym_id=gym_id,
            coach_id=current_user()["id"],
            name=data.get("name"),
            location=data.get("location"),
            county=data.get("county"),
        )
        return jsonify({"gym": gym})
    except ValueError as e:
        return err(str(e), 403)


@gyms_bp.route("/<int:gym_id>", methods=["DELETE"])
@roles_required("coach", "admin")
@subscription_required
def delete_gym(gym_id):
    try:
        current_app.auth_db.delete_gym(gym_id, current_user()["id"])
        return jsonify({"message": "Gym deleted successfully."})
    except ValueError as e:
        return err(str(e), 403)


@gyms_bp.route("/<int:gym_id>/fighters", methods=["GET"])
@login_required
def gym_fighters(gym_id):
    gym = current_app.auth_db.get_gym(gym_id)
    if not gym:
        return err("Gym not found.", 404)
    from ..services.matchmaker import elo_band
    viewer  = current_user()
    results = []
    from .fighters import TOP_RANKS_SHOWN
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            fighters = db.get_fighters_by_gym(gym_id)
            if fighters:
                elo_ratings = db.elo_pool()
                # Rank is a position within the discipline, not within the gym,
                # so it comes from the whole sport's pool.
                ranked = sorted(db.get_all_fighters(),
                                key=lambda f: elo_ratings.get(f["id"], 0.0), reverse=True)
                top_ranks = {f["id"]: i + 1
                             for i, f in enumerate(ranked[:TOP_RANKS_SHOWN])}
                sport_results = [
                    {**f, "sport": sport,
                     "elo": elo_ratings.get(f["id"], 0.0),
                     "elo_band": elo_band(elo_ratings.get(f["id"], 0.0))}
                    for f in fighters
                ]
                shown = _apply_privacy(sport_results, sport, viewer)
                for f in shown:
                    if not f.get("record_hidden") and top_ranks.get(f["id"]):
                        f["rank"] = top_ranks[f["id"]]
                results.extend(shown)
    return jsonify({"gym": gym, "fighters": results})


@gyms_bp.route("/<int:gym_id>/candidates", methods=["GET"])
@roles_required("coach", "admin")
# A GET, but a recruiting tool: its only purpose is the assignment that follows
# it, and it scans all four disciplines to produce the list. Gated with the
# write it serves rather than with the reads.
@subscription_required
def gym_candidates(gym_id):
    """Fighters this gym could take on, across every discipline.

    Only fighters with no gym are offered. Moving someone who already trains
    elsewhere is a transfer, not an add, and silently reassigning them from
    another coach's roster is not something a search box should do quietly —
    so those are filtered out rather than shown greyed-out and clickable.
    """
    try:
        current_app.auth_db._assert_gym_owner(gym_id, current_user()["id"])
    except ValueError as e:
        return err(str(e), 403)

    q = request.args.get("q", "").strip()
    results = []
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            fighters = db.search_fighters(q) if q else db.get_all_fighters()
        results.extend(
            {**f, "sport": sport} for f in fighters if not f.get("gym_id")
        )
    results.sort(key=lambda f: f["name"].lower())
    # Enough to pick from without shipping the whole table to the browser.
    return jsonify({"fighters": results[:50], "query": q})


@gyms_bp.route("/<int:gym_id>/fighters/<int:fighter_id>", methods=["POST"])
@roles_required("coach", "admin")
@subscription_required
def assign_fighter_to_gym(gym_id, fighter_id):
    try:
        current_app.auth_db._assert_gym_owner(gym_id, current_user()["id"])
    except ValueError as e:
        return err(str(e), 403)
    sport = request.args.get("sport")
    if sport not in VALID_SPORTS:
        return err("Provide a valid ?sport= parameter.")
    user = current_user()
    try:
        with get_db(sport) as db:
            fighter = db.get_fighter(fighter_id)
            if not fighter:
                return err(f"Fighter {fighter_id} not found.", 404)
            # Owning a gym is authority over that gym, not over every fighter.
            # Without this a coach could pull a rival's roster across one
            # fighter at a time, and the losing coach would never be told.
            current_gym = fighter.get("gym_id")
            if current_gym and current_gym != gym_id and user["role"] != "admin":
                return err(
                    "That fighter already trains at another gym. Their current "
                    "coach must remove them before you can add them.", 403)
            db.assign_gym(fighter_id, gym_id)
        return jsonify({"assigned": fighter_id, "gym_id": gym_id})
    except ValueError as e:
        return err(str(e), 404)


@gyms_bp.route("/<int:gym_id>/fighters/<int:fighter_id>", methods=["DELETE"])
@roles_required("coach", "admin")
@subscription_required
def remove_fighter_from_gym(gym_id, fighter_id):
    try:
        current_app.auth_db._assert_gym_owner(gym_id, current_user()["id"])
    except ValueError as e:
        return err(str(e), 403)
    sport = request.args.get("sport")
    if sport not in VALID_SPORTS:
        return err("Provide a valid ?sport= parameter.")
    try:
        with get_db(sport) as db:
            db.assign_gym(fighter_id, None)
        return jsonify({"removed": fighter_id, "gym_id": gym_id})
    except ValueError as e:
        return err(str(e), 404)
