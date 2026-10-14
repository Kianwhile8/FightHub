from flask import Blueprint, jsonify, request, current_app
from ..helpers import (
    VALID_SPORTS, get_db, err, require_json, current_user,
    login_required, roles_required, subscription_required, _coach_owns_fighter, clean_str
)

events_bp = Blueprint("events", __name__, url_prefix="/api/events")


def _event_or_none(event_id):
    from ..models.event import Event
    try:
        return Event.query.get(int(event_id))
    except (TypeError, ValueError):
        return None


def _may_arrange(event, user) -> bool:
    """Who can set the running order.

    The event's creator, or an admin. Events created before `created_by`
    existed have no owner recorded, so any promoter keeps the access they had
    — locking those would strand cards nobody could touch.
    """
    if not user:
        return False
    if user["role"] == "admin":
        return True
    if event is None or event.created_by is None:
        return user["role"] == "promoter"
    return event.created_by == user["id"]


def _card_order(bouts: list) -> list:
    """Main event first, then down the card; unarranged bouts keep their
    creation order behind anything already placed."""
    return sorted(
        bouts,
        key=lambda b: (b.get("order_index") is None,
                       b.get("order_index", 0) or 0,
                       b.get("id", 0)),
    )


@events_bp.route("/<event_id>/bouts", methods=["GET"])
@login_required
def get_event_bouts(event_id):
    bouts = []
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            bouts.extend(db.get_bouts_for_events(event_id))
    bouts = _card_order(bouts)
    event = _event_or_none(event_id)
    return jsonify({
        "event_id":    event_id,
        "bouts":       bouts,
        "max_bouts":   event.max_bouts if event else None,
        "can_arrange": _may_arrange(event, current_user()),
    })


@events_bp.route("/<event_id>/bouts/order", methods=["PUT"])
@roles_required("promoter", "admin")
@subscription_required
def set_bout_order(event_id):
    """Store the running order as a list of bout ids, main event first."""
    event = _event_or_none(event_id)
    if not _may_arrange(event, current_user()):
        return err("Only the promoter who created this event can arrange its card.", 403)

    data = request.get_json(silent=True) or {}
    order = data.get("order")
    if not isinstance(order, list) or not order:
        return err("Send the running order as a list of bout ids.")

    from ..models.event import EventBout
    from ..extensions import db as _db
    bouts = EventBout.query.filter_by(event_id=str(event_id)).all()
    by_id = {b.id: b for b in bouts}

    try:
        ids = [int(i) for i in order]
    except (TypeError, ValueError):
        return err("Bout ids must be whole numbers.")

    # Refuse a partial or foreign list outright: applying it would silently
    # leave some bouts unordered and scramble the card rather than reorder it.
    if set(ids) != set(by_id) or len(ids) != len(by_id):
        return err("The running order must list every bout on this card exactly once.")

    for position, bout_id in enumerate(ids):
        by_id[bout_id].order_index = position
    _db.session.commit()

    return jsonify({"event_id": event_id,
                    "bouts": _card_order([b.to_dict() for b in bouts])})


@events_bp.route("/<event_id>/bouts", methods=["POST"])
@roles_required("coach", "promoter", "admin")
@subscription_required
def add_event_bout(event_id):
    data, error = require_json("sport", "fighter_a_id", "fighter_b_id")
    if error:
        return error
    sport = data["sport"]
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport: {sport}")
    user     = current_user()
    fighter_a = int(data["fighter_a_id"])
    fighter_b = int(data["fighter_b_id"])
    if fighter_a == fighter_b:
        return err("A fighter cannot fight themselves.")
    if user["role"] == "coach":
        owns_a = _coach_owns_fighter(sport, fighter_a, user)
        owns_b = _coach_owns_fighter(sport, fighter_b, user)
        if not owns_a and not owns_b:
            return err("At least one fighter must be from your gym.", 403)
        with get_db(sport) as db_chk:
            regs = db_chk.get_event_registrations(event_id)
        reg_ids = {r["fighter"]["id"] for r in regs}
        if not owns_a and fighter_a not in reg_ids:
            return err("Fighter A is not in your gym and is not registered for this event.", 403)
        if not owns_b and fighter_b not in reg_ids:
            return err("Fighter B is not in your gym and is not registered for this event.", 403)
    event = _event_or_none(event_id)
    if event is not None and event.max_bouts:
        from ..models.event import EventBout
        current = EventBout.query.filter_by(event_id=str(event_id)).count()
        if current >= event.max_bouts:
            return err(f"This card is full — {event.max_bouts} of "
                       f"{event.max_bouts} bouts. Remove one before adding another.")

    # Column widths: event_bouts.description is Text, ruleset String(50).
    description = clean_str(data.get("description"), max_len=2000,
                            field="Description")
    ruleset     = clean_str(data.get("ruleset"), max_len=50, field="Ruleset")
    try:
        with get_db(sport) as db:
            bout = db.add_bout(event_id, fighter_a, fighter_b,
                               description=description, ruleset=ruleset)
        return jsonify({"bout": bout}), 201
    except ValueError as e:
        return err(str(e))


