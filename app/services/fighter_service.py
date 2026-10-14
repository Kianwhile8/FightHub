"""FighterService — same external interface as the old SQLite FighterDB class,
backed by SQLAlchemy. Blueprints continue to use `with get_db(sport) as db:`
unchanged."""

from datetime import date as _date, datetime
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..constants import ENGLISH_COUNTIES
from ..validation import (
    ValidationError, clean_str, clean_float, clean_text_block,
)
from ..models.fighter import Fighter, FighterRecord, PriorExperience
from ..models.fight import FightHistory
from ..models.event import Event, EventBout, EventRegistration


class FighterService:
    def __init__(self, sport: str) -> None:
        self.sport = sport

    def __enter__(self):  return self
    def __exit__(self, *_): pass   # SQLAlchemy session is request-scoped

    # ── fighters ───────────────────────────────────────────────────────────

    def get_all_fighters(self, county: str = None,
                         max_weight: float = None,
                         gender: str = None) -> list[dict]:
        q = Fighter.query.filter_by(sport=self.sport)
        return [f.to_dict() for f in
                self._filtered(q, county, max_weight, gender).order_by(Fighter.name).all()]

    def search_fighters(self, query: str, county: str = None,
                        max_weight: float = None,
                        gender: str = None) -> list[dict]:
        q = Fighter.query.filter(
            Fighter.sport == self.sport,
            Fighter.name.ilike(f"%{query}%"),
        )
        return [f.to_dict() for f in
                self._filtered(q, county, max_weight, gender).order_by(Fighter.name).all()]

    @staticmethod
    def _filtered(q, county: str = None, max_weight: float = None,
                  gender: str = None):
        """Apply the shared list filters, so browsing and searching agree.

        `max_weight` is an inclusive ceiling — "at or under 57 kg" — which is
        how a coach actually thinks about it: they want everyone their fighter
        could plausibly meet, not one narrow division.

        `gender` is an exact match, and profiles that have not stated one are
        excluded rather than shown under both. Someone filtering to "female" is
        almost always building a card or looking for an opponent, and a profile
        of unknown sex is not a candidate for either — matchmaking refuses those
        pairings too. They remain visible with the filter off.
        """
        if county:
            q = q.filter(Fighter.county == county)
        if max_weight is not None:
            q = q.filter(Fighter.weight <= max_weight)
        if gender:
            q = q.filter(Fighter.gender == gender)
        return q

    def get_fighter(self, fighter_id: int) -> dict | None:
        f = Fighter.query.filter_by(id=fighter_id, sport=self.sport).first()
        return f.to_dict() if f else None

    VALID_GENDERS = ("male", "female")

    # Matches the column widths, so an over-long value is refused with a clear
    # message instead of raising a DataError from the driver.
    MAX_NAME_LEN = 100
    MAX_DESCRIPTION_WORDS = 200
    MAX_DESCRIPTION_CHARS = 2000
    # A plausible range for a competing adult, in kilograms. The lower bound is
    # the previous `weight > 0` CHECK made useful: 0.5 kg passed that.
    MIN_WEIGHT_KG = 20.0
    MAX_WEIGHT_KG = 400.0

    def add_fighter(self, name: str, weight: float, date_of_birth=None,
                    description: str = None, county: str = None,
                    gender: str = None) -> int:
        from datetime import date as _date
        name        = self._clean_name(name)
        weight      = self._clean_weight(weight)
        description = self._clean_description(description)
        county      = self._clean_county(county)
        if date_of_birth:
            today = _date.today()
            age = today.year - date_of_birth.year - (
                (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
            )
            if age < 16:
                raise ValueError("Fighter must be at least 16 years old.")
        if gender is not None and gender not in self.VALID_GENDERS:
            raise ValueError("Gender must be 'male' or 'female'.")
        f = Fighter(
            name=name, date_of_birth=date_of_birth, weight=weight,
            sport=self.sport, description=description, county=county,
            gender=gender,
            created_at=datetime.utcnow(),
        )
        db.session.add(f)
        db.session.flush()
        rec = FighterRecord(fighter_id=f.id)
        db.session.add(rec)
        db.session.commit()
        return f.id

    def update_fighter(self, fighter_id: int, **fields) -> None:
        f = Fighter.query.filter_by(id=fighter_id, sport=self.sport).first()
        if not f:
            raise ValueError(f"Fighter {fighter_id} not found.")
        # Clean through the same helpers as creation. An edit reaches the same
        # columns, so anything refused on the way in has to be refused here too
        # — otherwise the cap is bypassed by creating a row and then updating it.
        if "name" in fields:
            fields["name"] = self._clean_name(fields["name"])
        if "weight" in fields:
            fields["weight"] = self._clean_weight(fields["weight"])
        if "description" in fields:
            fields["description"] = self._clean_description(fields["description"])
        if "county" in fields:
            fields["county"] = self._clean_county(fields["county"])
        if "gender" in fields and fields["gender"] is not None \
                and fields["gender"] not in self.VALID_GENDERS:
            raise ValueError("Gender must be 'male' or 'female'.")
        for field in ("name", "date_of_birth", "weight", "description", "county", "gender"):
            if field in fields:
                setattr(f, field, fields[field])
        db.session.commit()

    # ── field cleaning, shared by create and update ────────────────────────

    @classmethod
    def _clean_name(cls, value):
        name = clean_str(value, max_len=cls.MAX_NAME_LEN, field="Name")
        if not name:
            raise ValidationError("Name is required.")
        return name

    @classmethod
    def _clean_weight(cls, value):
        return clean_float(value, field="Weight",
                           minimum=cls.MIN_WEIGHT_KG, maximum=cls.MAX_WEIGHT_KG)

    @classmethod
    def _clean_description(cls, value):
        return clean_text_block(value, field="Description",
                                max_words=cls.MAX_DESCRIPTION_WORDS,
                                max_chars=cls.MAX_DESCRIPTION_CHARS)

    @staticmethod
    def _clean_county(value):
        """A county has to be one we actually list.

        Free text here was stored verbatim and then used as a filter value, so
        a typo produced a county nobody else could ever match on.
        """
        county = clean_str(value, max_len=100, field="County")
        if county and county not in ENGLISH_COUNTIES:
            raise ValidationError(f"'{county}' is not a recognised county.")
        return county

    def delete_fighter(self, fighter_id: int) -> None:
        f = Fighter.query.filter_by(id=fighter_id, sport=self.sport).first()
        if not f:
            raise ValueError(f"Fighter {fighter_id} not found.")
        db.session.delete(f)
        db.session.commit()

    def assign_gym(self, fighter_id: int, gym_id: int | None) -> None:
        f = Fighter.query.filter_by(id=fighter_id, sport=self.sport).first()
        if not f:
            raise ValueError(f"Fighter {fighter_id} not found.")
        f.gym_id = gym_id
        db.session.commit()

    def get_fighters_by_gym(self, gym_id: int) -> list[dict]:
        return [f.to_dict() for f in
                Fighter.query.filter_by(sport=self.sport, gym_id=gym_id)
                             .order_by(Fighter.name).all()]

    # ── fight history ──────────────────────────────────────────────────────

    def add_fight(self, fighter_id: int, opponent_name: str, result: str,
                  method: str = "Decision", fight_date: str = None,
                  opponent_id: int = None, ruleset: str = None,
                  event_id: int = None) -> int:
        result = result.upper()
        if result not in ("W", "L", "D"):
            raise ValueError("Result must be 'W', 'L', or 'D'.")
        fight_date = fight_date or str(_date.today())
        method     = method or "Decision"
        f = Fighter.query.filter_by(id=fighter_id, sport=self.sport).first()
        if not f:
            raise ValueError(f"Fighter {fighter_id} not found.")
        # If this matchup is on an event card, the fight took place at that event.
        card_bout = None
        if event_id is None:
            card_bout = self._find_card_bout(fighter_id, opponent_id, opponent_name)
            if card_bout:
                event_id = self._event_pk(card_bout)
        history = FightHistory(
            fighter_id=fighter_id,
            opponent_name=opponent_name,
            opponent_id=opponent_id,
            result=result,
            method=method,
            fight_date=fight_date,
            ruleset=ruleset or None,
            event_id=event_id,
        )
        db.session.add(history)
        if card_bout and not card_bout.completed:
            self._stamp_bout(card_bout, self._bout_result(card_bout, fighter_id, result),
                             method, fight_date)
        rec = f.record
        if result == "W": rec.wins   += 1
        if result == "L": rec.losses += 1
        if result == "D": rec.draws  += 1
        db.session.commit()
        return history.id

    def get_fight_history(self, fighter_id: int) -> list[dict]:
        rows = FightHistory.query.filter_by(fighter_id=fighter_id)\
                                 .order_by(FightHistory.fight_date.desc()).all()
        return [h.to_dict() for h in rows]

    def get_all_fights(self) -> list[dict]:
        rows = (FightHistory.query
                .join(Fighter, FightHistory.fighter_id == Fighter.id)
                .filter(Fighter.sport == self.sport)
                .order_by(FightHistory.fight_date.desc())
                .all())
        return [h.to_full_dict() for h in rows]

    # ── prior experience (declared) ────────────────────────────────────────

    def list_prior_experience(self, fighter_id: int) -> list[dict]:
        return [p.to_dict() for p in
                PriorExperience.query.filter_by(fighter_id=fighter_id)
                                     .order_by(PriorExperience.sport).all()]

    def set_prior_experience(self, fighter_id: int, sport: str, wins: int = 0,
                             losses: int = 0, draws: int = 0,
                             last_bout_date: str = None,
                             note: str = None) -> dict:
        """Declare (or replace) a fighter's record in another discipline.

        Upserts on (fighter_id, sport) so re-submitting corrects the figures
        rather than stacking a second entry on top of the first.
        """
        from .matchmaker import transfer_sports
        if sport not in transfer_sports:
            allowed = ", ".join(transfer_sports)
            raise ValueError(f"Unknown discipline '{sport}'. Choose from: {allowed}")
        if sport == self.sport:
            raise ValueError(
                "Prior experience is for other disciplines — bouts in this sport "
                "belong in the fight history."
            )
        if not Fighter.query.filter_by(id=fighter_id, sport=self.sport).first():
            raise ValueError(f"Fighter {fighter_id} not found.")
        wins, losses, draws = int(wins or 0), int(losses or 0), int(draws or 0)
        if min(wins, losses, draws) < 0:
            raise ValueError("Bout counts cannot be negative.")
        if wins + losses + draws == 0:
            raise ValueError("Declared experience must include at least one bout.")
        if last_bout_date:
            try:
                _date.fromisoformat(str(last_bout_date)[:10])
            except ValueError:
                raise ValueError("last_bout_date must be an ISO date (YYYY-MM-DD).")

        row = PriorExperience.query.filter_by(fighter_id=fighter_id, sport=sport).first()
        if row is None:
            row = PriorExperience(fighter_id=fighter_id, sport=sport,
                                  created_at=datetime.utcnow())
            db.session.add(row)
        row.wins, row.losses, row.draws = wins, losses, draws
        row.last_bout_date = last_bout_date or None
        row.note = note or None
        db.session.commit()
        return row.to_dict()

    def delete_prior_experience(self, fighter_id: int, entry_id: int) -> None:
        row = PriorExperience.query.filter_by(id=entry_id, fighter_id=fighter_id).first()
        if not row:
            raise ValueError(f"Prior experience entry {entry_id} not found.")
        db.session.delete(row)
        db.session.commit()

    # ── cross-sport experience ─────────────────────────────────────────────

    @staticmethod
    def _histories_for(fighter_ids: list[int]) -> dict[int, list[dict]]:
        """All fight histories in one query — the matchmaker needs the whole
        pool, and fetching them one fighter at a time is an N+1."""
        out: dict[int, list[dict]] = {fid: [] for fid in fighter_ids}
        if not fighter_ids:
            return out
        for h in FightHistory.query.filter(
            FightHistory.fighter_id.in_(fighter_ids)
        ).all():
            out[h.fighter_id].append(h.to_dict())
        return out

    @staticmethod
    def _last_bout_dates(fighter_ids: list[int]) -> dict[int, str]:
        if not fighter_ids:
            return {}
        rows = (db.session.query(FightHistory.fighter_id,
                                 db.func.max(FightHistory.fight_date))
                .filter(FightHistory.fighter_id.in_(fighter_ids))
                .group_by(FightHistory.fighter_id).all())
        return {fid: last for fid, last in rows}

    @staticmethod
    def _native_elo_pool(sport: str) -> dict[int, float]:
        """Unseeded ratings for a whole discipline.

        This is the basis for transfer credit into *other* disciplines, and is
        deliberately unseeded: seeding from an already-seeded rating would let
        credit chain across three sports and compound.
        """
        from .matchmaker import compute_elo_for_pool
        pool = Fighter.query.filter_by(sport=sport).all()
        if not pool:
            return {}
        ids = [f.id for f in pool]
        return compute_elo_for_pool([f.to_dict() for f in pool],
                                    FighterService._histories_for(ids))

    def experience_sources(self, fighter_ids: list[int]) -> dict[int, list[dict]]:
        """Each fighter's record in disciplines other than this one.

        Two origins: profiles owned by the same user account, and experience
        declared by a coach for fighters who have no account. Costs nothing
        extra when nobody in the pool has a cross-sport history.
        """
        sources: dict[int, list[dict]] = {fid: [] for fid in fighter_ids}
        if not fighter_ids:
            return sources

        fighters = Fighter.query.filter(Fighter.id.in_(fighter_ids)).all()
        user_ids = {f.user_id for f in fighters if f.user_id}

        siblings = []
        if user_ids:
            siblings = Fighter.query.filter(
                Fighter.user_id.in_(user_ids),
                Fighter.sport != self.sport,
            ).all()

        if siblings:
            elo_by_sport = {s: self._native_elo_pool(s)
                            for s in {sib.sport for sib in siblings}}
            last_dates = self._last_bout_dates([sib.id for sib in siblings])
            by_owner: dict[int, list] = {}
            for sib in siblings:
                by_owner.setdefault(sib.user_id, []).append(sib)

            for f in fighters:
                if not f.user_id:
                    continue
                for sib in by_owner.get(f.user_id, []):
                    if sib.id == f.id:
                        continue
                    rec = sib.record
                    sources[f.id].append({
                        "sport":          sib.sport,
                        "wins":           rec.wins   if rec else 0,
                        "losses":         rec.losses if rec else 0,
                        "draws":          rec.draws  if rec else 0,
                        "elo":            elo_by_sport.get(sib.sport, {}).get(sib.id),
                        "last_bout_date": last_dates.get(sib.id),
                        "fighter_id":     sib.id,
                    })

        for pe in PriorExperience.query.filter(
            PriorExperience.fighter_id.in_(fighter_ids)
        ).all():
            if pe.sport == self.sport:
                continue
            sources[pe.fighter_id].append({
                "sport":          pe.sport,
                "wins":           pe.wins,
                "losses":         pe.losses,
                "draws":          pe.draws,
                "elo":            None,   # declared, never fought here
                "last_bout_date": pe.last_bout_date,
                "declared":       True,
            })
        return sources

    def elo_pool(self) -> dict[int, float]:
        """Ratings for every fighter in this discipline, with cross-sport
        experience seeded in — so the rating shown on a profile, on the rankings
        page and inside matchmaking are all the same number."""
        from .matchmaker import compute_elo_for_pool, experience_credit
        pool = Fighter.query.filter_by(sport=self.sport).all()
        if not pool:
            return {}
        ids       = [f.id for f in pool]
        histories = self._histories_for(ids)
        sources   = self.experience_sources(ids)
        seeds = {}
        for fid in ids:
            credit = experience_credit(sources.get(fid, []), self.sport)
            if credit["elo_seed"] is not None:
                seeds[fid] = credit["elo_seed"]
        return compute_elo_for_pool([f.to_dict() for f in pool], histories, seeds)

    # ── matchmaking ────────────────────────────────────────────────────────

    def get_matches(self, fighter_id: int,
                    include_ineligible: bool = False) -> list[dict]:
        from .matchmaker import rank_opponents
        fighter = Fighter.query.filter_by(id=fighter_id, sport=self.sport).first()
        if not fighter:
            raise ValueError(f"Fighter {fighter_id} not found.")
        pool      = Fighter.query.filter_by(sport=self.sport).all()
        ids       = [f.id for f in pool]
        histories = self._histories_for(ids)
        sources   = self.experience_sources(ids)
        candidates = [
            {"fighter": f.to_dict(), "history": histories.get(f.id, [])}
            for f in pool if f.id != fighter_id
        ]
        return rank_opponents(
            fighter.to_dict(), histories.get(fighter_id, []), candidates,
            sport=self.sport, sources=sources,
            include_ineligible=include_ineligible,
        )

    # ── event bouts ────────────────────────────────────────────────────────

    def add_bout(self, event_id: str, fighter_a_id: int, fighter_b_id: int,
                 description: str = None, ruleset: str = None) -> dict:
        for fid in (fighter_a_id, fighter_b_id):
            if not Fighter.query.filter_by(id=fid).first():
                raise ValueError(f"Fighter {fid} not found.")
        existing = EventBout.query.filter(
            EventBout.event_id == str(event_id),
            db.or_(
                db.and_(EventBout.fighter_a_id == fighter_a_id,
                        EventBout.fighter_b_id == fighter_b_id),
                db.and_(EventBout.fighter_a_id == fighter_b_id,
                        EventBout.fighter_b_id == fighter_a_id),
            )
        ).first()
        if existing:
            raise ValueError("This matchup already exists on the event card.")
        a = Fighter.query.filter_by(id=fighter_a_id).first()
        b = Fighter.query.filter_by(id=fighter_b_id).first()
        # Checked here rather than only in the blueprint so no route, script or
        # future caller can put a mixed bout on a card.
        if a.gender and b.gender and a.gender != b.gender:
            raise ValueError(
                f"{a.name} and {b.name} cannot be matched: "
                f"{a.name} is {a.gender} and {b.name} is {b.gender}.")
        bout = EventBout(
            event_id=str(event_id),
            sport=self.sport,
            fighter_a_id=fighter_a_id,
            fighter_b_id=fighter_b_id,
            description=description,
            ruleset=ruleset or None,
            created_at=datetime.utcnow(),
        )
        db.session.add(bout)
        # clear pending registrations for both fighters at this event
        EventRegistration.query.filter(
            EventRegistration.event_id == str(event_id),
            EventRegistration.fighter_id.in_([fighter_a_id, fighter_b_id]),
        ).delete(synchronize_session=False)
        db.session.commit()
        return bout.to_dict()

    def get_bout(self, bout_id: int) -> dict | None:
        bout = db.session.get(EventBout, bout_id)
        return bout.to_dict() if bout else None

    def complete_bout(self, bout_id: int, result: str, method: str = "Decision",
                      fight_date: str = None) -> dict:
        """Check a bout off as complete on the event card. Records the result in
        both fighters' histories, attributed to the event it was listed on."""
        result = (result or "").upper()
        if result not in ("A", "B", "D"):
            raise ValueError("Result must be 'A', 'B', or 'D'.")
        bout = db.session.get(EventBout, bout_id)
        if not bout:
            raise ValueError(f"Bout {bout_id} not found.")
        if bout.completed:
            raise ValueError("This bout has already been marked complete.")
        fa = db.session.get(Fighter, bout.fighter_a_id)
        fb = db.session.get(Fighter, bout.fighter_b_id)
        if not fa or not fb:
            raise ValueError("Both fighters must still exist to complete this bout.")
        method     = method or "Decision"
        fight_date = fight_date or str(_date.today())
        event_id   = self._event_pk(bout)
        side_a, side_b = {"A": ("W", "L"), "B": ("L", "W"), "D": ("D", "D")}[result]
        for fighter, opponent, res in ((fa, fb, side_a), (fb, fa, side_b)):
            db.session.add(FightHistory(
                fighter_id=fighter.id,
                opponent_name=opponent.name,
                opponent_id=opponent.id,
                result=res,
                method=method,
                fight_date=fight_date,
                ruleset=bout.ruleset,
                event_id=event_id,
            ))
            rec = fighter.record
            if rec is None:
                rec = FighterRecord(fighter_id=fighter.id)
                db.session.add(rec)
            if res == "W": rec.wins   += 1
            if res == "L": rec.losses += 1
            if res == "D": rec.draws  += 1
        self._stamp_bout(bout, result, method, fight_date)
        db.session.commit()
        return bout.to_dict()

    def _find_card_bout(self, fighter_id: int, opponent_id: int = None,
                        opponent_name: str = None) -> EventBout | None:
        """Find the bout on an event card matching this matchup, so a logged fight
        can be attributed to the event it took place at. Prefers a bout that has
        not been checked off as complete yet, then the most recently added."""
        if not opponent_id and not opponent_name:
            return None
        bouts = (EventBout.query
                 .filter(EventBout.sport == self.sport,
                         db.or_(EventBout.fighter_a_id == fighter_id,
                                EventBout.fighter_b_id == fighter_id))
                 .order_by(EventBout.completed, EventBout.created_at.desc())
                 .all())
        target_name = opponent_name.strip().lower() if opponent_name else None
        for b in bouts:
            is_a     = b.fighter_a_id == fighter_id
            other_id = b.fighter_b_id if is_a else b.fighter_a_id
            if opponent_id:
                if other_id == opponent_id:
                    return b
                continue
            other = b.fighter_b if is_a else b.fighter_a
            if other and other.name.strip().lower() == target_name:
                return b
        return None

    @staticmethod
    def _event_pk(bout: EventBout) -> int | None:
        """EventBout.event_id is text for legacy reasons — resolve it to a real
        Event row, or None if it points at a client-generated id."""
        try:
            pk = int(bout.event_id)
        except (TypeError, ValueError):
            return None
        return pk if db.session.get(Event, pk) else None

    @staticmethod
    def _bout_result(bout: EventBout, fighter_id: int, result: str) -> str:
        """Translate one fighter's W/L/D into the card's A/B/D."""
        if result == "D":
            return "D"
        won  = result == "W"
        is_a = bout.fighter_a_id == fighter_id
        return "A" if won == is_a else "B"

    @staticmethod
    def _stamp_bout(bout: EventBout, result: str, method: str, fight_date: str) -> None:
        bout.completed  = True
        bout.result     = result
        bout.method     = method
        bout.fight_date = fight_date

    def get_bouts_for_events(self, event_id: str) -> list[dict]:
        return [b.to_dict() for b in
                EventBout.query.filter_by(event_id=str(event_id))
                               .filter_by(sport=self.sport)
                               .order_by(EventBout.created_at).all()]

    def delete_bout(self, bout_id: int) -> None:
        bout = db.session.get(EventBout, bout_id)
        if not bout:
            raise ValueError(f"Bout {bout_id} not found.")
        db.session.delete(bout)
        db.session.commit()

    # ── event registrations ────────────────────────────────────────────────

    def register_fighter_for_event(self, event_id: str, fighter_id: int) -> dict:
        if not Fighter.query.filter_by(id=fighter_id).first():
            raise ValueError(f"Fighter {fighter_id} not found.")
        if EventRegistration.query.filter_by(
            event_id=str(event_id), fighter_id=fighter_id
        ).first():
            raise ValueError("This fighter is already registered for this event.")
        reg = EventRegistration(
            event_id=str(event_id),
            fighter_id=fighter_id,
            sport=self.sport,
            registered_at=datetime.utcnow(),
        )
        db.session.add(reg)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValueError("This fighter is already registered for this event.")
        return reg.to_dict()

    def get_registration(self, reg_id: int) -> dict | None:
        reg = db.session.get(EventRegistration, reg_id)
        return reg.to_dict() if reg else None

    def get_event_registrations(self, event_id: str) -> list[dict]:
        return [r.to_dict() for r in
                EventRegistration.query.filter_by(
                    event_id=str(event_id), sport=self.sport
                ).order_by(EventRegistration.registered_at).all()]

    def remove_registration(self, reg_id: int) -> None:
        reg = db.session.get(EventRegistration, reg_id)
        if not reg:
            raise ValueError(f"Registration {reg_id} not found.")
        db.session.delete(reg)
        db.session.commit()
