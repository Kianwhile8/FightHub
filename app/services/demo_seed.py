"""Demonstration data that can be removed cleanly afterwards.

Every row the seeder creates is recorded in `demo_records`, so `clear-demo`
removes precisely what was seeded and cannot touch a real gym, fighter or
event. Run the seeder twice and you get two independent runs, each removable on
its own.

The data is shaped to exercise the parts of the UI that are hard to judge when
empty: fights spread over several months so the history groups into months,
events on both sides of today so the Upcoming/Previous split has something in
each, and fighters at a range of experience levels so rankings and matchmaking
produce a spread rather than a flat list.
"""

import random
import uuid
from datetime import date, datetime, timedelta

from ..extensions import db
from ..models.demo import DemoRecord
from ..models.event import Event, EventBout, Venue
from ..models.fight import FightHistory
from ..models.fighter import Fighter, FighterRecord, PriorExperience
from ..models.gym import Gym
from ..models.user import User

# Fixed so repeated runs are comparable and a demo can be re-created as it was.
SEED = 20260918

VENUES = [
    ("Phoenix Centre",      "Charlton Road",   "Andover",    800),
    ("Guildhall",           "High Street",     "Winchester", 1200),
    ("Mountbatten Leisure", "Alec Rose Lane",  "Portsmouth", 1500),
]

# (gym name, town, county)
GYMS = [
    ("Kyokushin Andover",  "Andover",    "Hampshire"),
    ("Southcoast Boxing",  "Portsmouth", "Hampshire"),
    ("Meridian MMA",       "Reading",    "Berkshire"),
    ("Iron Gate Muay Thai", "Guildford", "Surrey"),
]

FIRST = ["Aisha", "Dev", "Rowan", "Mika", "Tomasz", "Priya", "Callum", "Nadia",
         "Femi", "Elena", "Jonah", "Saoirse", "Kofi", "Marta", "Ilias", "Bea",
         "Hana", "Otis", "Yusuf", "Greta"]
LAST = ["Okafor", "Lindqvist", "Marchetti", "Bahri", "Novak", "Ferreira",
        "Adeyemi", "Kowalski", "Rahimi", "Duarte", "Benali", "Sorensen",
        "Varga", "Iqbal", "Mensah", "Petrov", "Laurent", "Nakagawa"]

METHODS = ["Decision", "TKO", "KO", "Submission", "Split Decision", "Unanimous Decision"]

SPORT_GYM = {
    "kickboxing": 0,
    "boxing":     1,
    "mma":        2,
    "muaythai":   3,
}


