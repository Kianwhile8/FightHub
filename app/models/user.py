from datetime import datetime
from ..extensions import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('fighter','coach','promoter','admin')",
            name="ck_users_role",
        ),
        # 'undisclosed' is a stated refusal to answer; NULL means the account
        # was never asked. Every pre-existing account, and every coach and
        # promoter, is NULL — the question is only put to fighters, because
        # theirs is the only role the answer is used for.
        db.CheckConstraint(
            "gender IS NULL OR gender IN ('male','female','undisclosed')",
            name="ck_users_gender",
        ),
    )

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default="fighter")
    fighter_id    = db.Column(
        db.Integer,
        db.ForeignKey("fighters.id", ondelete="SET NULL", use_alter=True, name="fk_users_fighter_id"),
        nullable=True,
    )
    fighter_sport = db.Column(db.String(20), nullable=True)
    # Asked at registration, and only of fighters. It seeds the gender on the
    # fighter profile they go on to create, which is what matchmaking reads —
    # this column is the account's own answer, not the profile's.
    gender        = db.Column(db.String(20), nullable=True)
    hide_record     = db.Column(db.Boolean, nullable=False, default=False)
    # Set once the account has confirmed its address. Nothing gates on this yet
    # — REQUIRE_VERIFIED_EMAIL turns enforcement on when the mail flow lands.
    email_verified     = db.Column(db.Boolean, nullable=False, default=False)
    email_verified_at  = db.Column(db.DateTime, nullable=True)
    # Proof of agreement to the terms, required by UK GDPR Art. 7(1): which
    # version was accepted and when. Nullable because accounts created before
    # the terms existed have no record — those users are re-prompted on their
    # next sign-in rather than being silently treated as having agreed.
    terms_version     = db.Column(db.String(20), nullable=True)
    terms_accepted_at = db.Column(db.DateTime, nullable=True)
    # The privacy notice is transparency rather than consent — there is no
    # "agreeing" to be informed — but which version a user was shown, and when,
    # is the evidence that the Art. 13 duty was discharged. Recorded separately
    # from the terms so the two documents can be reissued independently.
    privacy_version     = db.Column(db.String(20), nullable=True)
    privacy_accepted_at = db.Column(db.DateTime, nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)
    created_at      = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    gyms           = db.relationship("Gym", back_populates="coach", foreign_keys="Gym.coach_id")
    linked_fighter = db.relationship("Fighter", foreign_keys=[fighter_id])

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "email":           self.email,
            "role":            self.role,
            "fighter_id":      self.fighter_id,
            "fighter_sport":   self.fighter_sport,
            "gender":          self.gender,
            "created_at":      self.created_at.isoformat() if self.created_at else None,
            "hide_record":     bool(self.hide_record),
            "email_verified":  bool(self.email_verified),
            "terms_version":    self.terms_version,
            "terms_accepted_at": self.terms_accepted_at.isoformat() if self.terms_accepted_at else None,
            "privacy_version":    self.privacy_version,
            "privacy_accepted_at": self.privacy_accepted_at.isoformat() if self.privacy_accepted_at else None,
            "profile_picture": self.profile_picture,
        }
