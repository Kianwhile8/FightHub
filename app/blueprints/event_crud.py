"""Event and venue routes, under /api/...

  GET    /venues               list
  POST   /venues               create               (promoter, admin)
  GET    /events               list, newest first
  POST   /events               create (optionally with a new venue inline)
  GET    /events/<id>          one event
  PUT    /events/<id>          edit                 (promoter, admin)
  DELETE /events/<id>          delete               (promoter, admin)

The fight card for an event is in events.py.
"""

from datetime import datetime
from flask import Blueprint, jsonify, request
from ..extensions import db
from ..models.event import Event, EventBout, Venue
from ..helpers import (err, require_json, login_required, roles_required, subscription_required,
                       clean_str, current_user)
from ..validation import clean_int, clean_text_block

# Allowed range for an event's max_bouts.
MIN_BOUTS, MAX_BOUTS = 5, 20

# Match the column widths, so an over-long value is refused with a readable
# message rather than raising a DataError from the driver.
MAX_EVENT_NAME = 150
MAX_EVENT_DESCRIPTION = 5000
MAX_VENUE_NAME, MAX_VENUE_ADDRESS, MAX_VENUE_CITY = 100, 200, 100


def parse_max_bouts(value):
    """Validate the card size. Returns (value, error_message)."""
    if value in (None, ""):
        return None, None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None, "Maximum bouts must be a whole number."
    if not MIN_BOUTS <= n <= MAX_BOUTS:
        return None, f"Maximum bouts must be between {MIN_BOUTS} and {MAX_BOUTS}."
    return n, None


event_crud_bp = Blueprint("event_crud", __name__, url_prefix="/api")


# ── Venues ────────────────────────────────────────────────────────────────────

@event_crud_bp.route("/venues", methods=["GET"])
@login_required
def list_venues():
    """All venues, by name."""
    venues = Venue.query.order_by(Venue.name).all()
    return jsonify({"venues": [v.to_dict() for v in venues]})


def _build_venue(data: dict) -> Venue:
    """Create a Venue from a {name, address, city, capacity} dict.

    Shared by the venues endpoint and inline creation during event creation, so
    the two cannot validate differently.
    """
    name = clean_str(data.get("name"), max_len=MAX_VENUE_NAME, field="Venue name")
    if not name:
        raise ValueError("A venue needs a name.")
    # The largest stadium holds ~114,000, so anything past 200,000 is a typo.
    capacity = clean_int(data.get("capacity"), field="Capacity",
                         minimum=1, maximum=200_000)
    return Venue(
        name=name,
        address=clean_str(data.get("address"), max_len=MAX_VENUE_ADDRESS,
                          field="Address"),
        city=clean_str(data.get("city"), max_len=MAX_VENUE_CITY, field="City"),
        capacity=capacity,
    )


@event_crud_bp.route("/venues", methods=["POST"])
@roles_required("promoter", "admin")
@subscription_required
def create_venue():
    """Add a venue (promoters and admins)."""
    data, error = require_json("name")
    if error:
        return error
    try:
        v = _build_venue(data)
    except ValueError as e:
        return err(str(e))
    db.session.add(v)
    db.session.commit()
    return jsonify({"venue": v.to_dict()}), 201


# ── Events ────────────────────────────────────────────────────────────────────

def _event_dict(ev: Event) -> dict:
    """Serialise an event with its venue flattened onto it.

    Adds venue_name/city/address and `venue_location` ("address, city") so
    the client does not have to fetch and join venues itself.
    """
    d = ev.to_dict()
    if ev.venue:
        d["venue_name"]     = ev.venue.name
        d["venue_city"]     = ev.venue.city
        d["venue_address"]  = ev.venue.address
        d["venue_location"] = ", ".join(
            p for p in (ev.venue.address, ev.venue.city) if p
        ) or None
    return d


