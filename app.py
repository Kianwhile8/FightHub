""" Main application file 
run :
pip install flask flask-cors
python app.py

base URL: http://localhost:5000
all responses are json errors reutnr with appropriate status code
"""
 




from flask import Flask, jsonify, request, send_from_directory, session
from fighter_database import FighterDB
from auth import authDB
import os
import functools



app = Flask(__name__, static_folder="frontend", static_url_path="")
app.secret_key = os.environ.get("FIGHTHUB_SECRET", "ABC123")


DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)

VALID_SPORTS = ("kickboxing", "mma", "boxing")


#isngle shared authdb insatnce
auth_db = authDB(db_dir=DB_DIR)



# addition of helpers



def _mask_record(fighter: dict) -> dict:
    return {**fighter, "wins": None, "losses": None, "draws": None, "record_hidden": True}

def _apply_privacy(fighters: list, sport: str, viewer: dict | None) -> list:
    hidden = auth_db.get_hidden_fighter_ids(sport)
    if not hidden:
        return fighters
    is_admin = viewer and viewer["role"] == "admin"
    own_id = viewer["fighter_id"] if viewer else None
    own_sport = viewer["fighter_sport"] if viewer else None
    return [
        f if (is_admin or (own_id == f["id"] and own_sport == sport) or f["id"] not in hidden)
        else _mask_record(f)
        for f in fighters
    ]

def _coach_owns_fighter(sport:str,fighter_id:int, user:dict) -> bool:

    """Check if a coach owns a specific fighter. returns true if the user 
    is the coach of the gym who the fighter belongs to."""

    if user["role"] == "admin":
        return True
    with get_db(sport) as db:
        fighter = db.get_fighter(fighter_id)
    if not fighter or not fighter.get("gym_id"):
        # unassigned fighters can only be managed by admin
        return False
    gym = auth_db.get_gym (fighter["gym_id"])
    return gym is not None and gym["coach_id"] == user["id"]

def get_db(sport: str) -> FighterDB:
    return FighterDB(sport, db_dir=DB_DIR)

def err(msg: str, status: int = 400):
    return jsonify({"error": msg}), status

def require_json(*fields):
    data = request.get_json(silent=True) or {}
    missing = [f for f in fields if f not in data or data[f] in ("", None)]
    if missing:
        return None, err(f"Missing required fields: {', '.join(missing)}")
    return data, None

def current_user() -> dict |None:
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return None
    return auth_db.get_by_id(uid)

# adding auth decorators

def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return err("Login required", 401)
        return f(*args, **kwargs)
    return wrapper



