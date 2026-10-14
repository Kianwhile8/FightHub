"""Events, venues, fight-card bouts and event registrations."""

from datetime import datetime
from ..extensions import db


class Venue(db.Model):
    """Where an event is held."""
    __tablename__ = "venues"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    address  = db.Column(db.String(200), nullable=True)
    city     = db.Column(db.String(100), nullable=True)
    capacity = db.Column(db.Integer, nullable=True)

    events = db.relationship("Event", back_populates="venue")

    def to_dict(self) -> dict:
        return {
            "id":       self.id,
            "name":     self.name,
            "address":  self.address,
            "city":     self.city,
            "capacity": self.capacity,
        }


class Event(db.Model):
    """A promoter's event. Its bouts and registrations are linked by event_id."""
    __tablename__ = "events"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False)
    date        = db.Column(db.String(20), nullable=True)
    time        = db.Column(db.String(10), nullable=True)
    venue_id    = db.Column(
        db.Integer, db.ForeignKey("venues.id", ondelete="SET NULL"), nullable=True
    )
    description = db.Column(db.Text, nullable=True)
    photo       = db.Column(db.String(255), nullable=True)
    # How many bouts this card is being built to. The card can be arranged once
    # it is full, so this is what decides when that phase opens.
    max_bouts   = db.Column(db.Integer, nullable=True)
    # Who set the event up. NULL on older events, which any promoter may edit.
    created_by  = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    venue = db.relationship("Venue", back_populates="events")

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "date":        self.date,
            "time":        self.time,
            "venue_id":    self.venue_id,
            "description": self.description,
            "photo":       self.photo,
            "max_bouts":   self.max_bouts,
            "created_by":  self.created_by,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }


class EventBout(db.Model):
    """One bout on an event's fight card.

    `event_id` is a text column, not a foreign key, because early cards used
    ids generated in the browser. FighterService._event_pk() resolves it to a
    real Event when there is one.
    """

    __tablename__ = "event_bouts"

    id           = db.Column(db.Integer, primary_key=True)
    event_id     = db.Column(db.String(50), nullable=False, index=True)
    sport        = db.Column(db.String(20), nullable=False)
    fighter_a_id = db.Column(
        db.Integer, db.ForeignKey("fighters.id", ondelete="CASCADE"), nullable=False
    )
    fighter_b_id = db.Column(
        db.Integer, db.ForeignKey("fighters.id", ondelete="CASCADE"), nullable=False
    )
    description  = db.Column(db.Text, nullable=True)
    ruleset      = db.Column(db.String(50), nullable=True)
    created_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Position on the card. 0 is the main event, which tops the running order
    # and is fought last; the opener has the highest index. NULL means the card
    # has not been arranged yet, and those sort by creation order.
    order_index  = db.Column(db.Integer, nullable=True)

    # Set once the bout has been checked off as complete on the event card.
    # result is 'A' (fighter A won), 'B' (fighter B won) or 'D' (draw).
    completed    = db.Column(db.Boolean, nullable=False, default=False)
    result       = db.Column(db.String(1), nullable=True)
    method       = db.Column(db.String(50), nullable=True)
    fight_date   = db.Column(db.String(20), nullable=True)

    fighter_a = db.relationship("Fighter", foreign_keys=[fighter_a_id])
    fighter_b = db.relationship("Fighter", foreign_keys=[fighter_b_id])

    def to_dict(self) -> dict:
        fa, fb = self.fighter_a, self.fighter_b
        winner = {"A": fa, "B": fb}.get(self.result or "")
        return {
            "id":          self.id,
            "event_id":    self.event_id,
            "sport":       self.sport,
            "order_index": self.order_index,
            "description": self.description,
            "ruleset":     self.ruleset,
            "fighter_a":   {"id": fa.id, "name": fa.name, "weight_kg": fa.weight} if fa else None,
            "fighter_b":   {"id": fb.id, "name": fb.name, "weight_kg": fb.weight} if fb else None,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
            "completed":   bool(self.completed),
            "result":      self.result,
            "method":      self.method,
            "fight_date":  self.fight_date,
            "winner":      {"id": winner.id, "name": winner.name} if winner else None,
        }


class EventRegistration(db.Model):
    """A fighter putting themselves forward for an event, before being booked.

    Removed automatically when the fighter is put on the card (add_bout).
    """
    __tablename__ = "event_registrations"
    __table_args__ = (
        db.UniqueConstraint("event_id", "fighter_id", name="uq_event_registration"),
    )

    id            = db.Column(db.Integer, primary_key=True)
    event_id      = db.Column(db.String(50), nullable=False)
    fighter_id    = db.Column(
        db.Integer, db.ForeignKey("fighters.id", ondelete="CASCADE"), nullable=False
    )
    sport         = db.Column(db.String(20), nullable=False)
    registered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    fighter = db.relationship("Fighter", foreign_keys=[fighter_id])

    def to_dict(self) -> dict:
        f = self.fighter
        return {
            "id":       self.id,
            "event_id": self.event_id,
            "sport":    self.sport,
            "fighter":  {"id": f.id, "name": f.name, "weight_kg": f.weight} if f else None,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
        }
