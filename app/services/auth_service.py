"""AuthService — same external interface as the old SQLite authDB class,
backed by SQLAlchemy. Blueprints continue to call current_app.auth_db.*
unchanged."""

from datetime import datetime
from flask import current_app
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db
from ..legal import TERMS_VERSION, PRIVACY_VERSION
from ..constants import ENGLISH_COUNTIES
from ..validation import clean_email, clean_password, clean_str
from ..models.user import User
from ..models.gym import Gym
from ..models.fighter import Fighter
from ..models.fight import FightHistory
from ..models.deletion_request import DeletionRequest

VALID_ROLES  = ("fighter", "coach", "promoter", "admin")
# Must match VALID_SPORTS in helpers.py and ck_fighters_sport in the database.
VALID_SPORTS = ("kickboxing", "mma", "boxing", "muaythai")
# Must match ck_users_gender. Wider than the fighter profile's own vocabulary:
# an account may decline to answer, a competitive division may not.
VALID_USER_GENDERS = ("male", "female", "undisclosed")

_DUMMY_HASH = None


def _dummy_hash() -> str:
    """A real hash of a value no password can be, for timing equalisation.

    Built on first use rather than at import: it costs one full scrypt round,
    which is wasted work in a process that never serves a failed sign-in (the
    CLI, the migration runner) and would slow every container start.
    """
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = generate_password_hash("\x00 no account \x00")
    return _DUMMY_HASH


