"""
fighter_database.py
-------------------
FighterDB — one instance per sport (kickboxing | mma | boxing).

Tables
------
fighters   — id, name, age, weight_kg
records    — fighter_id, wins, losses, draws          (1-to-1 with fighters)
fight_history — id, fighter_id, opponent_name, result, method, date
"""

import sqlite3
from datetime import date as _date


class FighterDB:
    VALID_SPORTS = ("kickboxing", "mma", "boxing")

    def __init__(self, sport: str, db_dir: str = ".") -> None:
        if sport not in self.VALID_SPORTS:
            raise ValueError(f"Invalid sport '{sport}'. Choose from: {self.VALID_SPORTS}")
        self.sport   = sport
        self.db_path = f"{db_dir}/{sport}.db"
        self._conn   = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    #  context manager 

    def __enter__(self):  return self
    def __exit__(self, *_): self.close()
    def __repr__(self):   return f"FighterDB(sport='{self.sport}')"

    #  schema 

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS fighters (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL,
                age     INTEGER NOT NULL CHECK(age >= 16),
                weight  REAL    NOT NULL CHECK(weight > 0)
            );

            CREATE TABLE IF NOT EXISTS records (
                fighter_id  INTEGER PRIMARY KEY,
                wins        INTEGER NOT NULL DEFAULT 0 CHECK(wins   >= 0),
                losses      INTEGER NOT NULL DEFAULT 0 CHECK(losses >= 0),
                draws       INTEGER NOT NULL DEFAULT 0 CHECK(draws  >= 0),
                FOREIGN KEY (fighter_id) REFERENCES fighters(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS fight_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                fighter_id    INTEGER NOT NULL,
                opponent_name TEXT    NOT NULL,
                result        TEXT    NOT NULL CHECK(result IN ('W','L','D')),
                method        TEXT    NOT NULL DEFAULT 'Decision',
                date          TEXT    NOT NULL,
                FOREIGN KEY (fighter_id) REFERENCES fighters(id) ON DELETE CASCADE
            );
        """)
        self._conn.commit()

    # ── helpers 

    @staticmethod
    def _fighter_row(row: tuple) -> dict:
        return {
            "id":        row[0],
            "name":      row[1],
            "age":       row[2],
            "weight_kg": row[3],
            "wins":      row[4],
            "losses":    row[5],
            "draws":     row[6],
        }

    #  fighter CRUD 

    def add_fighter(self, name: str, age: int, weight: float) -> int:
        """Insert a fighter and initialise their 0-0-0 record. Returns new ID."""
        cur = self._conn.cursor()
        cur.execute("INSERT INTO fighters (name, age, weight) VALUES (?,?,?)", (name, age, weight))
        fid = cur.lastrowid
        cur.execute("INSERT INTO records (fighter_id) VALUES (?)", (fid,))
        self._conn.commit()
        return fid

    def get_fighter(self, fighter_id: int) -> dict | None:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, f.name, f.age, f.weight, r.wins, r.losses, r.draws
            FROM fighters f JOIN records r ON r.fighter_id = f.id
            WHERE f.id = ?
        """, (fighter_id,))
        row = cur.fetchone()
        return self._fighter_row(row) if row else None

    def get_all_fighters(self) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, f.name, f.age, f.weight, r.wins, r.losses, r.draws
            FROM fighters f JOIN records r ON r.fighter_id = f.id
            ORDER BY f.name
        """)
        return [self._fighter_row(r) for r in cur.fetchall()]

    def search_fighters(self, query: str) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, f.name, f.age, f.weight, r.wins, r.losses, r.draws
            FROM fighters f JOIN records r ON r.fighter_id = f.id
            WHERE LOWER(f.name) LIKE LOWER(?)
            ORDER BY f.name
        """, (f"%{query}%",))
        return [self._fighter_row(r) for r in cur.fetchall()]

    def update_fighter(self, fighter_id: int, name: str = None,
                       age: int = None, weight: float = None) -> None:
        """Update any combination of name / age / weight."""
        fighter = self.get_fighter(fighter_id)
        if not fighter:
            raise ValueError(f"Fighter {fighter_id} not found.")
        cur = self._conn.cursor()
        cur.execute("""
            UPDATE fighters SET name=?, age=?, weight=? WHERE id=?
        """, (
            name   if name   is not None else fighter["name"],
            age    if age    is not None else fighter["age"],
            weight if weight is not None else fighter["weight_kg"],
            fighter_id,
        ))
        self._conn.commit()

    def delete_fighter(self, fighter_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM fighters WHERE id=?", (fighter_id,))
        if cur.rowcount == 0:
            raise ValueError(f"Fighter {fighter_id} not found.")
        self._conn.commit()

    #  record 

    def update_record(self, fighter_id: int,
                      wins: int = 0, losses: int = 0, draws: int = 0) -> None:
        """Increment wins/losses/draws by the given delta values."""
        cur = self._conn.cursor()
        cur.execute("""
            UPDATE records
            SET wins=wins+?, losses=losses+?, draws=draws+?
            WHERE fighter_id=?
        """, (wins, losses, draws, fighter_id))
        if cur.rowcount == 0:
            raise ValueError(f"No record for fighter {fighter_id}.")
        self._conn.commit()

    #  fight history 

    def add_fight(self, fighter_id: int, opponent_name: str,
                  result: str, method: str = "Decision",
                  fight_date: str = None) -> int:
        """
        Log a fight and automatically update the fighter's W/L/D record.
        uses result
        way of result e.g KO/ decision
        data of fight 

        """
        result = result.upper()
        if result not in ("W", "L", "D"):
            raise ValueError("result must be 'W', 'L', or 'D'")
        fight_date = fight_date or str(_date.today())
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO fight_history (fighter_id, opponent_name, result, method, date)
            VALUES (?,?,?,?,?)
        """, (fighter_id, opponent_name, result, method, fight_date))
        fight_id = cur.lastrowid
        self._conn.commit()
        # mirror into records table
        self.update_record(fighter_id,
                           wins=1   if result == "W" else 0,
                           losses=1 if result == "L" else 0,
                           draws=1  if result == "D" else 0)
        return fight_id

    def get_fight_history(self, fighter_id: int) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT id, opponent_name, result, method, date
            FROM fight_history WHERE fighter_id=?
            ORDER BY date DESC
        """, (fighter_id,))
        return [
            {"id": r[0], "opponent": r[1], "result": r[2],
             "method": r[3], "date": r[4]}
            for r in cur.fetchall()
        ]

    def get_all_fights(self) -> list[dict]:
        """Return every fight log in this sport's database."""
        cur = self._conn.cursor()
        cur.execute("""
            SELECT fh.id, f.name, fh.opponent_name, fh.result, fh.method, fh.date
            FROM fight_history fh
            JOIN fighters f ON f.id = fh.fighter_id
            ORDER BY fh.date DESC
        """)
        return [
            {"id": r[0], "fighter": r[1], "opponent": r[2],
             "result": r[3], "method": r[4], "date": r[5]}
            for r in cur.fetchall()
        ]

    # matchmaking 
    # Full algorithm lives in matchmaker.py.
    # gathers requried data and delegates to matchmaker.py

    def get_matches(self, fighter_id: int) -> list[dict]:
        """
        Return all other fighters ranked by compatibility score (0-100).
        Scoring is handled by matchmaker.rank_opponents() — see matchmaker.py
        for factor weights and full algorithm documentation.
        """
        from matchmaker import rank_opponents

        fighter = self.get_fighter(fighter_id)
        if not fighter:
            raise ValueError(f"Fighter {fighter_id} not found.")

        fighter_history = self.get_fight_history(fighter_id)

        candidates = [
            {
                "fighter": f,
                "history": self.get_fight_history(f["id"]),
            }
            for f in self.get_all_fighters()
            if f["id"] != fighter_id
        ]

        return rank_opponents(fighter, fighter_history, candidates)

    #  housekeeping 

    def close(self) -> None:
        self._conn.close()