@event_crud_bp.route("/events", methods=["GET"])
@login_required
def list_events():
    """Every event, newest date first (undated events last)."""
    events = Event.query.order_by(Event.date.desc().nullslast(), Event.created_at.desc()).all()
    return jsonify({"events": [_event_dict(ev) for ev in events]})


@event_crud_bp.route("/events", methods=["POST"])
@roles_required("promoter", "admin")
@subscription_required
def create_event():
    """Create an event. Pass `venue_id`, or a `venue` object to create one."""
    data, error = require_json("name")
    if error:
        return error

    # A new venue can be created inline with the event.
    venue_id = int(data["venue_id"]) if data.get("venue_id") else None
    new_venue = data.get("venue")
    if venue_id is None and isinstance(new_venue, dict) and (new_venue.get("name") or "").strip():
        try:
            v = _build_venue(new_venue)
        except ValueError as e:
            return err(str(e))
        db.session.add(v)
        # flush, not commit: if the event insert then fails we do not want a
        # stray venue left behind from an event that was never created.
        db.session.flush()
        venue_id = v.id

    max_bouts, mb_error = parse_max_bouts(data.get("max_bouts"))
    if mb_error:
        return err(mb_error)

    ev = Event(
        name=clean_str(data["name"], max_len=MAX_EVENT_NAME, field="Event name"),
        date=data.get("date") or None,
        time=data.get("time") or None,
        venue_id=venue_id,
        description=clean_text_block(data.get("description"), field="Description",
                                     max_chars=MAX_EVENT_DESCRIPTION),
        max_bouts=max_bouts,
        created_by=current_user()["id"],
        created_at=datetime.utcnow(),
    )
    db.session.add(ev)
    db.session.commit()
    return jsonify({"event": _event_dict(ev)}), 201


@event_crud_bp.route("/events/<int:event_id>", methods=["GET"])
@login_required
def get_event(event_id):
    """One event."""
    ev = db.session.get(Event, event_id)
    if not ev:
        return err("Event not found.", 404)
    return jsonify({"event": _event_dict(ev)})


@event_crud_bp.route("/events/<int:event_id>", methods=["PUT"])
@roles_required("promoter", "admin")
@subscription_required
def update_event(event_id):
    """Partial update: only fields present in the body change."""
    ev = db.session.get(Event, event_id)
    if not ev:
        return err("Event not found.", 404)
    data = request.get_json(silent=True) or {}
    if "name"        in data: ev.name        = clean_str(data["name"], ev.name,
                                                         max_len=MAX_EVENT_NAME,
                                                         field="Event name")
    if "date"        in data: ev.date        = data["date"] or None
    if "time"        in data: ev.time        = data["time"] or None
    if "venue_id"    in data: ev.venue_id    = clean_int(data["venue_id"],
                                                         field="venue_id", minimum=1)
    if "description" in data: ev.description = clean_text_block(
        data["description"], field="Description", max_chars=MAX_EVENT_DESCRIPTION)
    if "max_bouts"   in data:
        max_bouts, mb_error = parse_max_bouts(data["max_bouts"])
        if mb_error:
            return err(mb_error)
        # Can't shrink below the number of bouts already on the card.
        current = EventBout.query.filter_by(event_id=str(ev.id)).count()
        if max_bouts is not None and max_bouts < current:
            return err(f"This card already has {current} bouts. "
                       f"Remove some before lowering the maximum to {max_bouts}.")
        ev.max_bouts = max_bouts
    db.session.commit()
    return jsonify({"event": _event_dict(ev)})


@event_crud_bp.route("/events/<int:event_id>", methods=["DELETE"])
@roles_required("promoter", "admin")
@subscription_required
def delete_event(event_id):
    """Delete an event."""
    ev = db.session.get(Event, event_id)
    if not ev:
        return err("Event not found.", 404)
    db.session.delete(ev)
    db.session.commit()
    return jsonify({"deleted": event_id})
