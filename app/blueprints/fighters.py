from flask import Blueprint, jsonify, request, current_app
from ..helpers import (
    VALID_SPORTS, get_db, err, require_json, current_user,
    login_required, roles_required, subscription_required, _apply_privacy, _coach_owns_fighter,
    _mask_record, owns_profile, clean_str
)
from ..services.fighter_service import FighterService
from ..validation import clean_int

fighters_bp = Blueprint("fighters", __name__, url_prefix="/api")

# How far down the rankings a fighter card still shows its position.
TOP_RANKS_SHOWN = 10


@fighters_bp.route("/<sport>/fighters", methods=["GET"])
@login_required
def list_fighters(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    q      = request.args.get("q", "").strip()
    county = request.args.get("county", "").strip() or None
    raw_max = request.args.get("max_weight", "").strip()
    try:
        max_weight = float(raw_max) if raw_max else None
    except ValueError:
        return err("max_weight must be a number of kilograms.")
    if max_weight is not None and max_weight <= 0:
        return err("max_weight must be greater than zero.")
    gender = request.args.get("gender", "").strip().lower() or None
    if gender is not None and gender not in FighterService.VALID_GENDERS:
        return err("gender must be 'male' or 'female'.")

    with get_db(sport) as db:
        fighters = (db.search_fighters(q, county, max_weight, gender) if q
                    else db.get_all_fighters(county, max_weight, gender))
        # Rank is a standing within the whole discipline, so it is computed
        # from every fighter in the sport and then attached to whatever subset
        # the filters returned. Ranking the filtered set instead would make
        # "#1" mean "first among fighters in Kent", which is not what the badge
        # claims and would change as the user typed in the search box.
        elo_ratings = db.elo_pool()
        everyone    = db.get_all_fighters()

    ranked = sorted(everyone, key=lambda f: elo_ratings.get(f["id"], 0.0), reverse=True)
    # Only the top of the table is worth surfacing on a card: "#247" tells a
    # reader nothing, and the badge stops meaning anything if everyone has one.
    top_ranks = {f["id"]: i + 1 for i, f in enumerate(ranked[:TOP_RANKS_SHOWN])}

    fighters = _apply_privacy(fighters, sport, current_user())
    for f in fighters:
        # A fighter who hid their record hid their standing with it — a rank is
        # derived from exactly the results they chose not to publish.
        if f.get("record_hidden"):
            continue
        rank = top_ranks.get(f["id"])
        if rank:
            f["rank"] = rank
    return jsonify({"sport": sport, "fighters": fighters})


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>", methods=["GET"])
@login_required
def get_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    with get_db(sport) as db:
        fighter = db.get_fighter(fighter_id)
    if not fighter:
        return err("Fighter not found.", 404)
    [fighter] = _apply_privacy([fighter], sport, current_user())
    try:
        from ..services.matchmaker import elo_band
        with get_db(sport) as db2:
            elo_ratings = db2.elo_pool()
            fighter["prior_experience"] = db2.list_prior_experience(fighter_id)
        fighter["elo"]      = elo_ratings.get(fighter_id, 0)
        fighter["elo_band"] = elo_band(fighter["elo"])
    except Exception:
        fighter["elo"]      = 0
        fighter["elo_band"] = "Amateur"
    return jsonify(fighter)


@fighters_bp.route("/<sport>/fighters", methods=["POST"])
@roles_required("coach", "admin")
@subscription_required
def add_fighter(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    data, error = require_json("name", "weight")
    if error:
        return error

    # Placing the fighter in a gym at creation matters more than it looks:
    # _coach_owns_fighter() derives a coach's authority over a fighter from the
    # gym, so a fighter created with no gym is one the creating coach cannot
    # subsequently edit or delete.
    gym_id = data.get("gym_id")
    if gym_id is not None:
        try:
            gym_id = int(gym_id)
            current_app.auth_db._assert_gym_owner(gym_id, current_user()["id"])
        except (TypeError, ValueError) as e:
            return err(str(e) if isinstance(e, ValueError) else "Invalid gym_id.", 403)

    try:
        from datetime import date
        raw_dob = data.get("date_of_birth")
        dob = date.fromisoformat(raw_dob) if raw_dob else None
        with get_db(sport) as db:
            fid = db.add_fighter(
                name=str(data["name"]).strip(),
                date_of_birth=dob,
                weight=float(data["weight"]),
                description=str(data["description"]).strip() if data.get("description") else None,
                county=data.get("county") or None,
                gender=clean_str(data.get("gender")),
            )
            if gym_id is not None:
                db.assign_gym(fid, gym_id)
            fighter = db.get_fighter(fid)
        return jsonify(fighter), 201
    except (ValueError, Exception) as e:
        return err(str(e))


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>", methods=["PUT"])
@roles_required("coach", "admin")
@subscription_required
def update_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("You can only edit fighters in your own gym.", 403)
    data = request.get_json(silent=True) or {}
    try:
        from datetime import date
        updates = {}
        if "name"          in data: updates["name"]          = str(data["name"]).strip()
        if "weight"        in data: updates["weight"]        = float(data["weight"])
        if "description"   in data: updates["description"]   = str(data["description"]).strip() if data["description"] else None
        if "gender"        in data: updates["gender"]        = clean_str(data["gender"])
        if "county"        in data: updates["county"]        = data["county"] or None
        if "date_of_birth" in data:
            raw = data["date_of_birth"]
            updates["date_of_birth"] = date.fromisoformat(raw) if raw else None
        with get_db(sport) as db:
            db.update_fighter(fighter_id, **updates)
            fighter = db.get_fighter(fighter_id)
        return jsonify(fighter)
    except ValueError as e:
        return err(str(e), 404)


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>", methods=["DELETE"])
@roles_required("coach", "admin")
@subscription_required
def delete_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("You can only delete fighters in your own gym.", 403)
    try:
        with get_db(sport) as db:
            db.delete_fighter(fighter_id)
        return jsonify({"deleted": fighter_id})
    except ValueError as e:
        return err(str(e), 404)


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>/matches", methods=["GET"])
@login_required
# Gated despite being a GET, which is the one deliberate exception to "reads are
# free". This endpoint is a computation, not a record: it is the only thing here
# producing an answer the user could not reach by reading pages they already
# have. It is also the most expensive handler in the app — it scores every
# fighter in the discipline and recomputes ratings from history. Leaving it open
# would make the whole pitch free and reduce the paid tier to data entry, which
# is work the user does for the platform rather than the other way round.
@subscription_required
def get_fighter_matches(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    viewer = current_user()
    # Opponents whose experience gap makes for a mismatch are held back by
    # default; ?include_ineligible=1 returns them flagged so a promoter can see
    # who was filtered and why.
    show_all = request.args.get("include_ineligible", "").lower() in ("1", "true", "yes")
    try:
        with get_db(sport) as db:
            raw = db.get_matches(fighter_id, include_ineligible=True)
    except ValueError as e:
        return err(str(e), 404)

    hidden = set()
    try:
        from flask import current_app
        hidden = current_app.auth_db.get_hidden_fighter_ids(sport)
    except Exception:
        pass

    is_admin = viewer and viewer["role"] == "admin"
    envelope_keys = ("match_score", "weight_diff", "elo", "elo_band",
                     "effective_bouts", "transferred_bouts",
                     "eligible", "ineligible_reason")

    matches, excluded = [], 0
    for m in raw:
        eligible = m.get("eligible", True)
        if not eligible:
            excluded += 1
            if not show_all:
                continue
        fighter_data = {k: v for k, v in m.items() if k not in envelope_keys}
        if m["id"] in hidden and not is_admin and not owns_profile(viewer, fighter_data, sport):
            fighter_data = _mask_record(fighter_data)
        row = {
            "fighter":           fighter_data,
            "score":             m.get("match_score", 0),
            "elo":               m.get("elo", 0),
            "elo_band":          m.get("elo_band", "Amateur"),
            "weight_diff":       m.get("weight_diff", 0),
            "effective_bouts":   m.get("effective_bouts", 0),
            "transferred_bouts": m.get("transferred_bouts", 0),
        }
        if show_all:
            row["eligible"] = eligible
            if not eligible:
                row["ineligible_reason"] = m.get("ineligible_reason")
        matches.append(row)

    return jsonify({"sport": sport, "fighter_id": fighter_id,
                    "matches": matches, "excluded": excluded})


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>/fights", methods=["GET"])
@login_required
def get_fighter_fights(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    from flask import current_app
    viewer = current_user()
    hidden = current_app.auth_db.get_hidden_fighter_ids(sport)
    is_admin = viewer and viewer["role"] == "admin"
    is_own   = viewer and fighter_id in current_app.auth_db.owned_fighter_ids(viewer["id"])
    if fighter_id in hidden and not is_admin and not is_own:
        return jsonify({"fighter_id": fighter_id, "fights": [], "record_hidden": True})
    with get_db(sport) as db:
        history = db.get_fight_history(fighter_id)
    return jsonify({"fighter_id": fighter_id, "fights": history})


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>/fights", methods=["POST"])
@roles_required("coach", "promoter", "admin")
@subscription_required
def add_fight(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] != "admin":
        with get_db(sport) as db:
            chk = db.get_fighter(fighter_id)
        if not chk:
            return err("Fighter not found.", 404)
        if not chk.get("gym_id"):
            return err("Only admins can log fights for unassigned fighters.", 403)
        if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
            return err("You can only log fights for fighters in your own gym.", 403)
    data, error = require_json("opponent_name", "result")
    if error:
        return error
    try:
        with get_db(sport) as db:
            fight_id = db.add_fight(
                fighter_id=fighter_id,
                # Bounded to the column widths — these were unbounded strings
                # written straight into the record another fighter reads.
                opponent_name=clean_str(data["opponent_name"], max_len=100,
                                        field="Opponent name"),
                result=str(data["result"]).upper(),
                method=clean_str(data.get("method"), "Decision", max_len=50,
                                 field="Method"),
                fight_date=data.get("date"),
                opponent_id=clean_int(data.get("opponent_id"),
                                      field="opponent_id", minimum=1),
                ruleset=clean_str(data.get("ruleset"), max_len=50, field="Ruleset"),
            )
            fighter = db.get_fighter(fighter_id)
        return jsonify({"fight_id": fight_id, "updated_record": fighter}), 201
    except ValueError as e:
        return err(str(e))


@fighters_bp.route("/<sport>/fights", methods=["GET"])
@login_required
def get_all_fights(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    from flask import current_app
    viewer = current_user()
    with get_db(sport) as db:
        fights = db.get_all_fights()
    if viewer["role"] != "admin":
        hidden = current_app.auth_db.get_hidden_fighter_ids(sport)
        own    = current_app.auth_db.owned_fighter_ids(viewer["id"])
        fights = [f for f in fights
                  if f["fighter_id"] not in hidden or f["fighter_id"] in own]
    return jsonify({"sport": sport, "fights": fights})


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>/prior-experience", methods=["GET"])
@login_required
def list_prior_experience(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    with get_db(sport) as db:
        if not db.get_fighter(fighter_id):
            return err("Fighter not found.", 404)
        return jsonify({"fighter_id": fighter_id,
                        "prior_experience": db.list_prior_experience(fighter_id)})


@fighters_bp.route("/<sport>/fighters/<int:fighter_id>/prior-experience", methods=["POST"])
@roles_required("coach", "admin")
@subscription_required
def set_prior_experience(sport, fighter_id):
    """Declare a fighter's record in another discipline.

    This is how experience reaches matchmaking for fighters with no linked
    account — without it they enter a new sport looking like a debutant.
    """
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("You can only edit fighters in your own gym.", 403)
    data, error = require_json("sport")
    if error:
        return error
    try:
        with get_db(sport) as db:
            entry = db.set_prior_experience(
                fighter_id=fighter_id,
                sport=str(data["sport"]).strip().lower(),
                wins=data.get("wins", 0),
                losses=data.get("losses", 0),
                draws=data.get("draws", 0),
                last_bout_date=data.get("last_bout_date") or None,
                note=str(data["note"]).strip() if data.get("note") else None,
            )
        return jsonify(entry), 201
    except (ValueError, TypeError) as e:
        return err(str(e))


@fighters_bp.route(
    "/<sport>/fighters/<int:fighter_id>/prior-experience/<int:entry_id>",
    methods=["DELETE"])
@roles_required("coach", "admin")
@subscription_required
def delete_prior_experience(sport, fighter_id, entry_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("You can only edit fighters in your own gym.", 403)
    try:
        with get_db(sport) as db:
            db.delete_prior_experience(fighter_id, entry_id)
        return jsonify({"deleted": entry_id})
    except ValueError as e:
        return err(str(e), 404)
