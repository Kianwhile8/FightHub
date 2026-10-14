"""Gym routes, under /api/gyms/...

  GET    ""                                list (?mine=1 for the coach's own)
  POST   ""                                create             (coach, admin)
  GET    /<gym_id>                         one gym
  PUT    /<gym_id>                         edit               (owner, admin)
  DELETE /<gym_id>                         delete             (owner, admin)
  GET    /<gym_id>/fighters                roster, all sports, with Elo and rank
  GET    /<gym_id>/candidates              gymless fighters to recruit (owner, admin)
  POST   /<gym_id>/fighters/<id>?sport=    add a fighter      (owner, admin)
  DELETE /<gym_id>/fighters/<id>?sport=    remove a fighter   (owner, admin)

Ownership is checked by AuthService._assert_gym_owner.
"""

from flask import Blueprint, jsonify, request, current_app
from ..helpers import (
    VALID_SPORTS, get_db, err, require_json, current_user,
    login_required, roles_required, subscription_required, _apply_privacy
)
from ..services.matchmaker import elo_band
from .fighters import TOP_RANKS_SHOWN

gyms_bp = Blueprint("gyms", __name__, url_prefix="/api/gyms")


@gyms_bp.route("", methods=["GET"])
@login_required
def list_gyms():
    """All gyms (optionally ?county=), or only a coach's own with ?mine=1.

    Everyone sees every gym; the client separates "my gyms" itself. ?mine=1 is
    for places that need only the caller's own, like the new-fighter gym picker.
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
    """Create a gym owned by the caller."""
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
    """One gym."""
    gym = current_app.auth_db.get_gym(gym_id)
    if not gym:
        return err("Gym not found.", 404)
    return jsonify({"gym": gym})


@gyms_bp.route("/<int:gym_id>", methods=["PUT"])
@roles_required("coach", "admin")
@subscription_required
def update_gym(gym_id):
    """Edit name / location / county (owner or admin)."""
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
    """Delete a gym (owner or admin). Its fighters become gymless."""
    try:
        current_app.auth_db.delete_gym(gym_id, current_user()["id"])
        return jsonify({"message": "Gym deleted successfully."})
    except ValueError as e:
        return err(str(e), 403)


@gyms_bp.route("/<int:gym_id>/fighters", methods=["GET"])
@login_required
def gym_fighters(gym_id):
    """The gym's roster across every sport, each with Elo, band and rank."""
    gym = current_app.auth_db.get_gym(gym_id)
    if not gym:
        return err("Gym not found.", 404)
    viewer  = current_user()
    results = []
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
@subscription_required
def gym_candidates(gym_id):
    """Fighters this gym could take on, across every sport (max 50, ?q= search).

    Only gymless fighters are offered: taking a fighter from another gym is
    a transfer their current coach must start. Paid-only, like the
    assignment it leads to.
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
    """Add a gymless fighter to this gym."""
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
            # A coach may not take a fighter from another gym.
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
    """Make a fighter gymless."""
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
