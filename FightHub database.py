import sqlite3
import os

"""creating database file paths"""

DB_PATHS ={
    "kickboxing": "kickboxing.db",
    "boxing": "boxing.db",
    "mma": "mma.db"
}

"""creating tables for each sport"""

def create_tables(sport: str) -> sqlite3.connection:
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
    return create_tables(sport)