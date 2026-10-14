#!/usr/bin/env python3
"""
seed_demo.py — Populate FightHub with synthetic demo data for video demonstration.

Usage:  python seed_demo.py
        python seed_demo.py --clear     # wipe non-admin data first

Creates:
  • 8 gyms across English counties
  • 60 fighters (boxing/kickboxing/mma) spanning 5 experience tiers
  • Realistic fight histories (beginner 0-3 → elite 55-80 bouts)
  • 5 events with venues and coloured banner images
"""

import os, sys, struct, zlib, random, argparse
from datetime import date, timedelta, datetime

# ── PNG generator (no Pillow required) ────────────────────────────────────────

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc    = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return length + tag + data + crc


def make_gradient_png(width: int, height: int,
                      top: tuple, bottom: tuple) -> bytes:
    """Return bytes of a vertical-gradient RGB PNG (no external deps)."""
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    rows = []
    for y in range(height):
        t   = y / max(height - 1, 1)
        r   = int(top[0] + t * (bottom[0] - top[0]))
        g   = int(top[1] + t * (bottom[1] - top[1]))
        b   = int(top[2] + t * (bottom[2] - top[2]))
        rows.append(bytes([0] + [r, g, b] * width))
    idat = _png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
    iend = _png_chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


# ── Data tables ────────────────────────────────────────────────────────────────

GYMS = [
    ("Kronk Boxing Academy",      "Ancoats",           "Greater Manchester"),
    ("Elite MMA London",          "Bethnal Green",     "Greater London"),
    ("Yorkshire Fight Centre",    "Beeston",           "West Yorkshire"),
    ("Midlands Combat Sports",    "Digbeth",           "West Midlands"),
    ("South Coast Combat",        "Hove",              "East Sussex"),
    ("Northern Steel Boxing",     "Gateshead",         "Tyne and Wear"),
    ("Merseyside MMA",            "Birkenhead",        "Merseyside"),
    ("Bristol Fight Factory",     "Bedminster",        "Bristol"),
]

# (name, date_str, time_str, city, venue_name, capacity, description, gradient_top, gradient_bottom)
EVENTS = [
    (
        "FightHub Fight Night I",
        "2025-06-14", "18:00",
        "Manchester", "Manchester Central Convention Complex", 3000,
        "The inaugural FightHub event. Eight bouts across boxing and kickboxing.",
        (20, 20, 80), (80, 10, 40),
    ),
    (
        "Northern Clash 2025",
        "2025-10-11", "19:00",
        "Newcastle upon Tyne", "Utilita Arena Newcastle", 8000,
        "Northern England's biggest amateur mixed-martial-arts night of the year.",
        (10, 60, 40), (5, 20, 80),
    ),
    (
        "FightHub Grand Prix",
        "2026-01-24", "17:30",
        "London", "ExCeL London", 5000,
        "Elite-tier national tournament. Eight-man GP bracket across three weight classes.",
        (120, 20, 20), (40, 0, 80),
    ),
    (
        "Spring Rumble 2026",
        "2026-04-19", "18:30",
        "Birmingham", "Resorts World Arena Birmingham", 4000,
        "Regional qualifier event. Top finishers earn selection for the Grand Prix.",
        (10, 80, 60), (0, 30, 90),
    ),
    (
        "Summer Showdown 2026",
        "2026-08-23", "19:00",
        "Brighton", "Brighton Centre", 3500,
        "Season finale. Championship belts on the line across all three disciplines.",
        (180, 120, 0), (160, 40, 0),
    ),
]

FIRST_NAMES = [
    "James","Oliver","Harry","Jack","George","Noah","Charlie","Jacob","Alfie","Freddie",
    "Ethan","Leo","Henry","Oscar","Theo","Liam","Mason","Logan","Lucas","Elijah",
    "Mohammed","Adam","Amir","Tariq","Rashid","Yusuf","Bilal","Zain","Kai","Ravi",
    "Connor","Ryan","Sean","Callum","Kieran","Patrick","Luca","Marco","Mateo","Javier",
    "Tyler","Jayden","Marcus","Darius","Leon","Tyrese","Kofi","Emmanuel","Zack","Dean",
]