class AuthService:

    # ── users ──────────────────────────────────────────────────────────────

    def register(self, email: str, password: str, role: str,
                 fighter_id: int = None, fighter_sport: str = None,
                 accept_terms: bool = False, gender: str = None) -> dict:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'.")
        # Bounds and shape are checked here, at the chokepoint every account
        # creation passes through — the CLI seeder and any future import script
        # included — rather than in the route, which only covers the one path.
        email = clean_email(email)
        password = clean_password(password)
        if fighter_sport and fighter_sport not in VALID_SPORTS:
            raise ValueError(f"Invalid sport '{fighter_sport}'.")
        if gender is not None and gender not in VALID_USER_GENDERS:
            raise ValueError("Gender must be 'male', 'female' or 'undisclosed'.")
        # Only fighters are asked, so only fighters are recorded. Dropping it
        # here rather than relying on the form not to show the field means a
        # gender posted directly for a coach or promoter is discarded instead
        # of stored: the rule is that we do not hold data we have no use for,
        # and a rule enforced only in the UI is not enforced.
        if role != "fighter":
            gender = None
        # Checked here rather than only in the blueprint so that no code path
        # can create an account without a consent record — the CLI seeder and
        # any future import script go through this method too.
        if not accept_terms:
            raise ValueError("You must accept the terms and privacy notice to create an account.")
        now = datetime.utcnow()
        user = User(
            email=email,   # already normalised and validated above
            password_hash=generate_password_hash(password),
            role=role,
            fighter_id=fighter_id,
            fighter_sport=fighter_sport,
            gender=gender,
            terms_version=TERMS_VERSION,
            terms_accepted_at=now,
            # The notice was shown alongside the terms at sign-up, so the same
            # act evidences both.
            privacy_version=PRIVACY_VERSION,
            privacy_accepted_at=now,
            created_at=now,
        )
        db.session.add(user)
        try:
            # Flush, not commit: this assigns user.id so the subscription row can
            # reference it, while leaving both inserts in one transaction. A user
            # must never exist without an entitlement row — otherwise their
            # entitlement depends on whichever request happens to self-heal it
            # first, and a crash between two commits would leave an account that
            # has neither a trial nor a subscription.
            db.session.flush()
            # Administrators never pay, so their row is comped from the start
            # rather than running a trial that will never be looked at.
            if role == "admin":
                sub = current_app.billing_db.build_for_new_user(
                    user.id, role, created_at=now,
                    status="comped", comp_reason="administrator")
            else:
                sub = current_app.billing_db.build_for_new_user(
                    user.id, role, created_at=now)
            db.session.add(sub)
            db.session.commit()
        except IntegrityError:
            # Duplicate email. The rollback discards the subscription too, so
            # there is no orphan row to clean up.
            db.session.rollback()
            raise ValueError("An account with that email already exists.")
        return user.to_dict()

    # One message for both failure modes. Saying "no account found with that
    # address" confirms which addresses are registered, which turns the login
    # form into a membership oracle — usable to check whether a named person
    # competes, and to build a target list for credential stuffing. The rate
    # limit caps how fast that can be done; it does not stop it leaking.
    _LOGIN_FAILED = "Email or password is incorrect."

    def login(self, email: str, password: str) -> dict:
        user = User.query.filter_by(email=email.strip().lower()).first()
        if not user:
            # Verify against a throwaway hash so a missing account costs about
            # the same time as a wrong password. Without it the timing
            # difference hands back the answer the message above withholds.
            check_password_hash(_dummy_hash(), password)
            raise ValueError(self._LOGIN_FAILED)
        if not check_password_hash(user.password_hash, password):
            raise ValueError(self._LOGIN_FAILED)
        return user.to_dict()

    def accept_terms(self, user_id: int) -> dict:
        """Record agreement to the current terms and privacy notice.

        Used when either document is re-issued: its version constant moves
        ahead of the stored value and the user is asked again on their next
        sign-in. Both are recorded together because both are presented
        together — there is no path through the UI that shows one without the
        other.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found.")
        now = datetime.utcnow()
        user.terms_version = TERMS_VERSION
        user.terms_accepted_at = now
        user.privacy_version = PRIVACY_VERSION
        user.privacy_accepted_at = now
        db.session.commit()
        return user.to_dict()

    def get_by_id(self, user_id: int) -> dict | None:
        user = db.session.get(User, user_id)
        return user.to_dict() if user else None

    def get_all_users(self) -> list[dict]:
        return [u.to_dict() for u in
                User.query.order_by(User.created_at.desc()).all()]

    def update_role(self, user_id: int, new_role: str) -> dict:
        if new_role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{new_role}'.")
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found.")
        user.role = new_role
        db.session.commit()
        return user.to_dict()

    def link_fighter(self, user_id: int, fighter_id: int, fighter_sport: str) -> dict:
        """Claim a fighter profile for this account.

        A user may own a profile in more than one discipline; linking a second
        one does not release the first. `User.fighter_id` / `fighter_sport` track
        which profile is *active* (the one shown on their own profile page),
        while `Fighter.user_id` records ownership of each — that ownership is
        what lets matchmaking carry experience between disciplines.
        """
        if fighter_sport not in VALID_SPORTS:
            raise ValueError(f"Invalid sport '{fighter_sport}'.")
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found.")

        fighter = Fighter.query.filter_by(id=fighter_id, sport=fighter_sport).first()
        if not fighter:
            raise ValueError(f"Fighter {fighter_id} not found in {fighter_sport}.")
        if fighter.user_id and fighter.user_id != user_id:
            raise ValueError("This fighter profile is already linked to another account.")

        conflict = User.query.filter(
            User.fighter_id == fighter_id,
            User.fighter_sport == fighter_sport,
            User.id != user_id,
        ).first()
        if conflict:
            raise ValueError("This fighter profile is already linked to another account.")

        fighter.user_id    = user_id
        user.fighter_id    = fighter_id
        user.fighter_sport = fighter_sport
        db.session.commit()
        return user.to_dict()

    def owned_fighter_ids(self, user_id: int) -> set:
        """Every fighter profile this account owns, across all disciplines."""
        if not user_id:
            return set()
        ids = {f.id for f in Fighter.query.filter_by(user_id=user_id).all()}
        user = db.session.get(User, user_id)
        if user and user.fighter_id:          # legacy link, pre-Fighter.user_id
            ids.add(user.fighter_id)
        return ids

    # Replaces a deleted fighter's name wherever it survives on somebody else's
    # record. Not "Deleted user": the row is a real bout that really happened,
    # and the reader needs to see an opponent, not an error.
    ANONYMISED_OPPONENT = "Former member"

    def delete_user(self, user_id: int) -> None:
        """Erase an account and everything personal attached to it.

        Explicit rather than left to database cascades, because two things have
        to happen that no cascade would do:

        * `FightHistory.opponent_name` is a plain string, so the FK's ON DELETE
          SET NULL clears the link and leaves the name behind. It has to be
          overwritten first, or deleting an account would publish exactly the
          name it was meant to remove.
        * Uploaded photographs live in object storage, not in the database, so
          nothing in the schema knows to remove them.

        * A live Stripe subscription has to be cancelled first. The
          `subscriptions` row cascades away with the user, so without this Stripe
          would carry on charging somebody whose data has just been erased —
          both a billing fault and a UK GDPR one, and invisible from here
          afterwards because the row that named the subscription is gone.

        What deliberately survives: the bout rows themselves, anonymised, since
        a result belongs to both fighters and erasing it would rewrite someone
        else's record; and the deletion_requests audit row, whose foreign key
        is SET NULL for that reason.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found.")

        # Before the delete, while the subscription id is still readable. Logged
        # and continued on failure, exactly as _delete_stored_file is: an
        # erasure request must not be blocked by a Stripe outage. A subscription
        # left running is recoverable from the Stripe dashboard; a refused
        # erasure is a compliance failure.
        try:
            current_app.billing_db.cancel_stripe_subscription(user_id)
        except Exception:
            current_app.logger.exception(
                "could not cancel the Stripe subscription for user %s during "
                "deletion — CANCEL IT MANUALLY in the Stripe dashboard", user_id)

        fighter_ids = self.owned_fighter_ids(user_id)

        # Anonymise before deleting, while the ids still resolve.
        if fighter_ids:
            FightHistory.query.filter(
                FightHistory.opponent_id.in_(fighter_ids)
            ).update({"opponent_name": self.ANONYMISED_OPPONENT},
                     synchronize_session=False)

        # Photographs: the account avatar, and any photo on a fighter profile.
        self._delete_stored_file(user.profile_picture)

        for fid in fighter_ids:
            fighter = db.session.get(Fighter, fid)
            if fighter:
                # Cascades from here cover the record, the fight history this
                # fighter owns, prior experience, bouts and registrations.
                db.session.delete(fighter)

        db.session.delete(user)
        db.session.commit()

    @staticmethod
    def _delete_stored_file(filename: str | None) -> None:
        """Remove an uploaded file, tolerating one that has already gone.

        A storage failure must not abort an erasure that is otherwise complete:
        the database is the record of who exists, and leaving the account in
        place because an orphaned image could not be reached would be the worse
        outcome. It is logged instead so it can be cleaned up.
        """
        if not filename:
            return
        try:
            from .storage import get_storage
            get_storage().delete(filename)
        except Exception:
            from flask import current_app
            current_app.logger.warning(
                "could not delete stored file %r during account erasure", filename)

    # ── account deletion requests ──────────────────────────────────────────

    def get_deletion_request(self, user_id: int) -> dict | None:
        """This account's open request, if it has one."""
        req = DeletionRequest.query.filter_by(
            user_id=user_id, status="pending"
        ).order_by(DeletionRequest.requested_at.desc()).first()
        return req.to_dict() if req else None

    def request_deletion(self, user_id: int, password: str,
                         reason: str = None) -> dict:
        """Open an erasure request, after re-checking the password.

        The password is asked for again because this is the one action on the
        platform that cannot be undone by the person it happens to. An
        unattended session should not be enough to destroy someone's record.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found.")
        if not check_password_hash(user.password_hash, password):
            raise ValueError("Password is incorrect.")
        if self.get_deletion_request(user_id):
            raise ValueError("A deletion request is already pending for this account.")
        # An administrator who deleted their own account could leave the
        # platform with nobody able to operate it — including nobody able to
        # action anyone else's deletion request.
        if user.role == "admin":
            raise ValueError(
                "Administrator accounts cannot be deleted through this form. "
                "Ask another administrator to remove the account.")

        req = DeletionRequest(
            user_id=user_id,
            user_email=user.email,
            reason=reason,
            status="pending",
            requested_at=datetime.utcnow(),
        )
        db.session.add(req)
        db.session.commit()
        return req.to_dict()

    def cancel_deletion(self, user_id: int) -> None:
        """Withdraw a pending request. Only the account holder can."""
        req = DeletionRequest.query.filter_by(
            user_id=user_id, status="pending"
        ).order_by(DeletionRequest.requested_at.desc()).first()
        if not req:
            raise ValueError("No pending deletion request to cancel.")
        req.status = "cancelled"
        req.resolved_at = datetime.utcnow()
        db.session.commit()

    def list_deletion_requests(self, status: str = None) -> list[dict]:
        q = DeletionRequest.query
        if status:
            q = q.filter_by(status=status)
        # Oldest first: the queue is worked against a 30-day deadline, so the
        # one closest to it should be the one on top.
        return [r.to_dict() for r in q.order_by(DeletionRequest.requested_at.asc()).all()]

    def resolve_deletion_request(self, request_id: int, admin_id: int,
                                 action: str, note: str = None) -> dict:
        """Complete or reject a request.

        'complete' erases the account. 'reject' refuses it — lawful only in the
        narrow cases the UK GDPR allows, and the note is where the reason is
        recorded, because the requester is entitled to be told it.
        """
        if action not in ("complete", "reject"):
            raise ValueError("Action must be 'complete' or 'reject'.")
        req = db.session.get(DeletionRequest, request_id)
        if not req:
            raise ValueError(f"Deletion request {request_id} not found.")
        if req.status != "pending":
            raise ValueError(f"That request is already {req.status}.")
        if action == "reject" and not (note or "").strip():
            raise ValueError("A reason is required when refusing a deletion request.")

        if action == "complete":
            if req.user_id:
                # Resolve the request first so the audit row is written even if
                # the account has somehow gone already.
                self.delete_user(req.user_id)
            # delete_user commits, and the FK's SET NULL has already cleared
            # req.user_id — so reload before writing the outcome.
            req = db.session.get(DeletionRequest, request_id)
            req.status = "completed"
        else:
            req.status = "rejected"

        req.resolved_at = datetime.utcnow()
        req.resolved_by = admin_id
        req.admin_note = note
        db.session.commit()
        return req.to_dict()

    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        new_password = clean_password(new_password, field="New password")
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError("User not found.")
        if not check_password_hash(user.password_hash, old_password):
            raise ValueError("Current password is incorrect.")
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()

    def update_privacy(self, user_id: int, hide_record: bool) -> dict:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found.")
        user.hide_record = hide_record
        db.session.commit()
        return user.to_dict()

    def get_hidden_fighter_ids(self, sport: str) -> set:
        """Fighter ids in `sport` whose owner has hidden their record.

        Covers every profile the user owns rather than only their active one —
        now that one account can hold a profile in several disciplines, a single
        privacy switch that only hid one of them would leak the rest.
        """
        hidden_users = [u.id for u in User.query.filter_by(hide_record=True).all()]
        ids = set()
        if hidden_users:
            ids |= {f.id for f in Fighter.query.filter(
                Fighter.user_id.in_(hidden_users),
                Fighter.sport == sport,
            ).all()}
        # Accounts linked before Fighter.user_id existed.
        ids |= {u.fighter_id for u in User.query.filter_by(
            hide_record=True, fighter_sport=sport
        ).filter(User.fighter_id.isnot(None)).all()}
        return ids

    # ── gyms ───────────────────────────────────────────────────────────────

    # Gym column widths.
    MAX_GYM_NAME_LEN = 100
    MAX_GYM_LOCATION_LEN = 200

    def create_gym(self, name: str, coach_id: int, location: str = None,
                   county: str = None) -> dict:
        coach = db.session.get(User, coach_id)
        if not coach:
            raise ValueError(f"User {coach_id} not found.")
        if coach.role not in ("coach", "admin"):
            raise ValueError("Only coaches and admins can create gyms.")
        name     = self._clean_gym_name(name)
        location = clean_str(location, max_len=self.MAX_GYM_LOCATION_LEN,
                             field="Location")
        county   = self._clean_gym_county(county)
        gym = Gym(
            name=name,
            location=location,
            coach_id=coach_id,
            county=county,
            created_at=datetime.utcnow(),
        )
        db.session.add(gym)
        db.session.commit()
        return gym.to_dict()

    def get_gym(self, gym_id: int) -> dict | None:
        gym = db.session.get(Gym, gym_id)
        return gym.to_dict() if gym else None

    def get_all_gyms(self, county: str = None) -> list[dict]:
        q = Gym.query
        if county:
            q = q.filter(Gym.county == county)
        return [g.to_dict() for g in q.order_by(Gym.name).all()]

    def get_all_gyms_by_coach(self, coach_id: int, county: str = None) -> list[dict]:
        q = Gym.query.filter_by(coach_id=coach_id)
        if county:
            q = q.filter(Gym.county == county)
        return [g.to_dict() for g in q.all()]

    def update_gym(self, gym_id: int, coach_id: int,
                   name: str = None, location: str = None,
                   county: str = None) -> dict:
        gym = self._assert_gym_owner(gym_id, coach_id)
        if name:
            gym["_obj"].name = self._clean_gym_name(name)
        if location is not None:
            gym["_obj"].location = clean_str(
                location, max_len=self.MAX_GYM_LOCATION_LEN, field="Location")
        if county is not None:
            gym["_obj"].county = self._clean_gym_county(county)
        db.session.commit()
        return gym["_obj"].to_dict()

    @classmethod
    def _clean_gym_name(cls, value):
        name = clean_str(value, max_len=cls.MAX_GYM_NAME_LEN, field="Gym name")
        if not name:
            raise ValueError("Gym name is required.")
        return name

    @staticmethod
    def _clean_gym_county(value):
        county = clean_str(value, max_len=100, field="County")
        if county and county not in ENGLISH_COUNTIES:
            raise ValueError(f"'{county}' is not a recognised county.")
        return county

    def update_profile_picture(self, user_id: int, filename: str) -> dict:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found.")
        user.profile_picture = filename
        db.session.commit()
        return user.to_dict()

    def delete_gym(self, gym_id: int, coach_id: int) -> None:
        info = self._assert_gym_owner(gym_id, coach_id)
        db.session.delete(info["_obj"])
        db.session.commit()

    def _assert_gym_owner(self, gym_id: int, coach_id: int) -> dict:
        gym = db.session.get(Gym, gym_id)
        if not gym:
            raise ValueError(f"Gym {gym_id} not found.")
        coach = db.session.get(User, coach_id)
        role  = coach.role if coach else None
        if gym.coach_id != coach_id and role != "admin":
            raise ValueError("You do not have permission to modify this gym.")
        d = gym.to_dict()
        d["_obj"] = gym
        return d

    # Passwords that must never guard the account that can delete anyone's
    # data. Not a general password policy — a floor under the one credential
    # that gets planted automatically by a deploy script and then forgotten.
    _WEAK_ADMIN_PASSWORDS = frozenset({
        "admin", "admin123", "password", "password1", "password123",
        "letmein", "changeme", "fighthub", "fighthub1", "nimda", "nimda321",
        "12345678", "123456789", "qwertyui", "adminadmin",
        "replace-with-strong-password",
    })

    def seed_admin(self) -> None:
        import os
        if User.query.filter_by(role="admin").first():
            print("[AUTH] Admin account already exists — nothing to seed.")
            return
        email    = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")
        if not email or not password:
            print("[AUTH] No admin seeded — set ADMIN_EMAIL and ADMIN_PASSWORD in .env.")
            return
        # Refuse rather than warn. A warning printed during a container start
        # is a warning nobody reads, and the result would be a live
        # administrator account on a guessable password.
        if password.strip().lower() in self._WEAK_ADMIN_PASSWORDS:
            print("[AUTH] Admin NOT seeded: ADMIN_PASSWORD is a well-known weak "
                  "password. Set a strong one and run the seeder again.")
            return
        if len(password) < 12:
            print("[AUTH] Admin NOT seeded: ADMIN_PASSWORD must be at least 12 "
                  "characters. This account can read and erase every user's data.")
            return
        try:
            # The operator running the seeder is the one agreeing, on their own
            # behalf — this account is created by whoever controls the deploy,
            # not by a visitor filling in the sign-up form.
            self.register(email=email, password=password, role="admin",
                          accept_terms=True)
        except ValueError as e:
            # Email already taken by a non-admin account, or another process
            # seeded concurrently. Either way there is nothing more to do.
            print(f"[AUTH] Admin not seeded: {e}")
            return
        print(f"[AUTH] Admin account created: {email}")
