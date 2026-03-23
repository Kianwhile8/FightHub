""" Main application file 
run :
pip install flask flask-cors
python app.py

base URL: http://localhost:5000
all responses are json errors reutnr with appropriate status code
"""



from flask import Flask, jsonify, request, send_from_directory
from fighter_database import fighter_database
import os

app = Flask(__name__, static_folder="frontend", static_url_path="")


DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)

VALID_SPORTS = ("kickboxing", "mma", "boxing")


def get_db(sport: str) -> fighter_database:
    return fighter_database(sport, db_dir=DB_DIR)

def err(msg: str, status: int = 400):
    return jsonify({"error": msg}), status

def require_json(*fields):
    data = request.get_json(silent=True) or {}
    missing = [f for f in fields if f not in data or data[f] in ("", None)]
    if missing:
        return None, err(f"Missing required fields: {', '.join(missing)}")
    return data, None


@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


'''creating fighter page'''


@app.route("/api/<sport>/fighters", methods=["GET"])
def list_fighters(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    q = request.args.get("q", "").strip()
    with get_db(sport) as db:
        fighters = db.search_fighters(q) if q else db.get_all_fighters()
    return jsonify({"sport": sport, "fighters": fighters})


@app.route("/api/<sport>/fighters/<int:fighter_id>", methods=["GET"])
def get_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    with get_db(sport) as db:
        fighter = db.get_fighter(fighter_id)
    if not fighter:
        return err("Fighter not found", 404)
    return jsonify(fighter)


@app.route("/api/<sport>/fighters", methods=["POST"])
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
def update_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
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
def delete_fighter(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    try:
        with get_db(sport) as db:
            db.delete_fighter(fighter_id)
        return jsonify({"deleted": fighter_id})
    except ValueError as e:
        return err(str(e), 404)



'''creating fight history'''

@app.route("/api/<sport>/fighters/<int:fighter_id>/fights", methods=["GET"])
def get_fighter_fights(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    with get_db(sport) as db:
        history = db.get_fight_history(fighter_id)
    return jsonify({"fighter_id": fighter_id, "fights": history})


@app.route("/api/<sport>/fighters/<int:fighter_id>/fights", methods=["POST"])
def add_fight(sport, fighter_id):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
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
def get_all_fights(sport):
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport '{sport}'", 404)
    with get_db(sport) as db:
        fights = db.get_all_fights()
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


'''function to validate statistics'''

@app.route("/api/stats", methods=["GET"])
def stats():
    totals = {}
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            totals[sport] = len(db.get_all_fighters())
    totals["total"] = sum(totals.values())
    return jsonify(totals)


if __name__ == "__main__":
    app.run(debug=True, port=5000)