LAST_NAMES = [
    "Smith","Jones","Williams","Taylor","Brown","Davies","Evans","Wilson","Thomas","Roberts",
    "Johnson","Walker","Wright","Thompson","White","Hughes","Edwards","Green","Hall","Wood",
    "Khan","Ali","Ahmed","Hussain","Patel","Singh","Sharma","Iqbal","Malik","Begum",
    "Murphy","O'Brien","Ryan","O'Sullivan","McCarthy","Kelly","Walsh","Burke","Brennan","Flynn",
    "Clarke","Mitchell","Turner","Robinson","Carter","Phillips","Baker","Morris","Harris","King",
]

METHODS_W = ["Decision", "Decision", "Decision", "KO", "TKO", "Submission", "RSC", "Points"]
METHODS_L = ["Decision", "Decision", "Decision", "KO", "TKO", "Submission", "RSC", "Points"]
METHODS_D = ["Draw"]

COUNTIES = [
    "Greater Manchester", "Greater London", "West Yorkshire", "West Midlands",
    "East Sussex", "Tyne and Wear", "Merseyside", "Bristol", "Lancashire",
    "South Yorkshire", "North Yorkshire", "Kent", "Essex", "Hampshire",
    "Nottinghamshire", "Leicestershire", "Staffordshire",
]

# Weight classes (kg) per sport
WEIGHT_CLASSES = {
    "boxing":     [51, 54, 57, 61, 64, 67, 71, 75, 81, 86, 92, 92],
    "kickboxing": [52, 56, 60, 64, 68, 72, 76, 84, 92, 92],
    "mma":        [52, 57, 61, 66, 70, 77, 84, 93, 120],
}

# (tier_label, bout_range, win_rate, draw_rate)
TIERS = [
    ("Beginner",     (0,  3),  0.50, 0.10),
    ("Novice",       (4,  15), 0.55, 0.08),
    ("Intermediate", (16, 35), 0.58, 0.07),
    ("Advanced",     (36, 55), 0.62, 0.06),
    ("Elite",        (56, 80), 0.65, 0.05),
]

# Fighters per (tier × sport) = 4  →  4 × 5 tiers × 3 sports = 60 fighters
FIGHTERS_PER_TIER = 4


# ── Helpers ────────────────────────────────────────────────────────────────────

rng = random.Random(42)   # fixed seed for reproducibility


def rand_name(used: set) -> str:
    for _ in range(500):
        n = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        if n not in used:
            used.add(n)
            return n
    return f"Fighter {len(used)}"


def rand_dob(min_age=18, max_age=38) -> date:
    days = rng.randint(min_age * 365, max_age * 365)
    return date.today() - timedelta(days=days)


def rand_fight_date(n_fights: int, fight_index: int) -> str:
    """Space fights evenly back in time (oldest first)."""
    total_days = n_fights * 60 + 30
    offset     = total_days - int((fight_index / max(n_fights - 1, 1)) * total_days)
    d          = date.today() - timedelta(days=offset + rng.randint(0, 30))
    return d.isoformat()


def build_history(n_fights: int, win_rate: float, draw_rate: float,
                  used_names: set) -> list[dict]:
    fights = []
    for i in range(n_fights):
        r_val = rng.random()
        if r_val < draw_rate:
            result, methods = "D", METHODS_D
        elif r_val < draw_rate + win_rate:
            result, methods = "W", METHODS_W
        else:
            result, methods = "L", METHODS_L
        fights.append({
            "opponent": rand_name(used_names),
            "result":   result,
            "method":   rng.choice(methods),
            "date":     rand_fight_date(n_fights, i),
        })
    return fights


# ── Main seed logic ────────────────────────────────────────────────────────────

