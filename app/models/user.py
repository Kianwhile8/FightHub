"""User accounts."""

from datetime import datetime
from ..extensions import db


class User(db.Model):
    """A login. `role` is fighter, coach, promoter or admin.

    `fighter_id` / `fighter_sport` point at the user's *active* fighter
    profile. Ownership of every profile is recorded on `Fighter.user_id`.
    """
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('fighter','coach','promoter','admin')",
            name="ck_users_role",
        ),
        # 'undisclosed' means they chose not to answer; NULL means they were
        # never asked (only fighters are asked).
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
    # The account's own answer at registration. It pre-fills the fighter
    # profile's gender, which is what matchmaking actually reads.
    gender        = db.Column(db.String(20), nullable=True)
    hide_record     = db.Column(db.Boolean, nullable=False, default=False)
    # Not enforced yet: REQUIRE_VERIFIED_EMAIL will gate on it once outbound
    # email is wired up.
    email_verified     = db.Column(db.Boolean, nullable=False, default=False)
    email_verified_at  = db.Column(db.DateTime, nullable=True)
    # Which terms version was accepted, and when (UK GDPR Art. 7(1)). NULL
    # means never accepted; those users are prompted on their next sign-in.
    terms_version     = db.Column(db.String(20), nullable=True)
    terms_accepted_at = db.Column(db.DateTime, nullable=True)
    # Which privacy-notice version the user was shown, and when (Art. 13).
    # Separate from the terms so each document can be reissued on its own.
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
