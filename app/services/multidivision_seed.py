"""Test data for fighters who compete in more than one division.

`demo_seed.py` fills the app up so the screens look alive. This file does the
opposite: it builds the smallest cast that can answer a specific question —
what does the matchmaker do when a fighter's experience lives in a *different*
discipline from the one they are being matched in?

Everything here is deliberately controlled. Almost every fighter is 70.0 kg and
aged 24–29, so the weight factor (20 % of the score) and the age factor (3 %)
sit near 1.0 for every pairing and the cross-division machinery is what moves
the numbers. Where a fighter is off that weight it is on purpose and the name
says so.

The cast is organised as matched pairs, so each one is an A/B with a single
variable changed:

  Vane vs Ruiz        same 18-2 record crossing in opposite directions —
                      boxing→kickboxing (0.60) against kickboxing→boxing (0.45)
  Prosser vs Berrow   identical 20-5 boxing records, one fought eight years
                      ago and one three months ago — the decay half-life
  Adeyemi             credentials in two other disciplines at once — bouts add
                      up, the ELO seed does not (it takes the best, not the sum)
  Hlavac vs Pike      declared prior experience with no linked profile, so
                      bouts transfer but no rating does — muaythai (0.80)
                      against mma (0.50)
  Pace                a female crossover in a division where the best-scoring
                      opponents are male

Against them sits a ladder of natives in each division at 0, 4, 8, 12, 20 and
30 bouts, which is what the crossovers get ranked against.

Rows are recorded in `demo_records` exactly as the demo seeder does, so
`flask --app wsgi clear-demo --run <id>` removes precisely this fixture.
"""

import random
import uuid
from datetime import date, datetime, timedelta

from ..extensions import db
from ..models.demo import DemoRecord
from ..models.fight import FightHistory
from ..models.fighter import Fighter, FighterRecord, PriorExperience
from ..models.gym import Gym
from ..models.user import User

# Fixed so two runs produce the same fixture and a report can be compared
# against an earlier one.
SEED = 20260920

NOTE = "Multi-division test fixture — safe to delete."

# (gym name, town, county)
GYMS = [
    ("Crossover Athletic",   "Salford",    "Greater Manchester"),
    ("Two Sport Gym",        "Leytonstone", "Greater London"),
]

# How long ago a career ended, in days. `recent` is a fighter still competing;
# `stale` is one whose record is old enough for transfer decay to bite hard
# (eight years is ~4 half-lives, which lands under the 0.25 floor).
RECENCY = {
    "recent": 45,
    "mid":    400,
    "stale":  8 * 365,
}


def F(key, name, sport, record, *, gender="male", weight=70.0, age=26,
      recency="recent", owner=None, prior=(), note=""):
    """One fighter profile.

    `record` is the target (W, L, D) — the seeder writes real fight rows to
    match it, because ELO is computed from history and not from the stored
    record, and the two disagreeing would make every number here suspect.

    `owner` links profiles belonging to the same person: two specs sharing an
    owner key become two Fighter rows under one User, which is what
    `FighterService.experience_sources` follows to find a sibling division.

    `prior` is declared experience — (sport, wins, losses, draws, recency) —
    for a discipline the fighter has no profile in. It transfers bouts but no
    rating, because there is no history here to derive one from.
    """
    return {
        "key": key, "name": name, "sport": sport, "record": record,
        "gender": gender, "weight": weight, "age": age, "recency": recency,
        "owner": owner, "prior": list(prior), "note": note,
    }


# ── the cast ──────────────────────────────────────────────────────────────