@events_bp.route("/<event_id>/bouts/<int:bout_id>", methods=["DELETE"])
@roles_required("coach", "promoter", "admin")
@subscription_required
def delete_event_bout(event_id, bout_id):
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            try:
                db.delete_bout(bout_id)
                return jsonify({"deleted": bout_id})
            except ValueError:
                continue
    return err("Bout not found.", 404)


@events_bp.route("/<event_id>/bouts/<int:bout_id>/complete", methods=["POST"])
@roles_required("coach", "promoter", "admin")
@subscription_required
def complete_event_bout(event_id, bout_id):
    """Check a bout off as complete. The result lands in both fighters' histories,
    attributed to this event."""
    data, error = require_json("result")
    if error:
        return error
    with get_db(VALID_SPORTS[0]) as probe:   # get_bout is not sport-scoped
        bout = probe.get_bout(bout_id)
    if not bout or bout["event_id"] != str(event_id):
        return err("Bout not found.", 404)
    sport = bout["sport"]
    user  = current_user()
    if user["role"] == "coach":
        fighter_ids = [f["id"] for f in (bout["fighter_a"], bout["fighter_b"]) if f]
        if not any(_coach_owns_fighter(sport, fid, user) for fid in fighter_ids):
            return err("At least one fighter must be from your gym.", 403)
    try:
        with get_db(sport) as db:
            updated = db.complete_bout(
                bout_id,
                result=str(data["result"]),
                method=str(data.get("method") or "Decision"),
                fight_date=data.get("date") or None,
            )
        return jsonify({"bout": updated})
    except ValueError as e:
        return err(str(e))


@events_bp.route("/<event_id>/register", methods=["POST"])
@roles_required("coach", "promoter", "admin")
@subscription_required
def register_fighter_for_event(event_id):
    data, error = require_json("sport", "fighter_id")
    if error:
        return error
    sport = data["sport"]
    if sport not in VALID_SPORTS:
        return err(f"Unknown sport: {sport}")
    fighter_id = int(data["fighter_id"])
    user = current_user()
    if user["role"] == "coach" and not _coach_owns_fighter(sport, fighter_id, user):
        return err("This fighter is not in your gym.", 403)
    try:
        with get_db(sport) as db:
            reg = db.register_fighter_for_event(event_id, fighter_id)
        return jsonify({"registration": reg}), 201
    except ValueError as e:
        return err(str(e))


@events_bp.route("/<event_id>/registrations", methods=["GET"])
@login_required
def get_event_registrations(event_id):
    registrations = []
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            registrations.extend(db.get_event_registrations(event_id))
    return jsonify({"event_id": event_id, "registrations": registrations})


@events_bp.route("/<event_id>/registrations/<int:reg_id>", methods=["DELETE"])
@roles_required("coach", "promoter", "admin")
@subscription_required
def delete_event_registration(event_id, reg_id):
    user = current_user()
    for sport in VALID_SPORTS:
        with get_db(sport) as db:
            reg = db.get_registration(reg_id)
            if reg and reg["event_id"] == str(event_id):
                if user["role"] == "coach" and not _coach_owns_fighter(sport, reg["fighter"]["id"], user):
                    return err("You don't have permission to remove this registration.", 403)
                try:
                    db.remove_registration(reg_id)
                    return jsonify({"deleted": reg_id})
                except ValueError:
                    continue
    return err("Registration not found.", 404)