def roles_required(*roles):
    '''restricts endpoints to certain roles'''
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return err("Login required.", 401)
            if user["role"] not in roles:
                return err (f" Access denied. Required roles: {'or '.join(roles)}", 403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

    

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")



'''creating auth endpoints'''

@app.route("/api/auth/register", methods = ["POST"])
def register():
    data,error = require_json ("email", "password", "role")
    if error:
        return error
    try:
        user = auth_db.register(
            email = data["email"],
            password = data["password"],
            role = data["role"]
        )
        if data["role"] == "fighter" and data.get("fighter_id") and data.get("fighter_sport"):
            user = auth_db.link_fighter(user["id"], int(data["fighter_id"]), data ["fighter_sport"])

        session ["user_id"] = user["id"]
        return jsonify ({"user": user}), 201
    except ValueError as e:
        return err(str(e))
    

@app.route("/api/auth/login", methods=["POST"])
def login():
    data, error = require_json("email", "password")
    if error:
        return error
    try:
        user = auth_db.login(data["email"], data["password"])
        session["user_id"] = user["id"]
        if user["role"] == "fighter" and user["fighter_id"] and user["fighter_sport"]:
            try:
                with get_db(user["fighter_sport"]) as db:
                    user["fighter_record"] = db.get_fighter(user["fighter_id"])
            except Exception:
                user["fighter_record"] = None
        return jsonify({"user": user})
    except ValueError as e:
        return err(str(e), 401)


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify ({"message": "logged out."})



@app.route("/api/auth/me", methods=["GET"])
def me():
    '''returns logged in user. used by frontend page load.'''
    user = current_user()
    if not user:
        return err(" not logged in.", 401)
    if user ["role"] == "fighter" and user ["fighter_id"] and user["fighter_sport"]:
        try:
            with get_db(user["fighter_sport"]) as db:
                user["fighter_record"] = db.get_fighter(user["fighter_id"])
        except Exception:
            user ["fighter_record"] = None
    return jsonify ({"user": user})
    

@app.route ("/api/auth/link-fighter", methods=["POST"])
@login_required
def link_fighter():

    '''allows figthters to link accounts to database records'''

    user = current_user()
    if user ["role"] != "fighter":
        return err("Only fighters can link their accounts.", 403)
    data, error = require_json ("fighter_id", "fighter_sport")
    if error:
        return error
    try:
        updated = auth_db.link_fighter(user["id"], int(data["fighter_id"]), data["fighter_sport"])
        return jsonify ({"user": updated})
    except ValueError as e:
        return err(str(e))
    

@app.route("/api/auth/privacy", methods=["PUT"])
@login_required
def update_privacy():
    data = request.get_json(silent=True) or {}
    hide = bool(data.get("hide_record", False))
    try:
        updated = auth_db.update_privacy(current_user()["id"], hide)
        return jsonify({"user": updated})
    except ValueError as e:
        return err(str(e))


@app.route("/api/auth/change-password", methods=["POST"])
@login_required
def change_password():
    data, error = require_json ("old_password", "new_password")
    if error:
        return error
    try:
        auth_db.change_password(current_user()["id"], data["old_password"], data["new_password"])
        return jsonify({"message": "Password changed successfully."})
    except ValueError as e:
        return err(str(e))
    


'''adding admin endpoints'''

@app.route("/api/admin/users", methods=["GET"])
@roles_required("admin")
def list_users():
    return jsonify ({"users": auth_db.get_all_users()})

@app.route("/api/admin/users/<int:user_id>/role", methods=["PUT"])
@roles_required ("admin")
def admin_update_role(user_id):
    data = request.get_json(silent=True) or {}
    if "role" not in data:
        return err("missing field: role")
    try:
        updated = auth_db.update_role(user_id, data["role"])
        return jsonify ({"user": updated})
    except  ValueError as e:
        return err(str(e))
    

@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@roles_required ("admin")
def admin_delete_user(user_id):
    if user_id == current_user ()["id"]:
        return err("cannot delete your own account")
    try:
        auth_db.delete_user(user_id)
        return jsonify({"deleted": user_id})
    except ValueError as e:
        return err(str(e)), 404


'''creating fighter endpoints, must be logged in '''


@app.route("/api/<sport>/fighters", methods=["GET"])
@login_required
def list_fighters(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    q = request.args.get("q", "").strip()
    with get_db(sport) as db:
        fighters = db.search_fighters(q) if q else db.get_all_fighters()
    fighters = _apply_privacy(fighters, sport, current_user())
    return jsonify({"sport": sport, "fighters": fighters})


@app.route("/api/<sport>/fighters/<int:fighter_id>", methods=["GET"])
@login_required
def get_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    with get_db(sport) as db:
        fighter = db.get_fighter(fighter_id)
    if not fighter:
        return err("Fighter not found", 404)
    [fighter] = _apply_privacy([fighter], sport, current_user())
    return jsonify(fighter)


@app.route("/api/<sport>/fighters", methods=["POST"])
@roles_required ("coach", "admin")
def add_fighter(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    data, error = require_json("name", "age", "weight")
    if error:
        return error
    try:
        with get_db(sport) as db:
            fid = db.add_fighter(
                name=str(data["name"]).strip(),
                age=int(data["age"]),
                weight=float(data["weight"]),
            )
            fighter = db.get_fighter(fid)
        return jsonify(fighter), 201
    except (ValueError, Exception) as e:
        return err(str(e))


@app.route("/api/<sport>/fighters/<int:fighter_id>", methods=["PUT"])
@roles_required ("coach", "admin")
def update_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("You can only edit fighters in your own gym", 403)
    data = request.get_json(silent=True) or {}
    try:
        with get_db(sport) as db:
            db.update_fighter(
                fighter_id,
                name=data.get("name"),
                age=int(data["age"]) if "age" in data else None,
                weight=float(data["weight"]) if "weight" in data else None,
            )
            fighter = db.get_fighter(fighter_id)
        return jsonify(fighter)
    except ValueError as e:
        return err(str(e), 404)


@app.route("/api/<sport>/fighters/<int:fighter_id>", methods=["DELETE"])
@roles_required ("coach", "admin")
def delete_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("You can only delete fighters in your own gym", 403)
    try:
        with get_db(sport) as db:
            db.delete_fighter(fighter_id)
        return jsonify({"deleted": fighter_id})
    except ValueError as e:
        return err(str(e), 404)



'''creating fight history'''

@app.route("/api/<sport>/fighters/<int:fighter_id>/fights", methods=["GET"])
@login_required
def get_fighter_fights(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    viewer = current_user()
    hidden = auth_db.get_hidden_fighter_ids(sport)
    is_admin = viewer and viewer["role"] == "admin"
    is_own = viewer and viewer["fighter_id"] == fighter_id and viewer["fighter_sport"] == sport
    if fighter_id in hidden and not is_admin and not is_own:
        return jsonify({"fighter_id": fighter_id, "fights": [], "record_hidden": True})
    with get_db(sport) as db:
        history = db.get_fight_history(fighter_id)
    return jsonify({"fighter_id": fighter_id, "fights": history})


@app.route("/api/<sport>/fighters/<int:fighter_id>/fights", methods=["POST"])
@roles_required ("coach", "promoter", "admin")
def add_fight(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    user = current_user()
    if user["role"] != "admin":
        with get_db(sport) as db:
            chk = db.get_fighter(fighter_id)
        if not chk:
            return err("Fighter not found", 404)
        if not chk.get("gym_id"):
            return err("Only admins can log fights for unassigned fighters", 403)
        if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
            return err("You can only log fights for fighters in your own gym", 403)
    data, error = require_json("opponent_name", "result")
    if error:
        return error
    try:
        with get_db(sport) as db:
            fight_id = db.add_fight(
                fighter_id=fighter_id,
                opponent_name=str(data["opponent_name"]).strip(),
                result=str(data["result"]).upper(),
                method=str(data.get("method", "Decision")),
                fight_date=data.get("date"),
            )
            fighter = db.get_fighter(fighter_id)
        return jsonify({"fight_id": fight_id, "updated_record": fighter}), 201
    except ValueError as e:
        return err(str(e))


@app.route("/api/<sport>/fights", methods=["GET"])
@login_required
def get_all_fights(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    viewer = current_user()
    with get_db(sport) as db:
        fights = db.get_all_fights()
    if viewer["role"] != "admin":
        hidden = auth_db.get_hidden_fighter_ids(sport)
        own_id = viewer["fighter_id"] if viewer["fighter_sport"] == sport else None
        fights = [f for f in fights if f["fighter_id"] not in hidden or f["fighter_id"] == own_id]
    return jsonify({"sport": sport, "fights": fights})


'''function to create matches'''

@app.route("/api/<sport>/fighters/<int:fighter_id>/matches", methods=["GET"])
def get_matches(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    try:
        with get_db(sport) as db:
            matches = db.get_matches(fighter_id)
        return jsonify({"fighter_id": fighter_id, "matches": matches})
    except ValueError as e:
        return err(str(e), 404)
    
    '''adding elo stats'''

@app.route("/api/<sport>/rankings", methods=["GET"])
def get_rankings(sport):
    '''returns all fighters in a sport sorted by elo rating starting from the highest'''
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    try:
        from matchmaker import compute_elo_for_pool, elo_band
        with get_db(sport) as db:
            fighters = db.get_all_fighters()
            histories = {f["id"]: db.get_fight_history(f["id"]) for f in fighters}

            if not fighters:
                return jsonify({"sport": sport, "rankings": []})

            elo_ratings = compute_elo_for_pool(fighters, histories)
            ranked = sorted(
                [{**f, "elo": elo_ratings[f["id"]], "elo_band": elo_band(elo_ratings[f["id"]])} for f in fighters],
                    key=lambda x: x["elo"], reverse=True
            )
            ranked = _apply_privacy(ranked, sport, current_user())

            #positional number
            for i, f in enumerate(ranked):
                f["rank"] = i + 1

            return jsonify({"sport": sport, "rankings": ranked})
    except Exception as e:
        return err (str(e))

'''function to validate statistics'''

@app.route("/api/stats", methods=["GET"])
def stats():
    totals = {}
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            totals[sport] = len(db.get_all_fighters())
    totals["total"] = sum(totals.values())
    return jsonify(totals)



'''gym endpoints'''


@app.route("/api/gyms", methods=["GET"])
@login_required
def list_gyms():
    '''lists all gyms. coaches only see their gym, amdins can see all'''
    user = current_user()
    if user["role"] == "admin":
        gyms = auth_db.get_all_gyms()
    elif user["role"] == "coach":
        gyms = auth_db.get_all_gyms_by_coach(user["id"])
    else:
        gyms = auth_db.get_all_gyms()
    return jsonify({"gyms": gyms})

@app.route("/api/gyms", methods=["POST"])
@roles_required("coach", "admin")
def create_gym():
    data,error = require_json("name")
    if error:
        return error
    try:
        gym = auth_db.create_gym(
            name=data["name"],
            coach_id=current_user()["id"],
            location=data.get("location","")
        )
        return jsonify({"gym": gym}),201
    except ValueError as e:
        return err(str(e))
    
@app.route("/api/gyms/<int:gym_id>", methods=["GET"])
@login_required
def get_gym(gym_id):
    gym = auth_db.get_gym(gym_id)
    if not gym:
        return err("Gym not found", 404)
    return jsonify({"gym": gym})

@app.route("/api/gyms/<int:gym_id>",methods=["PUT"])
@roles_required("coach", "admin")
def update_gym(gym_id):
    data = request.get_json(silent=True) or {}
    try:
        gym = auth_db.update_gym(
            gym_id=gym_id,
            coach_id=current_user()["id"],
            name=data.get("name"),
            location=data.get("location"),
        )
        return jsonify({"gym": gym})
    except ValueError as e:
        return err(str(e), 403)

@app.route("/api/gyms/<int:gym_id>", methods=["DELETE"])
@roles_required("coach", "admin")
def delete_gym(gym_id):
    try:
        auth_db.delete_gym(gym_id, current_user()["id"])
        return jsonify({"message": "Gym deleted successfully"})
    except ValueError as e:
        return err(str(e), 403)
    

@app.route("/api/gyms/<int:gym_id>/fighters", methods=["GET"])
@login_required
def gym_fighters(gym_id):
    '''returns all figh5ters in a gym accross all sports'''

    gym = auth_db.get_gym(gym_id)
    if not gym:
        return err("gym not found", 404)
    from matchmaker import compute_elo_for_pool, elo_band
    viewer = current_user()
    results = []
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            fighters = db.get_fighters_by_gym(gym_id)
            if fighters:
                all_fighters = db.get_all_fighters()
                all_histories = {f["id"]: db.get_fight_history(f["id"]) for f in all_fighters}
                elo_ratings = compute_elo_for_pool(all_fighters, all_histories)
                sport_results = [
                    {**f, "sport": sport, "elo": elo_ratings.get(f["id"], 0.0), "elo_band": elo_band(elo_ratings.get(f["id"], 0.0))}
                    for f in fighters
                ]
                results.extend(_apply_privacy(sport_results, sport, viewer))
    return jsonify({"gym": gym, "fighters": results})

@app.route("/api/gyms/<int:gym_id>/fighters/<int:fighter_id>", methods=["POST"])
@roles_required("coach", "admin")
def assign_fighter_to_gym(gym_id, fighter_id):
    '''assings a fighter to a gym. a coach must own the gym'''
    try:
        auth_db._assert_gym_owner(gym_id, current_user()["id"])
    except ValueError as e:
        return err(str(e), 403)
    sport = request.args.get("sport")
    if sport not in VALID_SPORTS:
        return err(f"please provide a valid ?sport= parameter")
    try:
        with get_db(sport) as db:
            db.assign_gym(fighter_id, gym_id)
        return jsonify({"assinged": fighter_id, "gym_id": gym_id})
    except ValueError as e:
        return err(str(e), 404)
    

@app.route("/api/gyms/<int:gym_id>/fighters/<int:fighter_id>", methods=["DELETE"])
@roles_required("coach", "admin")
def remove_fighter_from_gym(gym_id, fighter_id):
    """Remove a fighter from the gym (sets gym_id to null)."""
    try:
        auth_db._assert_gym_owner(gym_id, current_user()["id"])
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
    

# event fight cards

@app.route("/api/events/<event_id>/bouts", methods=["GET"])
@login_required
def get_event_bouts(event_id):
    """reuturns all bouts on a fight card for all sports"""
    bouts = []
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            bouts.extend(db.get_bouts_for_events(event_id))
    return jsonify ({"event_id": event_id, "bouts": bouts})


@app.route ("/api/events/<event_id>/bouts", methods=["POST"])
@roles_required ("coach", "promoter", "admin")
def add_event_bout(event_id):
    """adds bouts to event card. 
    coaches can only add fighterse from their own gym"""
    data, error = require_json("sport", "fighter_a_id", "fighter_b_id")
    if error:
        return error
    sport = data["sport"]
    if sport not in VALID_SPORTS:
        return err(f"unknown sport: {sport}")
    user = current_user()
    fighter_a = int(data["fighter_a_id"])
    fighter_b = int(data["fighter_b_id"])
    if fighter_a == fighter_b:
        return err(" a fighter cannot fight themselves")
    # both fighters must belong to a gym

    if user["role"] == "coach":
        owns_a = _coach_owns_fighter(sport, fighter_a, user)
        owns_b = _coach_owns_fighter(sport, fighter_b, user)
        if not owns_a and not owns_b:
            return err("At least one fighter must be from your gym", 403)
        # unowned fighter must be registered/pending for this event
        with get_db(sport) as db_chk:
            regs = db_chk.get_event_registrations(event_id)
        reg_ids = {r["fighter"]["id"] for r in regs}
        if not owns_a and fighter_a not in reg_ids:
            return err("Fighter A is not in your gym and is not registered for this event", 403)
        if not owns_b and fighter_b not in reg_ids:
            return err("Fighter B is not in your gym and is not registered for this event", 403)
    try:
        with get_db(sport) as db:
            bout = db.add_bout(event_id, fighter_a, fighter_b)
        return jsonify ({"bout": bout}), 201
    except ValueError as e:
        return err(str(e))
    
@app.route("/api/events/<event_id>/bouts/<int:bout_id>", methods=["DELETE"])
@roles_required("coach", "promoter", "admin")
def delete_event_bout(event_id, bout_id):
    """Remove a bout from the fight card."""
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            try:
                db.delete_bout(bout_id)
                return jsonify({"deleted": bout_id})
            except ValueError:
                continue
    return err("Bout not found.", 404)
    


# event fighter registrations (pending fighters awaiting a bout)

@app.route("/api/events/<event_id>/register", methods=["POST"])
@roles_required("coach", "promoter", "admin")
def register_fighter_for_event(event_id):
    """Coach registers one of their fighters as pending/available for a bout at this event."""
    data, error = require_json("sport", "fighter_id")
    if error:
        return error
    sport = data["sport"]
    if sport not in VALID_SPORTS:
        return err(f"unknown sport: {sport}")
    fighter_id = int(data["fighter_id"])
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("This fighter is not in your gym", 403)
    try:
        with get_db(sport) as db:
            reg = db.register_fighter_for_event(event_id, fighter_id)
        return jsonify({"registration": reg}), 201
    except ValueError as e:
        return err(str(e))


@app.route("/api/events/<event_id>/registrations", methods=["GET"])
@login_required
def get_event_registrations(event_id):
    """Returns all pending fighter registrations for an event across all sports."""
    registrations = []
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            registrations.extend(db.get_event_registrations(event_id))
    return jsonify({"event_id": event_id, "registrations": registrations})


@app.route("/api/events/<event_id>/registrations/<int:reg_id>", methods=["DELETE"])
@roles_required("coach", "promoter", "admin")
def delete_event_registration(event_id, reg_id):
    """Remove a fighter's pending registration. Coaches can only remove their own fighters."""
    user = current_user()
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            reg = db.get_registration(reg_id)
            if reg and reg["event_id"] == str(event_id):
                if user["role"] == "coach" and not _coach_owns_fighter(sport, reg["fighter"]["id"], user):
                    return err("You don't have permission to remove this registration", 403)
                try:
                    db.remove_registration(reg_id)
                    return jsonify({"deleted": reg_id})
                except ValueError:
                    continue
    return err("Registration not found.", 404)


if __name__ == "__main__":
    app.run(debug=True, port=5000)