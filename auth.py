'''user authentication for fighthub

handles registration, login, session management and role based access.
passwords are hashedf with werkzeug.
'''


import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


VALID_ROLES = ("fighter", "coach", "promoter", "admin")
VALID_SPORTS = ("kickboxing", "mma", "boxing", "muaythai")

class authDB:
    def __init__(self, db_dir: str = ".") -> None:
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "auth.db")
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()
        self._seed_admin()

    def __enter__(self): return self
    def __exit__(self,*_): self.close()

    def _create_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT    NOT NULL,
            role          TEXT    NOT NULL DEFAULT 'fighter'
                            CHECK (role IN ('fighter','coach','promoter','admin')),
            fighter_id    INTEGER,
            fighter_sport TEXT,
            created_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gyms (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            location   TEXT,
            coach_id   INTEGER NOT NULL,
            created_at TEXT    NOT NULL,
            FOREIGN KEY (coach_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
        self._conn.commit()
        try:
            self._conn.execute("ALTER TABLE users ADD COLUMN hide_record INTEGER NOT NULL DEFAULT 0")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass


        # creating admin account for manageing all sessions

    def _seed_admin(self) -> None:
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM users WHERE role ='admin' LIMIT 1")
        if cur.fetchone():
            return
        admin_email = os.environ.get("ADMIN_EMAIL")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            print("[AUTH] No admin seeded — set ADMIN_EMAIL and ADMIN_PASSWORD in .env to create one.")
            return
        self.register(email=admin_email, password=admin_password, role="admin")
        print(f"[AUTH] Admin account created: {admin_email}")

    
    @staticmethod
    def _row(row) -> dict | None:
        if row is None:
            return None
        return {
            "id":            row["id"],
            "email":         row["email"],
            "role":          row["role"],
            "fighter_id":    row["fighter_id"],
            "fighter_sport": row["fighter_sport"],
            "created_at":    row["created_at"],
            "hide_record":   bool(row["hide_record"]),
        }
    
    # creating registration function making sure the same email cant be used for multiple accounts
    
    def register(self, email: str, password:str, role:str, fighter_id: int = None, fighter_sport: str = None) -> dict:
        if role not in VALID_ROLES:
            raise ValueError (f"Invalid role '{role}'.")
        if len(password) < 8:
            raise ValueError ("password must be at least 8 characters long.")
        if fighter_sport and fighter_sport not in VALID_SPORTS:
            raise ValueError (f"invalid sport '{fighter_sport}'.")
        pw_hash = generate_password_hash(password)
        cur = self._conn.cursor()
        try:
            cur.execute ("""
                INSERT INTO users (email, password_hash, role, fighter_id, fighter_sport, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)
                         """, (email.strip().lower(), pw_hash, role,
                            fighter_id, fighter_sport, datetime.utcnow().isoformat()))
            self._conn.commit()
            return self.get_by_id(cur.lastrowid)
        except sqlite3.IntegrityError:
            raise ValueError (f"An account with that email already exists")
        

    def login (self, email: str, password: str) -> dict:
        cur = self._conn.cursor()
        cur.execute ("SELECT * FROM users WHERE email =?", (email.strip().lower(),))
        row = cur.fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            raise ValueError("Incorrect login details.")
        return self._row(row)
    
    def get_by_id(self, user_id: int) -> dict | None:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return self._row(cur.fetchone())
    
    def get_all_users(self) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute ("SELECT * FROM users ORDER BY created_at DESC")
        return [self._row(r) for r in cur.fetchall()]
    

    def update_role(self, user_id: int, new_role:str) -> dict:
        if new_role not in VALID_ROLES:
            raise ValueError (f"invalid role '{new_role}'")
        cur = self._conn.cursor()
        cur.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
        if cur.rowcount == 0:
            raise ValueError (f"user {user_id} not found")
        self._conn.commit()
        return self.get_by_id(user_id)
    

    def link_fighter(self, user_id: int, fighter_id: int, fighter_sport: str) -> dict:
        if fighter_sport not in VALID_SPORTS:
            raise ValueError(f"Invalid sport '{fighter_sport}'.")
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE fighter_id=? AND fighter_sport=? AND id != ?",
            (fighter_id, fighter_sport, user_id)
        )
        if cur.fetchone():
            raise ValueError("This fighter profile is already linked to another account.")
        cur.execute(
            "UPDATE users SET fighter_id=?, fighter_sport=? WHERE id=?",
            (fighter_id, fighter_sport, user_id)
        )
        self._conn.commit()
        return self.get_by_id(user_id)
    

    def delete_user(self,user_id: int) -> dict:
        cur = self._conn.cursor()
        cur.execute ("DELETE FROM users WHERE id=?", (user_id,))
        if cur.rowcount == 0:
            raise ValueError (f" user {user_id} not found")
        self._conn.commit()

    def change_password(self, user_id:int, old_password:str, new_password:str) -> dict:
        cur = self._conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("user not found.")
        if not check_password_hash(row["password_hash"], old_password):
            raise ValueError("current password is incorrect")
        cur.execute (
            "UPDATE users SET password_hash=? WHERE id=?",
            (generate_password_hash(new_password), user_id)
        )
        self._conn.commit()

    # gym management 


    @staticmethod
    def _gym_row(row) -> dict | None:
        if row is None:
            return None
        return{
            "id": row ["id"],
            "name": row["name"],
            "location": row["location"],
            "coach_id": row["coach_id"],
            "created_at": row["created_at"]
        }
    
    def create_gym(self,name:str, coach_id: int, location: str = None) -> dict:

        '''creates a gym owned by coach_id '''

        cur = self._conn.cursor()
        cur.execute ("SELECT id, role FROM users WHERE id=?", (coach_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError (f"user {coach_id} not found")
        if row ["role"] not in ("coach", "admin"):
            raise ValueError ("only coaches and admins can create gyms")
        cur.execute(
            "INSERT INTO gyms (name, location, coach_id, created_at) VALUES (?, ?, ?, ?)",
            (name.strip(), location, coach_id, datetime.utcnow().isoformat())
        )
        self._conn.commit()
        return self.get_gym(cur.lastrowid)
    
    def get_gym(self, gym_id: int) -> dict | None:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM gyms WHERE id=?", (gym_id,))
        return self._gym_row(cur.fetchone())
    
    def get_all_gyms_by_coach (self, coach_id: int) -> list[dict]:
        cur= self._conn.cursor()
        cur.execute("SELECT * FROM gyms WHERE coach_id=?", (coach_id,))
        return [self._gym_row(r) for r in cur.fetchall()]
    
    def get_all_gyms(self) -> list[dict]:
        cur= self._conn.cursor()
        cur.execute ("SELECT * FROM gyms ORDER BY name")
        return [self._gym_row(r) for r in cur.fetchall()]
    
    def update_gym (self, gym_id: int, coach_id: int, name: str = None, location: str = None) -> dict:
        gym = self._assert_gym_owner(gym_id, coach_id)
        cur = self._conn.cursor()
        cur.execute("UPDATE gyms SET name=?, location=? WHERE id=?", 
                    (name or gym["name"], location if location is not None else gym["location"], gym_id))
        self._conn.commit()
        return self.get_gym(gym_id)
    
    def delete_gym (self, gym_id: int, coach_id :int) -> None:
        self._assert_gym_owner(gym_id, coach_id)
        self._conn.execute("DELETE FROM gyms WHERE id=?", (gym_id,))
        self._conn.commit()


    def _assert_gym_owner(self, gym_id: int, coach_id:int) -> dict:
        gym = self.get_gym(gym_id)
        if not gym:
            raise ValueError(f"Gym {gym_id} not found")
        cur = self._conn.cursor()
        cur.execute("SELECT role FROM users WHERE id=?", (coach_id,))
        row = cur.fetchone()
        role = row["role"] if row else None
        if gym["coach_id"] != coach_id and role != "admin":
            raise ValueError ("you do not have permission to modify this gym")
        return gym
    
    def update_privacy(self, user_id: int, hide_record: bool) -> dict:
        cur = self._conn.cursor()
        cur.execute("UPDATE users SET hide_record=? WHERE id=?", (1 if hide_record else 0, user_id))
        if cur.rowcount == 0:
            raise ValueError(f"User {user_id} not found")
        self._conn.commit()
        return self.get_by_id(user_id)

    def get_hidden_fighter_ids(self, sport: str) -> set:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT fighter_id FROM users WHERE hide_record=1 AND fighter_sport=? AND fighter_id IS NOT NULL",
            (sport,)
        )
        return {row["fighter_id"] for row in cur.fetchall()}

    def close(self):
        self._conn.close()
    
     
