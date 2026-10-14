"""Gyms."""

from datetime import datetime
from ..extensions import db


class Gym(db.Model):
    """A gym, owned by one coach (`coach_id`). Fighters belong to a gym."""
    __tablename__ = "gyms"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    location   = db.Column(db.String(200), nullable=True)
    coach_id   = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    photo      = db.Column(db.String(255), nullable=True)
    county     = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    coach    = db.relationship("User", back_populates="gyms", foreign_keys=[coach_id])
    fighters = db.relationship("Fighter", back_populates="gym")

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "name":       self.name,
            "location":   self.location,
            "coach_id":   self.coach_id,
            "photo":      self.photo,
            "county":     self.county,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