class DemoSeeder:
    def __init__(self, run_id: str = None):
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.rng = random.Random(SEED)
        self.counts = {}

    # ── manifest ──────────────────────────────────────────────────────────

    def _track(self, entity: str, entity_id: int) -> int:
        db.session.add(DemoRecord(run_id=self.run_id, entity=entity,
                                  entity_id=entity_id, created_at=datetime.utcnow()))
        self.counts[entity] = self.counts.get(entity, 0) + 1
        return entity_id

    # ── build ─────────────────────────────────────────────────────────────

    def run(self) -> dict:
        venues   = self._venues()
        coaches  = self._coaches()
        gyms     = self._gyms(coaches)
        fighters = self._fighters(gyms)
        self._fights(fighters)
        self._events(venues, fighters)
        db.session.commit()
        return {"run_id": self.run_id, "counts": self.counts}

    def _venues(self) -> list:
        out = []
        for name, address, city, capacity in VENUES:
            v = Venue(name=f"{name} (demo)", address=address, city=city, capacity=capacity)
            db.session.add(v)
            db.session.flush()
            self._track("venue", v.id)
            out.append(v)
        return out

    def _coaches(self) -> list:
        """Demo coaches own the demo gyms, so the roster screens look real.

        The addresses are on example.com, which is reserved by RFC 2606 and can
        never belong to a real person — a demo account must not be able to
        receive mail or collide with a genuine sign-up.

        They are given an unusable password hash rather than a known one: these
        are display fixtures, not accounts anyone should be able to log into.
        """
        out = []
        for i, (gym_name, _, _) in enumerate(GYMS):
            u = User(
                # The run id keeps a second seeding from colliding with the
                # first on the unique email index.
                email=f"demo.coach{i + 1}.{self.run_id}@example.com",
                password_hash="!demo-account-no-login",
                role="coach",
                terms_version=None,
                terms_accepted_at=None,
                created_at=datetime.utcnow(),
            )
            db.session.add(u)
            db.session.flush()
            self._track("user", u.id)
            out.append(u)
        return out

    def _gyms(self, coaches: list) -> list:
        out = []
        for (name, town, county), coach in zip(GYMS, coaches):
            g = Gym(name=f"{name} (demo)", location=town, county=county,
                    coach_id=coach.id, created_at=datetime.utcnow())
            db.session.add(g)
            db.session.flush()
            self._track("gym", g.id)
            out.append(g)
        return out

    def _fighters(self, gyms: list) -> dict:
        """Four per discipline: two male, two female.

        Two of each so every fighter has at least one valid opponent in their
        own division — with one of each, matchmaking would correctly return
        nothing and the demo would look broken.
        """
        by_sport = {}
        used = set()
        today = date.today()

        for sport, gym_index in SPORT_GYM.items():
            roster = []
            for n in range(4):
                while True:
                    name = f"{self.rng.choice(FIRST)} {self.rng.choice(LAST)}"
                    if name not in used:
                        used.add(name)
                        break
                age = self.rng.randint(19, 33)
                gender = "male" if n < 2 else "female"
                f = Fighter(
                    name=name,
                    date_of_birth=today.replace(year=today.year - age),
                    weight=round(self.rng.uniform(56, 93), 1),
                    sport=sport,
                    gender=gender,
                    gym_id=gyms[gym_index].id,
                    county=gyms[gym_index].county,
                    description="Demonstration fighter — safe to delete.",
                    created_at=datetime.utcnow(),
                )
                db.session.add(f)
                db.session.flush()
                db.session.add(FighterRecord(fighter_id=f.id))
                self._track("fighter", f.id)
                roster.append(f)
            by_sport[sport] = roster
        return by_sport

    def _fights(self, by_sport: dict) -> None:
        """Bouts spread back over ten months, so the history groups by month.

        Each bout is written from both fighters' points of view — that is how a
        real card reads, and it means the two records agree with each other
        instead of one side having a phantom win.
        """
        today = date.today()
        for sport, roster in by_sport.items():
            records = {f.id: db.session.get(FighterRecord, f.id) for f in roster}
            for months_ago in range(10, 0, -1):
                # Not every discipline has a bout every month.
                if self.rng.random() < 0.25:
                    continue
                # Same-division pairings only — the seeder must not create
                # data the application itself would refuse.
                division = self.rng.choice(["male", "female"])
                pool = [f for f in roster if f.gender == division]
                if len(pool) < 2:
                    continue
                a, b = self.rng.sample(pool, 2)
                when = today - timedelta(days=months_ago * 30 + self.rng.randint(0, 20))
                method = self.rng.choice(METHODS)
                roll = self.rng.random()
                res_a = "D" if roll < 0.12 else ("W" if roll < 0.56 else "L")
                res_b = {"W": "L", "L": "W", "D": "D"}[res_a]

                for fighter, opponent, result in ((a, b, res_a), (b, a, res_b)):
                    h = FightHistory(
                        fighter_id=fighter.id, opponent_name=opponent.name,
                        opponent_id=opponent.id, result=result, method=method,
                        fight_date=when.isoformat(), ruleset=None, event_id=None,
                    )
                    db.session.add(h)
                    db.session.flush()
                    self._track("fight", h.id)
                    rec = records[fighter.id]
                    if   result == "W": rec.wins   += 1
                    elif result == "L": rec.losses += 1
                    else:               rec.draws  += 1

    def _events(self, venues: list, by_sport: dict) -> None:
        """Three past events and two upcoming, so both tabs have content."""
        today = date.today()
        plan = [
            ("Southern Series 7",   -150, 0),
            ("Hampshire Open",       -80, 1),
            ("Winter Showcase",      -25, 2),
            ("Spring Classic",       +21, 0),
            ("Summer Invitational",  +75, 1),
        ]
        for name, offset, venue_index in plan:
            when = today + timedelta(days=offset)
            ev = Event(
                name=f"{name} (demo)",
                date=when.isoformat(),
                time="19:00",
                venue_id=venues[venue_index].id,
                description="Demonstration event — safe to delete.",
                created_at=datetime.utcnow(),
            )
            db.session.add(ev)
            db.session.flush()
            self._track("event", ev.id)

            # A couple of bouts on each card, drawn from one discipline.
            sport = self.rng.choice(list(by_sport))
            roster = by_sport[sport]
            for division in ("male", "female"):
                pool = [f for f in roster if f.gender == division]
                if len(pool) < 2:
                    continue
                a, b = self.rng.sample(pool, 2)
                bout = EventBout(
                    event_id=str(ev.id), sport=sport,
                    fighter_a_id=a.id, fighter_b_id=b.id,
                    description=None, ruleset=None,
                    created_at=datetime.utcnow(),
                    completed=False,
                )
                db.session.add(bout)
                db.session.flush()
                self._track("bout", bout.id)