FIGHTERS = [
    # ── kickboxing: the native ladder the crossovers are ranked against ────
    F("kb_deb_a", "Sam Oakley",      "kickboxing", (0, 0, 0), age=24,
      note="true debutant — control for debut protection"),
    F("kb_deb_b", "Ivan Dobrev",     "kickboxing", (0, 0, 0), age=25,
      note="second true debutant, so Oakley has one legal opponent"),
    F("kb_n4",   "Callum Reid",      "kickboxing", (3, 1, 0), age=25),
    F("kb_n8",   "Jonah Blake",      "kickboxing", (5, 2, 1)),
    F("kb_n12",  "Petr Novak",       "kickboxing", (8, 3, 1),
      note="12-bout native — the reference opponent"),
    F("kb_n20",  "Luka Marchetti",   "kickboxing", (14, 5, 1), age=27),
    F("kb_n30",  "Dwayne Ellis",     "kickboxing", (21, 8, 1), age=28),

    # Weight twins of kb_n12: same record, same age, different scale.
    F("kb_heavy", "Otis Crane",      "kickboxing", (8, 3, 1), weight=78.0,
      note="record twin of Novak at +8 kg"),
    F("kb_light", "Ilias Benali",    "kickboxing", (8, 3, 1), weight=62.0,
      note="record twin of Novak at -8 kg"),

    # ── the crossovers, all 0-0 natively in kickboxing ─────────────────────
    F("kb_vane", "Marcus Vane",      "kickboxing", (0, 0, 0), age=27,
      owner="vane",
      note="boxing 18-2 crossing in at 0.60"),
    F("kb_prosser", "Alan Prosser",  "kickboxing", (0, 0, 0), age=29,
      owner="prosser",
      note="boxing 20-5 that ended eight years ago"),
    F("kb_berrow", "Kyle Berrow",    "kickboxing", (0, 0, 0), age=29,
      owner="berrow",
      note="the same 20-5, still current"),
    F("kb_femi", "Femi Adeyemi",     "kickboxing", (0, 0, 0), age=27,
      owner="femi",
      note="credentials in two disciplines at once (mma + boxing)"),
    F("kb_hlavac", "Tomas Hlavac",   "kickboxing", (0, 0, 0),
      prior=[("muaythai", 14, 3, 0, "recent")],
      note="declared muaythai 14-3, no linked profile — bouts but no rating"),
    F("kb_pike", "Owen Pike",        "kickboxing", (0, 0, 0),
      prior=[("mma", 10, 2, 0, "recent")],
      note="declared mma 10-2, no linked profile — lower coefficient"),

    # The veteran side of the Ruiz pair lives here; his debut is in boxing.
    F("kb_ruiz", "Declan Ruiz",      "kickboxing", (18, 2, 0), age=27,
      owner="ruiz",
      note="kickboxing veteran whose second profile is a boxing debut"),

    # ── kickboxing, female division ────────────────────────────────────────
    F("kb_pace", "Rhiannon Pace",    "kickboxing", (0, 0, 0), gender="female",
      owner="pace",
      note="boxing 10-1 crossing in; her best-scoring peers are all male"),
    F("kb_ferreira", "Nadia Ferreira", "kickboxing", (5, 2, 0), gender="female"),
    F("kb_sato", "Hana Sato",        "kickboxing", (8, 3, 1), gender="female",
      age=27),

    # ── boxing: the ladder, plus the other half of each linked pair ────────
    F("bx_deb", "Nathan Cole",       "boxing", (0, 0, 0), age=24,
      note="true debutant — Ruiz should be filtered away from him"),
    F("bx_n4",  "Greg Sadler",       "boxing", (3, 1, 0), age=25),
    F("bx_n8",  "Dele Mensah",       "boxing", (5, 2, 1)),
    F("bx_n12", "Andre Laurent",     "boxing", (8, 3, 1)),
    F("bx_n20", "Ruben Duarte",      "boxing", (14, 5, 1), age=27),

    F("bx_vane", "Marcus Vane",      "boxing", (18, 2, 0), age=27,
      owner="vane", note="the record Vane carries into kickboxing"),
    F("bx_ruiz", "Declan Ruiz",      "boxing", (0, 0, 0), age=27,
      owner="ruiz", note="mirror of Vane — same 18-2, crossing the other way"),
    F("bx_prosser", "Alan Prosser",  "boxing", (20, 5, 0), age=29,
      recency="stale", owner="prosser",
      note="career ended eight years ago"),
    F("bx_berrow", "Kyle Berrow",    "boxing", (20, 5, 0), age=29,
      owner="berrow", note="same record, fought this year"),
    F("bx_femi", "Femi Adeyemi",     "boxing", (8, 1, 0), age=27, owner="femi"),
    F("bx_pace", "Rhiannon Pace",    "boxing", (10, 1, 0), gender="female",
      owner="pace"),

    # ── mma: Adeyemi's second credential, with peers to rate him against ───
    F("mma_femi", "Femi Adeyemi",    "mma", (12, 3, 0), age=27, owner="femi"),
    F("mma_n12", "Yusuf Rahimi",     "mma", (8, 3, 1), age=27),
    F("mma_n20", "Kofi Mensah",      "mma", (14, 5, 1), age=28),
]

# Bouts between two fighters in the cast, written from both sides so the two
# records agree. (winner, loser, method, days ago); a draw is result "D" for
# both, written as (a, b, method, days, "D").
HEAD_TO_HEAD = [
    ("kb_n8",   "kb_n4",   "Decision", 260),
    ("kb_n12",  "kb_n8",   "KO",       200),
    ("kb_n20",  "kb_n12",  "Decision", 150),
    ("kb_n30",  "kb_n20",  "TKO",      120),
    ("kb_ruiz", "kb_n30",  "Decision",  90),
    ("bx_vane", "bx_n20",  "KO",        95),
    ("bx_berrow", "bx_n12", "Decision", 100),
    ("mma_femi", "mma_n12", "Submission", 110),
]

