from datetime import datetime, date as _date
from ..extensions import db

VALID_SPORTS = ("kickboxing", "mma", "boxing")


def _compute_age(dob):
    if not dob:
        return None
    today = _date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class Fighter(db.Model):
    __tablename__ = "fighters"
    __table_args__ = (
        db.CheckConstraint("sport IN ('kickboxing','mma','boxing','muaythai')", name="ck_fighters_sport"),
        db.CheckConstraint("gender IS NULL OR gender IN ('male','female')", name="ck_fighters_gender"),
        db.CheckConstraint("weight > 0", name="ck_fighters_weight"),
    )

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    weight        = db.Column(db.Float, nullable=False)
    sport         = db.Column(db.String(20), nullable=False)
    # Combat sports are contested in single-sex divisions, so this gates both
    # matchmaking and bout creation. Nullable because fighters created before
    # the field existed have no value — those are treated as "not stated"
    # rather than as a match for everyone.
    gender        = db.Column(db.String(10), nullable=True)
    gym_id        = db.Column(
        db.Integer,
        db.ForeignKey("gyms.id", ondelete="SET NULL"),
        nullable=True,
    )
    description   = db.Column(db.Text, nullable=True)
    county        = db.Column(db.String(100), nullable=True)
    # The person behind this profile. One user may own a profile in several
    # disciplines; matchmaking uses this to carry experience between them so a
    # seasoned fighter changing sport is not scored as a debutant.
    user_id       = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    record = db.relationship(
        "FighterRecord", uselist=False, back_populates="fighter",
        cascade="all, delete-orphan",
    )
    fights = db.relationship(
        "FightHistory", back_populates="fighter",
        foreign_keys="FightHistory.fighter_id",   # not opponent_id
        cascade="all, delete-orphan", order_by="FightHistory.fight_date.desc()",
    )
    gym = db.relationship("Gym", back_populates="fighters")
    prior_experience = db.relationship(
        "PriorExperience", back_populates="fighter",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        r = self.record
        return {
            "id":            self.id,
            "name":          self.name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age":           _compute_age(self.date_of_birth),
            "weight_kg":     self.weight,
            "wins":          r.wins   if r else 0,
            "losses":        r.losses if r else 0,
            "draws":         r.draws  if r else 0,
            "gym_id":        self.gym_id,
            "description":   self.description,
            "county":        self.county,
            "sport":         self.sport,
            "gender":        self.gender,
            "user_id":       self.user_id,
        }


class FighterRecord(db.Model):
    __tablename__ = "fighter_records"
    __table_args__ = (
        db.CheckConstraint("wins   >= 0", name="ck_records_wins"),
        db.CheckConstraint("losses >= 0", name="ck_records_losses"),
        db.CheckConstraint("draws  >= 0", name="ck_records_draws"),
    )

    fighter_id = db.Column(
        db.Integer,
        db.ForeignKey("fighters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    wins   = db.Column(db.Integer, nullable=False, default=0)
    losses = db.Column(db.Integer, nullable=False, default=0)
    draws  = db.Column(db.Integer, nullable=False, default=0)

    fighter = db.relationship("Fighter", back_populates="record")


class PriorExperience(db.Model):
    """Experience in another discipline that was not fought on the platform.

    Coaches and admins declare this for fighters who have no linked account, or
    whose earlier career predates FightHub. It feeds the same transfer credit as
    a linked profile, minus the rating — there is no history to derive one from.
    """
    __tablename__ = "fighter_prior_experience"
    __table_args__ = (
        db.CheckConstraint("wins   >= 0", name="ck_prior_wins"),
        db.CheckConstraint("losses >= 0", name="ck_prior_losses"),
        db.CheckConstraint("draws  >= 0", name="ck_prior_draws"),
        db.UniqueConstraint("fighter_id", "sport", name="uq_prior_fighter_sport"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    fighter_id = db.Column(
        db.Integer,
        db.ForeignKey("fighters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sport          = db.Column(db.String(20), nullable=False)
    wins           = db.Column(db.Integer, nullable=False, default=0)
    losses         = db.Column(db.Integer, nullable=False, default=0)
    draws          = db.Column(db.Integer, nullable=False, default=0)
    last_bout_date = db.Column(db.String(20), nullable=True)
    note           = db.Column(db.String(255), nullable=True)
    created_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    fighter = db.relationship("Fighter", back_populates="prior_experience")

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "fighter_id":     self.fighter_id,
            "sport":          self.sport,
            "wins":           self.wins,
            "losses":         self.losses,
            "draws":          self.draws,
            "bouts":          self.wins + self.losses + self.draws,
            "last_bout_date": self.last_bout_date,
            "note":           self.note,
        }