def run(clear: bool = False):
    # Build Flask app and push context
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app import create_app
    app = create_app("development")

    with app.app_context():
        from app.extensions import db
        from app.models.user    import User
        from app.models.gym     import Gym
        from app.models.fighter import Fighter, FighterRecord
        from app.models.fight   import FightHistory
        from app.models.event   import Venue, Event

        upload_dir = app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)

        # ── optional clear ──────────────────────────────────────────────────
        if clear:
            print("Clearing existing demo data …")
            db.session.query(FightHistory).delete()
            db.session.query(FighterRecord).delete()
            db.session.query(Fighter).delete()
            # keep admin users, delete coaches/promoters added by seed
            db.session.query(User).filter(
                User.role.in_(["coach", "promoter"])
            ).delete(synchronize_session=False)
            db.session.query(Gym).delete()
            db.session.query(Event).delete()
            db.session.query(Venue).delete()
            db.session.commit()
            print("  Done.\n")

        # ── admin user (needed as coach_id placeholder) ─────────────────────
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            print("ERROR: No admin user found. Run the app once to seed the admin.")
            return

        # ── gyms ────────────────────────────────────────────────────────────
        print("Creating gyms …")
        gym_objs = []
        for (gname, gloc, gcounty) in GYMS:
            existing = Gym.query.filter_by(name=gname).first()
            if existing:
                gym_objs.append(existing)
                continue
            g = Gym(name=gname, location=gloc, county=gcounty,
                    coach_id=admin.id, created_at=datetime.utcnow())
            db.session.add(g)
            gym_objs.append(g)
        db.session.commit()
        print(f"  {len(gym_objs)} gyms ready.\n")

        # ── fighters ────────────────────────────────────────────────────────
        print("Creating fighters …")
        used_names: set = set(f.name for f in Fighter.query.all())
        total_created = 0

        for sport, weights in WEIGHT_CLASSES.items():
            for tier_label, (bout_min, bout_max), win_rate, draw_rate in TIERS:
                for _ in range(FIGHTERS_PER_TIER):
                    name   = rand_name(used_names)
                    dob    = rand_dob()
                    weight = float(rng.choice(weights))
                    county = rng.choice(COUNTIES)
                    gym    = rng.choice(gym_objs)

                    descriptions = [
                        f"{tier_label}-level {sport} competitor based in {county}.",
                        f"Trains out of {gym.name}. Competing since {dob.year + rng.randint(18,22)}.",
                        f"Hard-hitting {sport} fighter with a {tier_label.lower()} record.",
                        None,
                    ]

                    f = Fighter(
                        name=name, date_of_birth=dob, weight=weight,
                        sport=sport, gym_id=gym.id,
                        county=county,
                        description=rng.choice(descriptions),
                        created_at=datetime.utcnow(),
                    )
                    db.session.add(f)
                    db.session.flush()   # get f.id

                    n_fights = rng.randint(bout_min, bout_max)
                    history  = build_history(n_fights, win_rate, draw_rate, used_names)

                    wins = losses = draws = 0
                    for h in history:
                        fh = FightHistory(
                            fighter_id=f.id, opponent_name=h["opponent"],
                            result=h["result"], method=h["method"],
                            fight_date=h["date"],
                        )
                        db.session.add(fh)
                        if h["result"] == "W": wins   += 1
                        elif h["result"] == "L": losses += 1
                        else: draws += 1

                    rec = FighterRecord(fighter_id=f.id, wins=wins, losses=losses, draws=draws)
                    db.session.add(rec)
                    total_created += 1

        db.session.commit()
        print(f"  {total_created} fighters created across boxing / kickboxing / mma.\n")

        # ── venues & events ─────────────────────────────────────────────────
        print("Creating venues and events …")
        for (ename, edate, etime, ecity, vname, vcap,
             edesc, grad_top, grad_bottom) in EVENTS:

            if Event.query.filter_by(name=ename).first():
                print(f"  '{ename}' already exists, skipping.")
                continue

            venue = Venue.query.filter_by(name=vname).first()
            if not venue:
                venue = Venue(name=vname, city=ecity, capacity=vcap)
                db.session.add(venue)
                db.session.flush()

            ev = Event(
                name=ename, date=edate, time=etime,
                venue_id=venue.id, description=edesc,
                created_at=datetime.utcnow(),
            )
            db.session.add(ev)
            db.session.flush()

            # Generate a 800×300 gradient PNG banner and save as event photo
            img_bytes  = make_gradient_png(800, 300, grad_top, grad_bottom)
            img_name   = f"event_{ev.id}_banner.png"
            img_path   = os.path.join(upload_dir, img_name)
            with open(img_path, "wb") as fh:
                fh.write(img_bytes)
            ev.photo = img_name

            print(f"  Created '{ename}' -- banner saved as {img_name}")

        db.session.commit()
        print()

        # ── summary ─────────────────────────────────────────────────────────
        from sqlalchemy import func as sa_func
        n_gyms    = Gym.query.count()
        n_fighters= Fighter.query.count()
        n_fights  = FightHistory.query.count()
        n_events  = Event.query.count()

        print("=" * 50)
        print(f"  Gyms:     {n_gyms}")
        print(f"  Fighters: {n_fighters}")
        print(f"  Fights:   {n_fights}")
        print(f"  Events:   {n_events}")
        print("=" * 50)
        print("\nSeed complete. Refresh the app to see the data.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed FightHub demo data.")
    parser.add_argument("--clear", action="store_true",
                        help="Delete existing demo data before seeding.")
    args = parser.parse_args()
    run(clear=args.clear)