METHODS_W = ["Decision", "Decision", "Decision", "TKO", "KO", "Submission"]
METHODS_L = ["Decision", "Decision", "Decision", "TKO", "KO"]

# Opponents from outside the cast. A fight against a name the pool does not
# know is rated against an unranked opponent, which is the ordinary case for a
# fighter whose career mostly happened elsewhere.
OUTSIDERS = [
    "Rhys Calloway", "Milos Dragic", "Tobias Renn", "Sami Belhadj",
    "Kwame Boateng", "Andrei Lupu", "Fabio Nardi", "Josh Trent",
    "Radek Simek", "Nico Barreto", "Emeka Obi", "Luis Salas",
    "Bram Visser", "Kenji Arai", "Pavel Horak", "Dion Whyte",
    "Aaron Fitzgerald", "Marek Zielinski", "Tevin Ross", "Hamza Cherif",
    "Gio Palermo", "Stefan Vuk", "Danny Okoro", "Ruaridh Bain",
    "Elias Haddad", "Vince Moreau", "Kasper Lund", "Ade Fashola",
]


class MultiDivisionSeeder:
    """Builds the cross-division fixture described in the module docstring.

    Use `MultiDivisionSeeder().run()` (or `flask seed-multidivision`). Rows are
    tracked in demo_records like DemoSeeder's.
    """

    def __init__(self, run_id: str = None):
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.rng = random.Random(SEED)
        self.counts = {}
        self.by_key = {}

    # ── manifest ──────────────────────────────────────────────────────────

    def _track(self, entity: str, entity_id: int) -> int:
        """Record a created row against this run, and count it."""
        db.session.add(DemoRecord(run_id=self.run_id, entity=entity,
                                  entity_id=entity_id, created_at=datetime.utcnow()))
        self.counts[entity] = self.counts.get(entity, 0) + 1
        return entity_id

    # ── build ─────────────────────────────────────────────────────────────

    def run(self) -> dict:
        """Create the whole fixture in one transaction. Returns run_id and counts."""
        gyms    = self._gyms(self._coach())
        owners  = self._owners()
        self._fighters(gyms, owners)
        self._fights()
        self._prior_experience()
        db.session.commit()
        return {"run_id": self.run_id, "counts": self.counts}

    def _coach(self) -> User:
        """One coach to own the fixture gyms.

        example.com is reserved by RFC 2606 and cannot belong to a real person,
        and the hash is unusable on purpose — this is a fixture, not an account
        anyone should be able to sign into.
        """
        u = User(email=f"multidiv.coach.{self.run_id}@example.com",
                 password_hash="!fixture-account-no-login",
                 role="coach", created_at=datetime.utcnow())
        db.session.add(u)
        db.session.flush()
        self._track("user", u.id)
        return u

    def _gyms(self, coach: User) -> list:
        """One Gym per entry in GYMS."""
        out = []
        for name, town, county in GYMS:
            g = Gym(name=f"{name} (multi-div)", location=town, county=county,
                    coach_id=coach.id, created_at=datetime.utcnow())
            db.session.add(g)
            db.session.flush()
            self._track("gym", g.id)
            out.append(g)
        return out

    def _owners(self) -> dict:
        """One User per person who holds profiles in more than one division.

        This account is the only thing tying two Fighter rows together —
        matchmaking finds a fighter's other disciplines by looking for profiles
        under the same user_id, so without it the two profiles are strangers
        who happen to share a name.
        """
        keys = sorted({f["owner"] for f in FIGHTERS if f["owner"]})
        owners = {}
        for key in keys:
            gender = next(f["gender"] for f in FIGHTERS if f["owner"] == key)
            u = User(email=f"multidiv.{key}.{self.run_id}@example.com",
                     password_hash="!fixture-account-no-login",
                     role="fighter", gender=gender, created_at=datetime.utcnow())
            db.session.add(u)
            db.session.flush()
            self._track("user", u.id)
            owners[key] = u
        return owners

    def _fighters(self, gyms: list, owners: dict) -> None:
        """Create a Fighter (and empty record) for every spec in FIGHTERS.

        Fills `self.by_key` so later steps can look fighters up by spec key.
        """
        today = date.today()
        for i, spec in enumerate(FIGHTERS):
            gym = gyms[i % len(gyms)]
            owner = owners.get(spec["owner"])
            f = Fighter(
                name=spec["name"],
                date_of_birth=today - timedelta(days=spec["age"] * 365),
                weight=spec["weight"],
                sport=spec["sport"],
                gender=spec["gender"],
                gym_id=gym.id,
                county=gym.county,
                user_id=owner.id if owner else None,
                description=f"{NOTE} {spec['note']}".strip(),
                created_at=datetime.utcnow(),
            )
            db.session.add(f)
            db.session.flush()
            db.session.add(FighterRecord(fighter_id=f.id))
            self._track("fighter", f.id)
            self.by_key[spec["key"]] = f

        # Point each owner's account at one of their profiles, the way
        # registration would. Which one is arbitrary; the link that matters for
        # matchmaking is Fighter.user_id, not this.
        for key, user in owners.items():
            primary = next(self.by_key[s["key"]] for s in FIGHTERS
                           if s["owner"] == key)
            user.fighter_id    = primary.id
            user.fighter_sport = primary.sport

    # ── fight histories ───────────────────────────────────────────────────

    def _fights(self) -> None:
        """Write real bouts totalling each fighter's target record.

        Head-to-heads inside the cast are written first, from both sides, then
        the remainder is filled in against outsiders. Doing it in that order is
        what keeps the stored record and the fight rows in agreement: the
        filler is whatever the target still needs once the linked bouts are
        counted, so the two can never drift apart.
        """
        today = date.today()
        used  = {}   # key -> [wins, losses, draws] already written
        rows  = {f["key"]: [] for f in FIGHTERS}

        for winner_key, loser_key, method, days in HEAD_TO_HEAD:
            when = (today - timedelta(days=days)).isoformat()
            rows[winner_key].append((self.by_key[loser_key], "W", method, when))
            rows[loser_key].append((self.by_key[winner_key], "L", method, when))
            used.setdefault(winner_key, [0, 0, 0])[0] += 1
            used.setdefault(loser_key,  [0, 0, 0])[1] += 1

        for spec in FIGHTERS:
            key = spec["key"]
            w, l, d = spec["record"]
            uw, ul, ud = used.get(key, [0, 0, 0])
            need = (w - uw, l - ul, d - ud)
            if min(need) < 0:
                raise ValueError(
                    f"{spec['name']} ({spec['sport']}): head-to-head bouts "
                    f"exceed the target record {spec['record']}"
                )
            rows[key].extend(self._filler(spec, need, len(rows[key])))

        for spec in FIGHTERS:
            fighter = self.by_key[spec["key"]]
            record  = db.session.get(FighterRecord, fighter.id)
            for opponent, result, method, when in rows[spec["key"]]:
                is_row = isinstance(opponent, Fighter)
                h = FightHistory(
                    fighter_id=fighter.id,
                    opponent_name=opponent.name if is_row else opponent,
                    opponent_id=opponent.id if is_row else None,
                    result=result, method=method, fight_date=when,
                )
                db.session.add(h)
                db.session.flush()
                self._track("fight", h.id)
                if   result == "W": record.wins   += 1
                elif result == "L": record.losses += 1
                else:               record.draws  += 1

    def _filler(self, spec: dict, need: tuple, already: int) -> list:
        """Bouts against outsiders, spread back over a plausible career.

        The span ends at the recency the spec asked for, which is the whole
        point of the stale/recent pairs: the last fight date is what transfer
        decay reads, so it has to be controlled rather than incidental.
        """
        w, l, d = need
        total = w + l + d
        if total == 0:
            return []

        results = ["W"] * w + ["L"] * l + ["D"] * d
        self.rng.shuffle(results)

        end    = RECENCY[spec["recency"]]
        span   = max(total * 55, 120)
        today  = date.today()

        out = []
        for i, result in enumerate(results):
            # Oldest first, ending `end` days ago.
            offset = end + int(span * (total - 1 - i) / max(total - 1, 1))
            when   = (today - timedelta(days=offset + self.rng.randint(0, 14))).isoformat()
            if result == "W":
                method = self.rng.choice(METHODS_W)
            elif result == "L":
                method = self.rng.choice(METHODS_L)
            else:
                method = "Draw"
            out.append((self.rng.choice(OUTSIDERS), result, method, when))
        return out

    # ── declared experience ───────────────────────────────────────────────

    def _prior_experience(self) -> None:
        """Add the declared (PriorExperience) records listed in each spec."""
        today = date.today()
        for spec in FIGHTERS:
            if not spec["prior"]:
                continue
            fighter = self.by_key[spec["key"]]
            for sport, w, l, d, recency in spec["prior"]:
                last = (today - timedelta(days=RECENCY[recency])).isoformat()
                db.session.add(PriorExperience(
                    fighter_id=fighter.id, sport=sport,
                    wins=w, losses=l, draws=d,
                    last_bout_date=last,
                    note=NOTE,
                    created_at=datetime.utcnow(),
                ))
        db.session.flush()
