import sqlite3
import os







"""creating database file paths"""

DB_PATHS ={
    "kickboxing": "kickboxing.db",
    "boxing": "boxing.db",
    "mma": "mma.db"
}



def create_tables(sport: str) -> sqlite3.connection:

    """creating tables for each sport"""


    conn = sqlite3.connect(DB_PATHS[sport])
    cursor = conn.cursor()

    cursor.execute(f"""CREATE TABLE IF NOT EXISTS {sport}_fighters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL check (age > 16),
        weight real NOT NULL,, check (weight > 0), -- kilograms,
        height real NOT NULL, check (height > 0), -- centimeters,
    );
                
    create table if not exists records (
        id integer primary key autoincrement,
        fighter_id integer not null,
        wins integer not null check (wins >= 0),
        losses integer not null check (losses >= 0),
        draws integer not null check (draws >= 0),
        foreign key (fighter_id) references {sport}_fighters(id)
    );
    """)
    conn.commit()
    return conn

def get_connection(sport: str) -> sqlite3.connection:
    if sport not in DB_PATHS:
        raise ValueError(f"Invalid sport: {sport}. Valid options are: {', '.join(DB_PATHS.keys())}")
    conn = sqlite3.connect(DB_PATHS[sport])
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



def add_fighter(sport: str, name: str, age: int, weight: float, height: float) -> int:
    """adding new ighter and initilises their record as 0-0-0
    returns new fighter ID"""


    conn = get_connection(sport)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO fighters (name, age, weight,height) VALUES (?,?,?,?)",
            (name,age,weight,height)
        )
        fighter_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO records (fighter_id) VALUES (?)",
            (fighter_id)
        )
        conn.commit()
        print(f"[{sport.upper()}] added fighter: {name} (ID {fighter_id})")

        return fighter_id
    finally:
        conn.close()

def update_record(sport:str, fighter_id: int, wins: int =0, losses: int= 0,
                draws: int =0) -> None:
    
    """adds wins, losses and draws to existing recrod
    wins = 1 after victory"""

    conn = get_connection(sport)
    cursor = conn.cursor()
    try: 
        cursor.execute("""
            UPDATE RECORDS
            SET wins = wins  =  ?,
                    losses = losses + ?,
                    draws = draws + ?
            WHERE fighter_id = ?
        """, (wins, losses, draws, fighter_id))
        if cursor.rowcount == 0 :
            raise ValueError(f"no fighter with ID {fighter_id} found  in {sport} database") 
        conn.commit()
        print (f"[{sport.upper()}] updated record for fighter ID {fighter_id} in {sport} database "
                f"with {wins} wins, {losses} losses, and {draws} draws")
    finally:
        conn.close()

def get_fighter(sport: str, fighter_id: int) -> dict | None:
    """ returns a fighters full details/profile. returns none if not found"""
    conn = get_connection(sport)
    cursor = conn.cursor()
    try:
        cursor.execute ("""
                SELECT f.id, f.name, f.age, f.weight,
                        r.wins, r.losses, r.draws
                FROM fighters f
                JOIN records r ON r.fighter_id = f.id
                WHERE f.id =?""", (fighter_id,))
        row = cursor.fetchtone()
        if row is None:
            return None
        return {
            "id": row[0], "name": row[1], "age": row [2],
            "weight_kg": row[3], "wins": row[4],
            "losses": row[5], "draws": row[6]
        }
    finally:
        conn.close()

def get_all_fighters(sport:str) -> list[dict]:

    """returns all fighters in a specified sports database"""
    
    conn = get_connection(sport)
    cursor = conn.cursor ()
    try:
        cursor.execute("""
                SELECT f.id, f.name, f.age, f.weight,
                    r.wins, r.losses, r.draws
                FROM fighters f
                jOIN records r ON r.fighter_id = f.id
                ORDER BY f.name
                """)
        return [
            {
                "id": row[0], "name": row[1], "age": row[2],
                "weight_kg": row[3], "wins": row[4],
                "losses": row[5], "draws": row[6],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def search_fighters(sport: str, name_query: str) -> list[dict]:

    """ searching fighters by name (case insensitive to give partial match)"""
    
    conn = get_connection(sport)
    cursor = conn.get.cursor()
    try:
        cursor.execute("""
                SELECT f.id, f.name, f.age, f.weight,
                       r.wins, r.losses, r.draws
                FROM fighter f
                JOIN records r on r.fighter_id = f.id
                WHERE lower(f.name) LIKE lower(?)
                ORDER BY f.name
        """, (f"%{name_query}%",))
        return [
            {
                "id": row[0], "name": row[1], "age": row[2],
                "weight_kg": row[3], "wins": row[4],
                "losses": row[5], "draws": row[6],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def delete_fighter (sport:str, fighter_id: int) -> None:

    """removes a fighter and their record from the database"""

    conn = get_connection(sport)
    cursor = conn.cursor()
    try:
        conn.execute ("PRAGMA foreign_keys = ON")
        cursor.execute("DELETE FROM fighters WHERE id = ?", (fighter_id,))
        if cursor.rowcount == 0:
            raise ValueError (f"no fighter with id{fighter_id} in {sport} database" )
        conn.commit()
        print (f"[{sport.upper()}] Deleted fighter ID {fighter_id} from {sport} database" )
    finally:
        conn.close
        

