import sqlite3
import os

"""creating database file paths"""



class fighter_database:



    DB_PATHS ={
    "kickboxing": "kickboxing.db",
    "boxing": "boxing.db",
    "mma": "mma.db"
}

    """manages a single sports SQLITE database
    
    sports recorded in str can choose from kickboxing, boxing, mma"""

    VALID_SPORTS = ("kickboxing", "boxing", "mma")

    def __init__(self, sport: str, db_dir: str =".") -> None:

        if sport not in self.VALID_SPORTS:
            raise ValueError(f"Invalid sport '{sport}'. please choose from {self.VALID_SPORTS}")
            

        self.sport = sport
        self.db_path = f"{db_dir}/{sport}.db"
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute ("PRAGMA foreign_keys = ON")
        self._create_tables()
        print (f"[{self.sport.upper()}] database ready -> {self.db_path}")


    def __enter__(self) -> "fighter_database":
        return self
    
    def __exit__(self, *_) -> None:
        self.close()
    
    def __repr__(self) -> str:
        return f"fighter_database(sport ='{self.sport}', db= '{self.db_path}')"
        








    def create_tables(self) -> sqlite3.connection:

        """creating tables for each sport"""


       

        self._conn.executescript(f"""CREATE TABLE IF NOT EXISTS {self.sport}_fighters (
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
            foreign key (fighter_id) references {self.sport}_fighters(id)
        );
        """)
        self._conn.commit()




    
    @staticmethod
    def _row_to_dict(row: tuple) -> dict:
        return {
            "id": row[0],
            "name": row[1],
            "age": row[2],
            "weight_kg": row[3],
            "wins": row[4],
            "losses": row[5],
            "draws": row[6],
        }

    def get_connection(self) -> sqlite3.connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    







    def add_fighter(self, name:str, age:int, weight: float) -> int:
        """adding new ighter and initilises their record as 0-0-0
        returns new fighter ID"""


        cursor = self._conn.cursor
        cursor.execute(
            "INSERT INTO fighters (name, age, weight) VALUES (?,?,?,?)",
            (name,age,weight)
        )
        fighter_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO records (fighter_id) VALUES (?)",
            (fighter_id)
        )
        self._conn.commit()
        print(f"[{self.sport.upper()}] added fighter: {name} (ID {fighter_id})")
        return fighter_id
 




    def update_record(self,
                      fighter_id: int,
                        wins: int =0,
                      losses: int =0,
                      draws: int =0) -> None:
        
        """adds wins, losses and draws to existing recrod
        wins = 1 after victory"""

        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE RECORDS
            SET wins = wins  =  ?,
                    losses = losses + ?,
                    draws = draws + ?
            WHERE fighter_id = ?
        """, (wins, losses, draws, fighter_id))
        if cursor.rowcount == 0 :
            raise ValueError(f"no fighter with ID {fighter_id} found  in {self.sport} database") 
        self._conn.commit()
        print (f"[{self.sport.upper()}] updated record for fighter ID {fighter_id} in {self.sport} database "
                f"with {wins} wins, {losses} losses, and {draws} draws")
        





    def get_fighter(self, fighter_id: int) -> dict | None:


        """ returns a fighters full details/profile. returns none if not found"""

        cursor =  self._conn.cursor()
        cursor.execute ("""
                SELECT f.id, f.name, f.age, f.weight,
                        r.wins, r.losses, r.draws
                FROM fighters f
                JOIN records r ON r.fighter_id = f.id
                WHERE f.id =?""", (fighter_id,))
        row = cursor.fetchtone()
        return self._row_to_dict(row) if row else None
    

       

       

    def get_all_fighters(self) -> list[dict]:

        """returns all fighters in a specified sports database"""
        
        cursor = self._conn.cursor()
        cursor.execute("""
                SELECT f.id, f.name, f.age, f.weight,
                    r.wins, r.losses, r.draws
                FROM fighters f
                jOIN records r ON r.fighter_id = f.id
                ORDER BY f.name
                """)
        return [self._row_to_dict(row) for row in cursor.fetchall()]
    

    def search_fighters(self, name_query: str) -> list[dict]:

        """ searching fighters by name (case insensitive to give partial match)"""
        
        cursor=self._conn.cursor()
        cursor.execute("""
                SELECT f.id, f.name, f.age, f.weight,
                    r.wins, r.losses, r.draws
                FROM fighter f
                JOIN records r on r.fighter_id = f.id
                WHERE lower(f.name) LIKE lower(?)
                ORDER BY f.name
        """, (f"%{name_query}%",))
        return [self._row_to_dict(row) for row in cursor.fetchall()] 
    
    
        



   


    def delete_fighter (self, fighter_id: int) -> None:

        """removes a fighter and their record from the database"""

       
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM fighters WHERE id = ?", (fighter_id,))
        if cursor.rowcount == 0:
            raise ValueError (f"no fighter with id{fighter_id} in {self.sport} database" )
        self._conn.commit()
        print (f"[{self.sport.upper()}] Deleted fighter ID {fighter_id} from {self.sport} database" )
  



    def delete_fighter(self, fighter_id:int) -> None:
    
        """permamntly deletes a fighter and their record from the database"""

        cursor = self._conn.cursor()
        cursor.execute ("DELETE FROM fighters WHERE id = ?", (fighter_id,))
        if cursor.rowcount ==0:
            raise ValueError(
                f" no fighter with id {fighter_id} in {self.sport} database"
            )
        self._conn.commit()
        print (f" [{self.sport.upper()}] deleted fighter ID {fighter_id}")


    def print_fighter(self, fighter: dict) -> None:

        """Prints a fighter's details returned by get fighter/ get all fighters"""

        total = fighter ["wins"] + fighter ["losses"] + fighter ["draws"]
        print(f"Fighter: {fighter['name']}")
        print(f"Age: {fighter['age']}")
        print(f"Weight: {fighter['weight']}")
        print(f"Wins: {fighter['wins']}")
        print(f"Losses: {fighter['losses']}")
        print(f"Draws: {fighter['draws']}")
        print(f"Total: {total}")

    def close (self) -> None:

        """closes the database connection"""

        self._conn.close()
        print (f"[{self.sport.upper()}] Database connection closed")



from fighter_database import FighterDB

# Standard usage
kb = FighterDB("kickboxing")
fid = kb.add_fighter("Jordan Blake", age=22, weight=70.5)
kb.update_record(fid, wins=1)
kb.print_fighter(kb.get_fighter(fid))
kb.close()

# Or as a context manager (auto-closes)
with FighterDB("mma") as mma:
    fid = mma.add_fighter("Alex Torres", age=25, weight=77.1)
    mma.update_record(fid, wins=2, losses=1)