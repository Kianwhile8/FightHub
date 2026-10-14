"""migrate_sqlite_to_pg.py
------------------------
LEGACY, one-time migration from the old SQLite files (data/*.db) to
PostgreSQL. Only needed when moving data from the pre-Postgres version of the
app; a fresh install does not use it.

Run AFTER `flask db upgrade` has created all tables:

    python migration/migrate_sqlite_to_pg.py

Environment variables read from .env:
    DATABASE_URL   — target PostgreSQL connection string
    SQLITE_DIR     — directory containing the .db files (default: ./data)
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg2
import psycopg2.extras

SQLITE_DIR  = Path(os.environ.get("SQLITE_DIR", ROOT / "data"))
DATABASE_URL = os.environ.get("DATABASE_URL")

SPORTS = ("kickboxing", "mma", "boxing")

# ── seed venues (from the three hardcoded entries in loadLocalData()) ───────

SEED_VENUES = [
    {"name": "Madison Square Garden", "address": "4 Pennsylvania Plaza", "city": "New York",    "capacity": 20789},
    {"name": "MGM Grand Garden Arena", "address": "3799 S Las Vegas Blvd", "city": "Las Vegas", "capacity": 17157},
    {"name": "O2 Arena",              "address": "Peninsula Square",       "city": "London",    "capacity": 20000},
]


def open_sqlite(filename: str) -> sqlite3.Connection:
    path = SQLITE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"SQLite file not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def migrate(pg: psycopg2.extensions.connection) -> None:
    cur = pg.cursor()

    # ── 1. Gyms (from auth.db) ──────────────────────────────────────────
    print("Migrating gyms...")
    auth = open_sqlite("auth.db")
    gyms = auth.execute("SELECT * FROM gyms ORDER BY id").fetchall()
    gym_id_map: dict[int, int] = {}        # old_sqlite_id → new_pg_id
    gym_old_coach_map: dict[int, int] = {} # new_pg_id → old_sqlite_user_id

    for g in gyms:
        cur.execute(
            """INSERT INTO gyms (name, location, coach_id, created_at)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (g["name"], g["location"], None,   # NULL until users are inserted (step 4)
             g["created_at"] or datetime.utcnow().isoformat()),
        )
        new_id = cur.fetchone()[0]
        gym_id_map[g["id"]] = new_id
        if g["coach_id"]:
            gym_old_coach_map[new_id] = g["coach_id"]
    pg.commit()
    print(f"  {len(gyms)} gyms inserted.")

    # ── 2. Fighters (from sport DBs, add sport column) ──────────────────
    print("Migrating fighters...")
    # old (sport, old_id) → new_pg_id
    fighter_id_map: dict[tuple[str, int], int] = {}

    for sport in SPORTS:
        sport_db = open_sqlite(f"{sport}.db")
        fighters = sport_db.execute(
            "SELECT f.id, f.name, f.age, f.weight, f.gym_id, r.wins, r.losses, r.draws "
            "FROM fighters f JOIN records r ON r.fighter_id = f.id"
        ).fetchall()

        for f in fighters:
            old_gym = f["gym_id"]
            new_gym = gym_id_map.get(old_gym) if old_gym else None

            cur.execute(
                """INSERT INTO fighters (name, age, weight, sport, gym_id, created_at)
                   VALUES (%s, %s, %s, %s, %s, NOW()) RETURNING id""",
                (f["name"], f["age"], f["weight"], sport, new_gym),
            )
            new_id = cur.fetchone()[0]
            fighter_id_map[(sport, f["id"])] = new_id

            # fighter record
            cur.execute(
                """INSERT INTO fighter_records (fighter_id, wins, losses, draws)
                   VALUES (%s, %s, %s, %s)""",
                (new_id, f["wins"], f["losses"], f["draws"]),
            )

        pg.commit()
        print(f"  {len(fighters)} {sport} fighters inserted.")

    # ── 3. Fight history ────────────────────────────────────────────────
    print("Migrating fight history...")
    total_fights = 0

    for sport in SPORTS:
        sport_db = open_sqlite(f"{sport}.db")
        fights = sport_db.execute(
            "SELECT * FROM fight_history ORDER BY id"
        ).fetchall()

        for fh in fights:
            new_fid = fighter_id_map.get((sport, fh["fighter_id"]))
            if new_fid is None:
                print(f"  WARN: no mapping for {sport} fighter {fh['fighter_id']}, skipping fight {fh['id']}")
                continue
            cur.execute(
                """INSERT INTO fight_history
                     (fighter_id, opponent_name, result, method, fight_date)
                   VALUES (%s, %s, %s, %s, %s)""",
                (new_fid, fh["opponent_name"], fh["result"],
                 fh["method"], fh["date"]),
            )
            total_fights += 1

        pg.commit()

    print(f"  {total_fights} fight records inserted.")

    # ── 4. Users (from auth.db) ─────────────────────────────────────────
    print("Migrating users...")
    users = auth.execute("SELECT * FROM users ORDER BY id").fetchall()

    for u in users:
        old_sport = u["fighter_sport"]
        old_fid   = u["fighter_id"]
        new_fid   = fighter_id_map.get((old_sport, old_fid)) if (old_sport and old_fid) else None

        cur.execute(
            """INSERT INTO users
                 (email, password_hash, role, fighter_id, fighter_sport,
                  hide_record, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (u["email"], u["password_hash"], u["role"], new_fid, old_sport,
             bool(u["hide_record"]), u["created_at"] or datetime.utcnow().isoformat()),
        )

    pg.commit()
    print(f"  {len(users)} users inserted.")

    # ── 5. Seed venues ──────────────────────────────────────────────────
    print("Seeding venues...")
    for v in SEED_VENUES:
        cur.execute(
            "SELECT id FROM venues WHERE name=%s", (v["name"],)
        )
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO venues (name, address, city, capacity)
                   VALUES (%s, %s, %s, %s)""",
                (v["name"], v["address"], v["city"], v["capacity"]),
            )
    pg.commit()
    print(f"  {len(SEED_VENUES)} venues seeded.")

    # ── 6. Update gym coach_id references ───────────────────────────────
    # Gyms were inserted with coach_id=NULL. Now remap using email as the
    # stable key: old_sqlite_user_id → email → new_pg_user_id.
    print("Remapping gym coach_id to new user IDs...")
    sqlite_user_email = {u["id"]: u["email"] for u in users}
    cur.execute("SELECT id, email FROM users")
    pg_users = {row[1]: row[0] for row in cur.fetchall()}

    for new_gym_id, old_coach_id in gym_old_coach_map.items():
        email = sqlite_user_email.get(old_coach_id)
        new_uid = pg_users.get(email) if email else None
        if new_uid:
            cur.execute("UPDATE gyms SET coach_id=%s WHERE id=%s", (new_uid, new_gym_id))
        else:
            print(f"  WARN: no user match for old coach_id={old_coach_id}, gym {new_gym_id} left without coach")
    pg.commit()
    print("  Done.")

    # ── 7. Finalise ─────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM fighters"); print(f"\nFighters in PG: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM users");    print(f"Users in PG:    {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM gyms");     print(f"Gyms in PG:     {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM fight_history"); print(f"Fights in PG:   {cur.fetchone()[0]}")
    print("\nMigration complete.")


if __name__ == "__main__":
    if not DATABASE_URL:
        sys.exit("DATABASE_URL not set in .env")

    print("Connecting to PostgreSQL...")
    pg = psycopg2.connect(DATABASE_URL)
    try:
        migrate(pg)
    except Exception as e:
        pg.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        pg.close()