# ── removal ───────────────────────────────────────────────────────────────

# Children before parents, or the foreign keys refuse.
DELETE_ORDER = ["fight", "bout", "registration", "fighter", "event", "gym",
                "venue", "user"]

MODELS = {
    "fight":    FightHistory,
    "bout":     EventBout,
    "fighter":  Fighter,
    "event":    Event,
    "gym":      Gym,
    "venue":    Venue,
    "user":     User,
}


def clear_demo(run_id: str = None) -> dict:
    """Delete seeded rows. With no run_id, every run is removed.

    Rows already deleted by hand are skipped rather than treated as an error —
    the point is to end up with the demo data gone, not to insist the database
    is exactly as the seeder left it.
    """
    q = DemoRecord.query
    if run_id:
        q = q.filter_by(run_id=run_id)
    records = q.all()

    by_entity = {}
    for r in records:
        by_entity.setdefault(r.entity, []).append(r.entity_id)

    removed = {}
    for entity in DELETE_ORDER:
        ids = by_entity.get(entity)
        model = MODELS.get(entity)
        if not ids or model is None:
            continue
        if entity == "fighter":
            # Both of these are declared ON DELETE CASCADE, but a bulk delete
            # goes straight to SQL and so relies on the database enforcing it —
            # which SQLite only does with the foreign_keys pragma on. Clearing
            # them explicitly makes removal independent of that.
            FighterRecord.query.filter(FighterRecord.fighter_id.in_(ids)).delete(
                synchronize_session=False)
            PriorExperience.query.filter(PriorExperience.fighter_id.in_(ids)).delete(
                synchronize_session=False)
        count = model.query.filter(model.id.in_(ids)).delete(synchronize_session=False)
        removed[entity] = count

    for r in records:
        db.session.delete(r)
    db.session.commit()
    return {"removed": removed, "runs": sorted({r.run_id for r in records})}


def list_runs() -> list:
    """Summarise the seed runs present, newest first."""
    rows = DemoRecord.query.order_by(DemoRecord.created_at.desc()).all()
    runs = {}
    for r in rows:
        entry = runs.setdefault(r.run_id, {"run_id": r.run_id, "created_at": r.created_at,
                                           "counts": {}})
        entry["counts"][r.entity] = entry["counts"].get(r.entity, 0) + 1
        entry["created_at"] = min(entry["created_at"], r.created_at)
    return sorted(runs.values(), key=lambda e: e["created_at"], reverse=True)
