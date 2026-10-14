"""Account deletion requests.

Erasure is a request handled by an administrator rather than a button that
empties the database on the spot. Two reasons: a deletion cascades into other
people's competitive records and has to be reviewed before it runs, and an
account taken over by someone else should not be able to destroy the real
owner's history in one click. The trade-off is that erasure is not immediate,
so the privacy notice commits to completing it within 30 days — the outer limit
UK GDPR Art. 12(3) allows.

The row is the audit trail. It outlives the account it refers to: `user_id` is
set to NULL when the account goes, leaving `requested_at`, `resolved_at` and
`resolved_by` as evidence that the request was made and acted on.
"""

from datetime import datetime
from ..extensions import db

# How long the operator has to act, as promised in the privacy notice.
DELETION_SLA_DAYS = 30

STATUSES = ("pending", "completed", "rejected", "cancelled")


class DeletionRequest(db.Model):
    __tablename__ = "deletion_requests"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending','completed','rejected','cancelled')",
            name="ck_deletion_requests_status",
        ),
    )

    id      = db.Column(db.Integer, primary_key=True)
    # Nullable so the audit trail survives the deletion it records. Kept as a
    # plain reference rather than a cascade for the same reason.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL", name="fk_deletion_requests_user_id"),
        nullable=True,
        index=True,
    )
    # Denormalised at request time so an administrator working the queue can
    # still tell which account a completed request belonged to.
    user_email = db.Column(db.String(255), nullable=True)

    reason  = db.Column(db.Text, nullable=True)
    status  = db.Column(db.String(20), nullable=False, default="pending")

    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at  = db.Column(db.DateTime, nullable=True)
    resolved_by  = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL", name="fk_deletion_requests_resolved_by"),
        nullable=True,
    )
    admin_note = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "user_id":      self.user_id,
            "user_email":   self.user_email,
            "reason":       self.reason,
            "status":       self.status,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "resolved_at":  self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by":  self.resolved_by,
            "admin_note":   self.admin_note,
            "days_open":    self.days_open,
            "sla_days":     DELETION_SLA_DAYS,
        }

    @property
    def days_open(self) -> int | None:
        """Whole days since the request was made, for pending requests only."""
        if self.status != "pending" or not self.requested_at:
            return None
        return (datetime.utcnow() - self.requested_at).days
