"""Logged fight results."""

from ..extensions import db


class FightHistory(db.Model):
    """One fighter's result in one bout (each bout has a row per fighter).

    `opponent_name` is always set; `opponent_id` only when the opponent is
    also on FightHub. `fight_date` is an ISO date string (YYYY-MM-DD).
    """
    __tablename__ = "fight_history"
    __table_args__ = (
        db.CheckConstraint("result IN ('W','L','D')", name="ck_fight_result"),
    )

    id            = db.Column(db.Integer, primary_key=True)
    fighter_id    = db.Column(
        db.Integer,
        db.ForeignKey("fighters.id", ondelete="CASCADE"),
        nullable=False,
    )
    opponent_name = db.Column(db.String(100), nullable=False)
    opponent_id   = db.Column(
        db.Integer,
        db.ForeignKey("fighters.id", ondelete="SET NULL"),
        nullable=True,
    )
    result        = db.Column(db.String(1), nullable=False)
    method        = db.Column(db.String(50), nullable=False, default="Decision")
    fight_date    = db.Column(db.String(20), nullable=False)
    ruleset       = db.Column(db.String(50), nullable=True)
    event_id      = db.Column(
        db.Integer,
        db.ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    fighter = db.relationship("Fighter", back_populates="fights",
                              foreign_keys=[fighter_id])
    event   = db.relationship("Event")

    def _event_dict(self) -> dict | None:
        ev = self.event
        if not ev:
            return None
        return {"id": ev.id, "name": ev.name, "date": ev.date}

    def to_dict(self) -> dict:
        """For a single fighter's history (the fighter is implied)."""
        return {
            "id":          self.id,
            "opponent":    self.opponent_name,
            "opponent_id": self.opponent_id,
            "result":      self.result,
            "method":      self.method,
            "date":        self.fight_date,
            "ruleset":     self.ruleset,
            "event":       self._event_dict(),
        }

    def to_full_dict(self) -> dict:
        """As to_dict(), plus who the fighter was (for sport-wide lists)."""
        return {
            "id":          self.id,
            "fighter_id":  self.fighter_id,
            "fighter":     self.fighter.name if self.fighter else None,
            "opponent":    self.opponent_name,
            "opponent_id": self.opponent_id,
            "result":      self.result,
            "method":      self.method,
            "date":        self.fight_date,
            "ruleset":     self.ruleset,
            "event":       self._event_dict(),
        }
