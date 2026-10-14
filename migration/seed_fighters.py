"""Wipe all fighters and seed synthetic English fighters for all three sports.

Uses a match SCHEDULE so every result is recorded consistently for both fighters.
Run from project root:  python migration/seed_fighters.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.fighter import Fighter, FighterRecord
from app.models.fight import FightHistory
from datetime import date, datetime

app = create_app()

# ── Fighter definitions ────────────────────────────────────────────────────
# (name, weight_kg, dob, county, description or None)

BOXING_FIGHTERS = [
    ("Connor Fitzpatrick", 67.0, "1999-04-12", "Greater Manchester",
     "Former ABA champion, southpaw stylist with fast hands and excellent footwork. Trains at Bury ABC."),
    ("Nathan Griffiths",   63.5, "1996-06-25", "Merseyside",
     "Experienced super-lightweight with a wide amateur base. Hard to hurt and excellent in close."),
    ("Darnell Hughes",     61.2, "2001-08-30", "West Midlands",
     "Explosive lightweight with a powerful right hand. Unbeaten record in home city."),
    ("Reece Lawton",       76.2, "1997-11-03", "West Yorkshire",
     "Tough super-middleweight known for durability and pressure fighting. Six years at amateur level."),
    ("Amir Qasim",         75.5, "1995-03-22", "West Yorkshire",
     "Technically sound super-middleweight with clean punching and sharp defence."),
    ("Brandon Osei",       54.4, "2002-02-17", "South Yorkshire",
     "Featherweight prospect with slick combinations. Represented England at the 2021 junior nationals."),
    ("Marcus Webb",        66.7, "1998-07-14", "Greater Manchester", None),
    ("Tyler Moon",         54.1, "2001-12-09", "Tyne and Wear",
     "Quick combination puncher at bantamweight. Works behind a high guard and uses angles well."),
    ("Lewis Park",         70.3, "1994-09-28", "Merseyside", None),
    ("Luke Patterson",     67.5, "2000-03-15", "Cheshire",
     "Solid welterweight with good ring IQ and a reliable jab. Former national junior silver medallist."),
    ("Kirk Shelby",        69.5, "1993-01-15", "Derbyshire", None),
    ("Ben Hartley",        76.0, "1997-10-06", "Nottinghamshire", None),
    ("Joel Carter",        54.0, "2003-05-11", "Lancashire", None),
    ("Liam Cross",         61.0, "1998-05-19", "Kent", None),
    ("Gary Finch",         60.8, "1997-08-22", "Essex", None),
    ("Scott Vickers",      75.0, "1996-04-11", "Hampshire", None),
    ("Dean Cooper",        63.0, "1995-11-28", "Norfolk", None),
    ("Matty Burns",        63.2, "1994-06-15", "Suffolk", None),
    ("Will Foster",        53.8, "2002-09-07", "County Durham", None),
    ("Adam Sharp",         61.5, "2001-01-19", "Lincolnshire", None),
]

MMA_FIGHTERS = [
    ("Jake Winters",   70.3, "1998-02-28", "West Yorkshire",
     "Well-rounded lightweight with a wrestling base and sharp striking. Three submission wins in 2023."),
    ("Callum Pierce",  83.9, "1996-07-19", "Greater Manchester",
     "Hard-hitting middleweight with a Muay Thai background. Dangerous on the feet and against the cage."),
    ("Elliot Fox",     83.5, "1997-11-01", "South Yorkshire",
     "Technical middleweight with a BJJ black belt. Loves to drag fights to the mat."),
    ("Shane Doyle",    77.1, "1995-08-22", "Lancashire",
     "Aggressive welterweight who overwhelms opponents with volume strikes."),
    ("Ben Walsh",      77.5, "1999-06-14", "West Yorkshire",
     "Rising welterweight prospect with excellent takedown defence and a sharp counter jab."),
    ("Levi Brooks",    61.2, "2000-04-05", "Tyne and Wear",
     "Slick bantamweight with quick hands. Former regional amateur wrestling champion."),
    ("Ricky Dolan",    70.0, "1994-01-30", "West Yorkshire", None),
    ("Dan Hooper",     61.5, "2001-09-17", "West Midlands", None),
    ("Chris Morgan",   69.8, "1998-11-03", "West Midlands", None),
    ("Nathan Cole",    60.8, "2002-03-22", "South Yorkshire", None),
    ("Lee Carr",       83.2, "1996-05-08", "Lancashire", None),
    ("Craig Hutton",   70.5, "1997-06-04", "Greater Manchester", None),
    ("Ryan Ford",      84.0, "1993-12-14", "Merseyside", None),
    ("Tom Bradley",    83.0, "1999-03-09", "Nottinghamshire", None),
    ("Phil Stone",     70.1, "2000-11-25", "Derbyshire", None),
    ("Paul Neville",   61.0, "1998-07-11", "Kent", None),
    ("Danny Marsh",    83.5, "1997-02-18", "Essex", None),
    ("Alex Reid",      77.0, "2000-08-30", "Merseyside", None),
    ("Jamie Hunt",     69.5, "2001-05-14", "Tyne and Wear", None),
    ("Dean Park",      83.8, "1999-10-02", "Derbyshire", None),
]

KICKBOXING_FIGHTERS = [
    ("Mason Cole",    67.0, "1999-05-03", "West Midlands",
     "Switch-hitting welterweight with beautiful timing on the head kick. Four-time regional champion."),
    ("Karl Dennis",   66.5, "1997-03-14", "Merseyside",
     "Pressure fighter with excellent body kicks and a granite chin. Rarely stopped in over 20 amateur bouts."),
    ("Luke Evans",    77.0, "1996-09-07", "West Yorkshire",
     "Power puncher at middleweight. Likes to set up his right hand with heavy body combinations."),
    ("Jordan Price",  63.5, "2001-07-22", "South Yorkshire",
     "Talented lightweight with fast low kicks and lateral movement. Two-time England Schools champion."),
    ("Tom Hughes",    67.5, "1998-12-01", "Greater Manchester",
     "Disciplined welterweight with technical striking and good defensive awareness."),
    ("Jake Ross",     63.2, "2000-09-18", "West Yorkshire",
     "Quick lightweight with dynamic combination work and excellent ring craft."),
    ("Jack Steele",   67.5, "1998-12-30", "Lancashire", None),
    ("Ryan Booth",    67.2, "1999-10-15", "Derbyshire", None),
    ("Billy Marsh",   76.5, "1997-04-22", "Lancashire", None),
    ("Ryan Nash",     66.8, "2000-02-09", "South Yorkshire", None),
    ("Chris Blake",   63.1, "2001-07-05", "Merseyside", None),
    ("Sam Hunt",      70.0, "2000-08-19", "Nottinghamshire", None),
    ("Lee Young",     63.2, "2002-03-27", "Tyne and Wear", None),
    ("Dean Miles",    63.0, "1998-04-14", "Kent", None),
    ("Steve Dorrell", 76.2, "1996-10-31", "Essex", None),
    ("Michael Osei",  62.8, "1999-11-22", "West Midlands", None),
    ("Aaron Cole",    64.0, "1998-06-17", "Nottinghamshire", None),
    ("Adam Price",    77.2, "2001-01-08", "Tyne and Wear", None),
    ("Nathan Wood",   67.0, "2000-07-16", "Derbyshire", None),
    ("Lewis Brown",   62.5, "2002-04-03", "Greater Manchester", None),
]

# ── Match schedules ────────────────────────────────────────────────────────
# (date, fighter_a, fighter_b, method, a_wins)
# a_wins: True = A wins, False = B wins, None = Draw

BOXING_SCHEDULE = [
    # 2020 — early career establishing shots
    ("2020-01-18", "Darnell Hughes",     "Gary Finch",           "KO/TKO",   True),
    ("2020-01-25", "Nathan Griffiths",   "Gary Finch",           "Decision", True),
    ("2020-02-08", "Reece Lawton",       "Scott Vickers",        "Decision", True),
    ("2020-02-22", "Lewis Park",         "Matty Burns",          "Decision", True),
    ("2020-03-07", "Marcus Webb",        "Kirk Shelby",          "Decision", True),
    ("2020-04-04", "Amir Qasim",         "Dean Cooper",          "KO/TKO",   True),
    ("2020-04-18", "Nathan Griffiths",   "Dean Cooper",          "Decision", True),
    ("2020-05-02", "Luke Patterson",     "Liam Cross",           "Decision", True),
    ("2020-05-16", "Reece Lawton",       "Kirk Shelby",          "Decision", True),
    ("2020-06-06", "Reece Lawton",       "Dean Cooper",          "KO/TKO",   True),
    ("2020-06-20", "Darnell Hughes",     "Adam Sharp",           "Decision", True),
    ("2020-07-04", "Gary Finch",         "Matty Burns",          "Decision", True),
    ("2020-07-18", "Lewis Park",         "Dean Cooper",          "Decision", True),
    ("2020-07-25", "Amir Qasim",         "Matty Burns",          "Decision", True),
    ("2020-08-01", "Nathan Griffiths",   "Lewis Park",           "Decision", True),
    ("2020-08-08", "Tyler Moon",         "Joel Carter",          "Decision", True),
    ("2020-08-15", "Liam Cross",         "Will Foster",          "Decision", True),
    ("2020-08-22", "Connor Fitzpatrick", "Marcus Webb",          "Decision", True),
    ("2020-09-05", "Brandon Osei",       "Joel Carter",          "Decision", True),
    ("2020-09-12", "Reece Lawton",       "Matty Burns",          "KO/TKO",   True),
    ("2020-09-19", "Marcus Webb",        "Liam Cross",           "Decision", True),
    ("2020-09-26", "Kirk Shelby",        "Adam Sharp",           "Decision", True),
    ("2020-10-03", "Ben Hartley",        "Scott Vickers",        "Decision", True),
    ("2020-10-10", "Connor Fitzpatrick", "Kirk Shelby",          "Decision", True),
    ("2020-10-24", "Marcus Webb",        "Dean Cooper",          "Decision", True),
    ("2020-11-07", "Luke Patterson",     "Adam Sharp",           "Decision", True),
    ("2020-11-14", "Nathan Griffiths",   "Matty Burns",          "KO/TKO",   True),
    ("2020-11-21", "Tyler Moon",         "Will Foster",          "Decision", True),
    ("2020-11-28", "Amir Qasim",         "Scott Vickers",        "Decision", True),
    ("2020-12-05", "Lewis Park",         "Kirk Shelby",          "Decision", True),
    ("2020-12-12", "Ben Hartley",        "Liam Cross",           "Decision", True),
    ("2020-12-19", "Darnell Hughes",     "Joel Carter",          "KO/TKO",   True),
    # 2021
    ("2021-01-09", "Reece Lawton",       "Ben Hartley",          "Decision", True),
    ("2021-01-16", "Nathan Griffiths",   "Scott Vickers",        "Decision", True),
    ("2021-01-23", "Connor Fitzpatrick", "Liam Cross",           "Decision", True),
    ("2021-01-30", "Brandon Osei",       "Tyler Moon",           "Decision", True),
    ("2021-02-06", "Darnell Hughes",     "Gary Finch",           "KO/TKO",   True),
    ("2021-02-13", "Amir Qasim",         "Ben Hartley",          "KO/TKO",   True),
    ("2021-02-20", "Lewis Park",         "Matty Burns",          "Decision", True),
    ("2021-02-27", "Luke Patterson",     "Kirk Shelby",          "Decision", True),
    ("2021-03-06", "Nathan Griffiths",   "Liam Cross",           "Decision", True),
    ("2021-03-13", "Marcus Webb",        "Gary Finch",           "Decision", True),
    ("2021-03-20", "Ben Hartley",        "Dean Cooper",          "KO/TKO",   True),
    ("2021-03-27", "Tyler Moon",         "Adam Sharp",           "Decision", True),
    ("2021-04-03", "Connor Fitzpatrick", "Luke Patterson",       "Decision", True),
    ("2021-04-10", "Reece Lawton",       "Scott Vickers",        "KO/TKO",   True),
    ("2021-04-17", "Darnell Hughes",     "Liam Cross",           "Decision", True),
    ("2021-04-24", "Amir Qasim",         "Kirk Shelby",          "Decision", True),
    ("2021-05-01", "Nathan Griffiths",   "Tyler Moon",           "Decision", True),
    ("2021-05-08", "Gary Finch",         "Dean Cooper",          "Decision", True),
    ("2021-05-15", "Brandon Osei",       "Will Foster",          "Decision", True),
    ("2021-05-22", "Lewis Park",         "Adam Sharp",           "Decision", True),
    ("2021-05-29", "Marcus Webb",        "Matty Burns",          "Decision", True),
    ("2021-06-05", "Kirk Shelby",        "Liam Cross",           "Decision", True),
    ("2021-06-12", "Connor Fitzpatrick", "Dean Cooper",          "KO/TKO",   True),
    ("2021-06-19", "Reece Lawton",       "Marcus Webb",          "Decision", True),
    ("2021-06-26", "Darnell Hughes",     "Will Foster",          "Decision", True),
    ("2021-07-03", "Amir Qasim",         "Scott Vickers",        "Decision", True),
    ("2021-07-10", "Luke Patterson",     "Lewis Park",           "Decision", True),
    ("2021-07-17", "Nathan Griffiths",   "Kirk Shelby",          "KO/TKO",   True),
    ("2021-07-24", "Ben Hartley",        "Gary Finch",           "Decision", True),
    ("2021-07-31", "Joel Carter",        "Adam Sharp",           "Decision", True),
    ("2021-08-07", "Brandon Osei",       "Joel Carter",          "KO/TKO",   True),
    ("2021-08-14", "Tyler Moon",         "Dean Cooper",          "Decision", True),
    ("2021-08-21", "Liam Cross",         "Matty Burns",          "Decision", True),
    ("2021-08-28", "Will Foster",        "Adam Sharp",           "Decision", True),
    ("2021-09-04", "Connor Fitzpatrick", "Amir Qasim",           "Decision", True),
    ("2021-09-11", "Reece Lawton",       "Kirk Shelby",          "Decision", True),
    ("2021-09-18", "Nathan Griffiths",   "Matty Burns",          "Decision", True),
    ("2021-09-25", "Marcus Webb",        "Scott Vickers",        "Decision", True),
    ("2021-10-02", "Darnell Hughes",     "Adam Sharp",           "Decision", True),
    ("2021-10-09", "Lewis Park",         "Dean Cooper",          "Decision", True),
    ("2021-10-16", "Luke Patterson",     "Matty Burns",          "Decision", True),
    ("2021-10-23", "Ben Hartley",        "Liam Cross",           "Decision", True),
    ("2021-10-30", "Tyler Moon",         "Gary Finch",           "KO/TKO",   True),
    ("2021-11-06", "Amir Qasim",         "Dean Cooper",          "Decision", True),
    ("2021-11-13", "Kirk Shelby",        "Matty Burns",          "Decision", True),
    ("2021-11-20", "Connor Fitzpatrick", "Marcus Webb",          "KO/TKO",   True),
    ("2021-11-27", "Reece Lawton",       "Ben Hartley",          "Decision", True),
    ("2021-12-04", "Nathan Griffiths",   "Lewis Park",           "Decision", True),
    ("2021-12-11", "Brandon Osei",       "Tyler Moon",           "KO/TKO",   True),
    ("2021-12-18", "Joel Carter",        "Will Foster",          "Decision", False),  # Will wins
    # 2022
    ("2022-01-08", "Nathan Griffiths",   "Connor Fitzpatrick",   "Decision", True),   # UPSET
    ("2022-01-15", "Reece Lawton",       "Dean Cooper",          "Decision", True),
    ("2022-01-22", "Darnell Hughes",     "Gary Finch",           "KO/TKO",   True),
    ("2022-01-29", "Amir Qasim",         "Marcus Webb",          "Decision", True),
    ("2022-02-05", "Lewis Park",         "Kirk Shelby",          "Decision", True),
    ("2022-02-12", "Luke Patterson",     "Liam Cross",           "Decision", True),
    ("2022-02-19", "Marcus Webb",        "Matty Burns",          "Decision", True),
    ("2022-02-26", "Ben Hartley",        "Scott Vickers",        "Decision", True),
    ("2022-03-05", "Tyler Moon",         "Will Foster",          "Decision", True),
    ("2022-03-12", "Brandon Osei",       "Joel Carter",          "KO/TKO",   True),
    ("2022-03-19", "Reece Lawton",       "Marcus Webb",          "Decision", True),
    ("2022-03-26", "Nathan Griffiths",   "Adam Sharp",           "Decision", True),
    ("2022-04-02", "Connor Fitzpatrick", "Reece Lawton",         "Decision", True),
    ("2022-04-09", "Darnell Hughes",     "Joel Carter",          "KO/TKO",   True),
    ("2022-04-16", "Amir Qasim",         "Ben Hartley",          "Decision", True),
    ("2022-04-23", "Lewis Park",         "Matty Burns",          "Decision", True),
    ("2022-04-30", "Luke Patterson",     "Dean Cooper",          "Decision", True),
    ("2022-05-07", "Nathan Griffiths",   "Marcus Webb",          "Decision", True),
    ("2022-05-14", "Reece Lawton",       "Ben Hartley",          "Decision", True),
    ("2022-05-21", "Darnell Hughes",     "Will Foster",          "Decision", True),
    ("2022-05-28", "Kirk Shelby",        "Dean Cooper",          "Decision", True),
    ("2022-06-04", "Amir Qasim",         "Scott Vickers",        "Decision", True),
    ("2022-06-11", "Tyler Moon",         "Liam Cross",           "Decision", True),
    ("2022-06-18", "Connor Fitzpatrick", "Amir Qasim",           "KO/TKO",   True),
    ("2022-06-25", "Marcus Webb",        "Kirk Shelby",          "Decision", True),
    ("2022-07-02", "Luke Patterson",     "Marcus Webb",          "Decision", True),
    ("2022-07-09", "Nathan Griffiths",   "Kirk Shelby",          "KO/TKO",   True),
    ("2022-07-16", "Reece Lawton",       "Scott Vickers",        "Decision", True),
    ("2022-07-23", "Darnell Hughes",     "Liam Cross",           "KO/TKO",   True),
    ("2022-07-30", "Ben Hartley",        "Matty Burns",          "Decision", True),
    ("2022-08-06", "Gary Finch",         "Adam Sharp",           "Decision", True),
    ("2022-08-13", "Brandon Osei",       "Tyler Moon",           "Decision", True),
    ("2022-08-20", "Lewis Park",         "Dean Cooper",          "Decision", True),
    ("2022-08-27", "Amir Qasim",         "Matty Burns",          "KO/TKO",   True),
    ("2022-09-03", "Connor Fitzpatrick", "Marcus Webb",          "KO/TKO",   True),
    ("2022-09-10", "Nathan Griffiths",   "Lewis Park",           "Decision", True),
    ("2022-09-17", "Reece Lawton",       "Kirk Shelby",          "Decision", True),
    ("2022-09-24", "Tyler Moon",         "Adam Sharp",           "Decision", True),
    ("2022-10-01", "Luke Patterson",     "Liam Cross",           "Decision", True),
    ("2022-10-08", "Ben Hartley",        "Gary Finch",           "Decision", True),
    ("2022-10-15", "Nathan Griffiths",   "Matty Burns",          "KO/TKO",   True),
    ("2022-10-22", "Darnell Hughes",     "Adam Sharp",           "Decision", True),
    ("2022-10-29", "Reece Lawton",       "Dean Cooper",          "Decision", True),
    ("2022-11-05", "Connor Fitzpatrick", "Luke Patterson",       "Decision", True),
    ("2022-11-12", "Lewis Park",         "Matty Burns",          "Decision", True),
    ("2022-11-19", "Amir Qasim",         "Dean Cooper",          "Decision", True),
    ("2022-11-26", "Kirk Shelby",        "Will Foster",          "Decision", True),
    ("2022-12-03", "Nathan Griffiths",   "Scott Vickers",        "Decision", True),
    ("2022-12-10", "Marcus Webb",        "Dean Cooper",          "Decision", True),
    ("2022-12-17", "Gary Finch",         "Matty Burns",          "Decision", True),
    # 2023
    ("2023-01-07", "Connor Fitzpatrick", "Kirk Shelby",          "KO/TKO",   True),
    ("2023-01-14", "Nathan Griffiths",   "Dean Cooper",          "Decision", True),
    ("2023-01-21", "Reece Lawton",       "Ben Hartley",          "Decision", True),
    ("2023-01-28", "Darnell Hughes",     "Will Foster",          "KO/TKO",   True),
    ("2023-02-04", "Amir Qasim",         "Scott Vickers",        "KO/TKO",   True),
    ("2023-02-11", "Tyler Moon",         "Joel Carter",          "KO/TKO",   True),
    ("2023-02-18", "Lewis Park",         "Adam Sharp",           "Decision", True),
    ("2023-02-25", "Luke Patterson",     "Matty Burns",          "Decision", True),
    ("2023-03-04", "Connor Fitzpatrick", "Reece Lawton",         "KO/TKO",   True),
    ("2023-03-11", "Nathan Griffiths",   "Marcus Webb",          "KO/TKO",   True),
    ("2023-03-18", "Brandon Osei",       "Will Foster",          "Decision", True),
    ("2023-03-25", "Ben Hartley",        "Liam Cross",           "Decision", True),
    ("2023-04-01", "Reece Lawton",       "Scott Vickers",        "Decision", True),
    ("2023-04-08", "Darnell Hughes",     "Gary Finch",           "KO/TKO",   True),
    ("2023-04-15", "Amir Qasim",         "Kirk Shelby",          "Decision", True),
    ("2023-04-22", "Connor Fitzpatrick", "Lewis Park",           "Decision", True),
    ("2023-04-29", "Tyler Moon",         "Matty Burns",          "KO/TKO",   True),
    ("2023-05-06", "Nathan Griffiths",   "Gary Finch",           "Decision", True),
    ("2023-05-13", "Luke Patterson",     "Dean Cooper",          "Decision", True),
    ("2023-05-20", "Marcus Webb",        "Liam Cross",           "Decision", True),
    ("2023-05-27", "Reece Lawton",       "Kirk Shelby",          "Decision", True),
    ("2023-06-03", "Brandon Osei",       "Joel Carter",          "Decision", True),
    ("2023-06-10", "Darnell Hughes",     "Joel Carter",          "KO/TKO",   True),
    ("2023-06-17", "Amir Qasim",         "Matty Burns",          "Decision", True),
    ("2023-06-24", "Connor Fitzpatrick", "Nathan Griffiths",     "Decision", True),  # Rematch
    ("2023-07-01", "Lewis Park",         "Kirk Shelby",          "Decision", True),
    ("2023-07-08", "Luke Patterson",     "Scott Vickers",        "Decision", True),
    ("2023-07-15", "Ben Hartley",        "Dean Cooper",          "KO/TKO",   True),
    ("2023-07-22", "Tyler Moon",         "Will Foster",          "Decision", True),
    ("2023-07-29", "Nathan Griffiths",   "Lewis Park",           "Decision", True),
    ("2023-08-05", "Reece Lawton",       "Marcus Webb",          "Decision", True),
    ("2023-08-12", "Darnell Hughes",     "Matty Burns",          "KO/TKO",   True),
    ("2023-08-19", "Amir Qasim",         "Ben Hartley",          "KO/TKO",   True),
    ("2023-08-26", "Connor Fitzpatrick", "Amir Qasim",           "Decision", True),
    ("2023-09-02", "Tyler Moon",         "Liam Cross",           "Decision", True),
    ("2023-09-09", "Luke Patterson",     "Kirk Shelby",          "Decision", True),
    ("2023-09-16", "Nathan Griffiths",   "Adam Sharp",           "Decision", True),
    ("2023-09-23", "Reece Lawton",       "Dean Cooper",          "Decision", True),
    ("2023-09-30", "Marcus Webb",        "Gary Finch",           "Decision", True),
    ("2023-10-07", "Brandon Osei",       "Tyler Moon",           "Decision", True),
    ("2023-10-14", "Connor Fitzpatrick", "Luke Patterson",       "Decision", True),
    ("2023-10-21", "Lewis Park",         "Matty Burns",          "Decision", True),
    ("2023-10-28", "Darnell Hughes",     "Liam Cross",           "KO/TKO",   True),
    ("2023-11-04", "Ben Hartley",        "Scott Vickers",        "Decision", True),
    ("2023-11-11", "Nathan Griffiths",   "Kirk Shelby",          "Decision", True),
    ("2023-11-18", "Reece Lawton",       "Liam Cross",           "Decision", True),
    ("2023-11-25", "Amir Qasim",         "Gary Finch",           "Decision", True),
    ("2023-12-02", "Tyler Moon",         "Dean Cooper",          "Decision", True),
    ("2023-12-09", "Marcus Webb",        "Will Foster",          "Decision", True),
    ("2023-12-16", "Kirk Shelby",        "Joel Carter",          "Decision", True),
    # 2024
    ("2024-01-06", "Connor Fitzpatrick", "Ben Hartley",          "KO/TKO",   True),
    ("2024-01-13", "Darnell Hughes",     "Will Foster",          "Decision", True),
    ("2024-01-20", "Reece Lawton",       "Amir Qasim",           "Decision", True),
    ("2024-01-27", "Nathan Griffiths",   "Marcus Webb",          "Decision", True),
    ("2024-02-03", "Brandon Osei",       "Tyler Moon",           "KO/TKO",   True),
    ("2024-02-10", "Lewis Park",         "Dean Cooper",          "Decision", True),
    ("2024-02-17", "Luke Patterson",     "Ben Hartley",          "Decision", True),
    ("2024-02-24", "Darnell Hughes",     "Adam Sharp",           "KO/TKO",   True),
    ("2024-03-02", "Connor Fitzpatrick", "Reece Lawton",         "Decision", True),
    ("2024-03-09", "Amir Qasim",         "Marcus Webb",          "Decision", True),
    ("2024-03-16", "Nathan Griffiths",   "Lewis Park",           "Decision", True),
    ("2024-03-23", "Tyler Moon",         "Kirk Shelby",          "Decision", True),
    ("2024-04-06", "Reece Lawton",       "Scott Vickers",        "KO/TKO",   True),
    ("2024-04-13", "Darnell Hughes",     "Gary Finch",           "KO/TKO",   True),
    ("2024-04-20", "Connor Fitzpatrick", "Marcus Webb",          "Decision", True),
    ("2024-04-27", "Nathan Griffiths",   "Tyler Moon",           "Decision", True),
    ("2024-05-04", "Brandon Osei",       "Joel Carter",          "Decision", True),
    ("2024-05-11", "Lewis Park",         "Liam Cross",           "Decision", True),
    ("2024-05-18", "Reece Lawton",       "Ben Hartley",          "Decision", True),
    ("2024-05-25", "Darnell Hughes",     "Matty Burns",          "KO/TKO",   True),
    ("2024-06-01", "Connor Fitzpatrick", "Nathan Griffiths",     "Decision", True),  # Third fight
    ("2024-06-08", "Luke Patterson",     "Lewis Park",           "Decision", True),
    ("2024-06-15", "Amir Qasim",         "Scott Vickers",        "Decision", True),
    ("2024-06-22", "Tyler Moon",         "Matty Burns",          "KO/TKO",   True),
]

MMA_SCHEDULE = [
    # 2020
    ("2020-01-11", "Shane Doyle",    "Phil Stone",       "KO/TKO",   True),
    ("2020-01-25", "Jake Winters",   "Phil Stone",       "Decision", True),
    ("2020-02-08", "Callum Pierce",  "Danny Marsh",      "KO/TKO",   True),
    ("2020-02-22", "Elliot Fox",     "Ryan Ford",        "Submission", True),
    ("2020-03-07", "Ben Walsh",      "Alex Reid",        "Decision", True),
    ("2020-03-21", "Ricky Dolan",    "Jamie Hunt",       "Decision", True),
    ("2020-04-04", "Shane Doyle",    "Dean Park",        "KO/TKO",   True),
    ("2020-04-18", "Levi Brooks",    "Nathan Cole",      "Decision", True),
    ("2020-05-02", "Callum Pierce",  "Tom Bradley",      "KO/TKO",   True),
    ("2020-05-16", "Jake Winters",   "Craig Hutton",     "Submission", True),
    ("2020-05-30", "Elliot Fox",     "Danny Marsh",      "Submission", True),
    ("2020-06-13", "Chris Morgan",   "Jamie Hunt",       "Decision", True),
    ("2020-06-27", "Ben Walsh",      "Dean Park",        "Decision", True),
    ("2020-07-11", "Ricky Dolan",    "Phil Stone",       "Decision", True),
    ("2020-07-25", "Shane Doyle",    "Ryan Ford",        "KO/TKO",   True),
    ("2020-08-08", "Levi Brooks",    "Paul Neville",     "Decision", True),
    ("2020-08-22", "Callum Pierce",  "Lee Carr",         "KO/TKO",   True),
    ("2020-09-05", "Jake Winters",   "Jamie Hunt",       "Decision", True),
    ("2020-09-19", "Elliot Fox",     "Tom Bradley",      "Submission", True),
    ("2020-10-03", "Dan Hooper",     "Nathan Cole",      "Decision", True),
    ("2020-10-17", "Chris Morgan",   "Alex Reid",        "Decision", True),
    ("2020-10-31", "Ben Walsh",      "Craig Hutton",     "Decision", True),
    ("2020-11-14", "Shane Doyle",    "Tom Bradley",      "KO/TKO",   True),
    ("2020-11-28", "Ricky Dolan",    "Craig Hutton",     "Decision", True),
    ("2020-12-12", "Levi Brooks",    "Jamie Hunt",       "KO/TKO",   True),
    # 2021
    ("2021-01-09", "Jake Winters",   "Alex Reid",        "Submission", True),
    ("2021-01-23", "Callum Pierce",  "Ryan Ford",        "KO/TKO",   True),
    ("2021-02-06", "Elliot Fox",     "Lee Carr",         "Submission", True),
    ("2021-02-20", "Ben Walsh",      "Phil Stone",       "Decision", True),
    ("2021-03-06", "Shane Doyle",    "Craig Hutton",     "KO/TKO",   True),
    ("2021-03-20", "Ricky Dolan",    "Dan Hooper",       "Decision", True),
    ("2021-04-03", "Chris Morgan",   "Paul Neville",     "Decision", True),
    ("2021-04-17", "Levi Brooks",    "Nathan Cole",      "Decision", True),
    ("2021-05-01", "Jake Winters",   "Dean Park",        "Decision", True),
    ("2021-05-15", "Callum Pierce",  "Danny Marsh",      "KO/TKO",   True),
    ("2021-05-29", "Elliot Fox",     "Ryan Ford",        "Decision", True),
    ("2021-06-12", "Shane Doyle",    "Alex Reid",        "KO/TKO",   True),
    ("2021-06-26", "Ben Walsh",      "Tom Bradley",      "Decision", True),
    ("2021-07-10", "Jake Winters",   "Paul Neville",     "Submission", True),
    ("2021-07-24", "Ricky Dolan",    "Jamie Hunt",       "Decision", True),
    ("2021-08-07", "Callum Pierce",  "Tom Bradley",      "KO/TKO",   True),
    ("2021-08-21", "Elliot Fox",     "Danny Marsh",      "Submission", True),
    ("2021-09-04", "Chris Morgan",   "Nathan Cole",      "Decision", True),
    ("2021-09-18", "Levi Brooks",    "Dan Hooper",       "Decision", True),
    ("2021-10-02", "Shane Doyle",    "Phil Stone",       "KO/TKO",   True),
    ("2021-10-16", "Ben Walsh",      "Alex Reid",        "Decision", True),
    ("2021-10-30", "Jake Winters",   "Craig Hutton",     "Decision", True),
    ("2021-11-13", "Ricky Dolan",    "Dean Park",        "Decision", True),
    ("2021-11-27", "Callum Pierce",  "Lee Carr",         "KO/TKO",   True),
    ("2021-12-11", "Elliot Fox",     "Tom Bradley",      "Submission", True),
    ("2021-12-25", "Nathan Cole",    "Paul Neville",     "Decision", True),
    # 2022
    ("2022-01-08", "Jake Winters",   "Ricky Dolan",      "Decision", True),   # Jake beats Ricky
    ("2022-01-22", "Shane Doyle",    "Danny Marsh",      "KO/TKO",   True),
    ("2022-02-05", "Callum Pierce",  "Dean Park",        "KO/TKO",   True),
    ("2022-02-19", "Elliot Fox",     "Craig Hutton",     "Submission", True),
    ("2022-03-05", "Ben Walsh",      "Jamie Hunt",       "Decision", True),
    ("2022-03-19", "Levi Brooks",    "Phil Stone",       "KO/TKO",   True),
    ("2022-04-02", "Chris Morgan",   "Alex Reid",        "Decision", True),
    ("2022-04-16", "Jake Winters",   "Phil Stone",       "KO/TKO",   True),
    ("2022-04-30", "Shane Doyle",    "Ryan Ford",        "Decision", True),
    ("2022-05-14", "Callum Pierce",  "Ryan Ford",        "KO/TKO",   True),
    ("2022-05-28", "Ricky Dolan",    "Craig Hutton",     "Decision", True),
    ("2022-06-11", "Elliot Fox",     "Lee Carr",         "Submission", True),
    ("2022-06-25", "Ben Walsh",      "Nathan Cole",      "Decision", True),
    ("2022-07-09", "Levi Brooks",    "Jamie Hunt",       "Decision", True),
    ("2022-07-23", "Jake Winters",   "Dean Park",        "Decision", True),
    ("2022-08-06", "Shane Doyle",    "Alex Reid",        "KO/TKO",   True),
    ("2022-08-20", "Callum Pierce",  "Danny Marsh",      "KO/TKO",   True),
    ("2022-09-03", "Elliot Fox",     "Phil Stone",       "Submission", True),
    ("2022-09-17", "Chris Morgan",   "Tom Bradley",      "Decision", True),
    ("2022-10-01", "Ben Walsh",      "Dean Park",        "Decision", True),
    ("2022-10-15", "Ricky Dolan",    "Paul Neville",     "Decision", True),
    ("2022-10-29", "Levi Brooks",    "Nathan Cole",      "Decision", True),
    ("2022-11-12", "Jake Winters",   "Alex Reid",        "Submission", True),
    ("2022-11-26", "Shane Doyle",    "Craig Hutton",     "KO/TKO",   True),
    ("2022-12-10", "Callum Pierce",  "Tom Bradley",      "KO/TKO",   True),
    ("2022-12-24", "Elliot Fox",     "Ryan Ford",        "Decision", True),
    # 2023
    ("2023-01-07", "Jake Winters",   "Craig Hutton",     "Decision", True),
    ("2023-01-21", "Shane Doyle",    "Phil Stone",       "KO/TKO",   True),
    ("2023-02-04", "Callum Pierce",  "Lee Carr",         "KO/TKO",   True),
    ("2023-02-18", "Elliot Fox",     "Danny Marsh",      "Submission", True),
    ("2023-03-04", "Ben Walsh",      "Tom Bradley",      "Decision", True),
    ("2023-03-18", "Levi Brooks",    "Dan Hooper",       "KO/TKO",   True),
    ("2023-04-01", "Ricky Dolan",    "Jamie Hunt",       "Decision", True),
    ("2023-04-15", "Chris Morgan",   "Alex Reid",        "Decision", True),
    ("2023-04-29", "Jake Winters",   "Paul Neville",     "Submission", True),
    ("2023-05-13", "Shane Doyle",    "Dean Park",        "KO/TKO",   True),
    ("2023-05-27", "Callum Pierce",  "Ryan Ford",        "KO/TKO",   True),
    ("2023-06-10", "Elliot Fox",     "Tom Bradley",      "Submission", True),
    ("2023-06-24", "Ben Walsh",      "Alex Reid",        "Decision", True),
    ("2023-07-08", "Ricky Dolan",    "Nathan Cole",      "Decision", True),
    ("2023-07-22", "Levi Brooks",    "Phil Stone",       "Decision", True),
    ("2023-08-05", "Jake Winters",   "Dan Hooper",       "Decision", True),
    ("2023-08-19", "Shane Doyle",    "Tom Bradley",      "KO/TKO",   True),
    ("2023-09-02", "Callum Pierce",  "Danny Marsh",      "KO/TKO",   True),
    ("2023-09-16", "Elliot Fox",     "Craig Hutton",     "Submission", True),
    ("2023-09-30", "Chris Morgan",   "Jamie Hunt",       "Decision", True),
    ("2023-10-14", "Ben Walsh",      "Paul Neville",     "Decision", True),
    ("2023-10-28", "Jake Winters",   "Levi Brooks",      "Decision", True),   # Jake vs Levi
    ("2023-11-11", "Ricky Dolan",    "Dean Park",        "Decision", True),
    ("2023-11-25", "Shane Doyle",    "Ryan Ford",        "Decision", True),
    ("2023-12-09", "Callum Pierce",  "Alex Reid",        "KO/TKO",   True),
    # 2024
    ("2024-01-06", "Jake Winters",   "Ricky Dolan",      "Submission", True),  # Rematch Jake wins again
    ("2024-01-20", "Elliot Fox",     "Lee Carr",         "Decision", True),
    ("2024-02-03", "Ben Walsh",      "Craig Hutton",     "Decision", True),
    ("2024-02-17", "Levi Brooks",    "Paul Neville",     "KO/TKO",   True),
    ("2024-03-02", "Jake Winters",   "Shane Doyle",      "Decision", True),   # Big fight Jake vs Shane
    ("2024-03-16", "Callum Pierce",  "Lee Carr",         "KO/TKO",   True),
    ("2024-03-30", "Elliot Fox",     "Ryan Ford",        "Submission", True),
    ("2024-04-13", "Ricky Dolan",    "Phil Stone",       "Decision", True),
    ("2024-04-27", "Ben Walsh",      "Dan Hooper",       "Decision", True),
    ("2024-05-11", "Levi Brooks",    "Jamie Hunt",       "Decision", True),
    ("2024-05-25", "Chris Morgan",   "Nathan Cole",      "Decision", True),
    ("2024-06-08", "Jake Winters",   "Ben Walsh",        "Decision", True),   # Jake vs Ben: Jake wins
    ("2024-06-22", "Callum Pierce",  "Elliot Fox",       "KO/TKO",   True),   # Big fight: Callum wins
]

KICKBOXING_SCHEDULE = [
    # 2020
    ("2020-01-18", "Mason Cole",    "Sam Hunt",       "KO/TKO",   True),
    ("2020-02-01", "Karl Dennis",   "Dean Miles",     "Decision", True),
    ("2020-02-15", "Luke Evans",    "Steve Dorrell",  "KO/TKO",   True),
    ("2020-03-07", "Tom Hughes",    "Nathan Wood",    "Decision", True),
    ("2020-03-21", "Jordan Price",  "Lewis Brown",    "Decision", True),
    ("2020-04-04", "Jake Ross",     "Lee Young",      "Decision", True),
    ("2020-04-18", "Mason Cole",    "Michael Osei",   "Decision", True),
    ("2020-05-02", "Karl Dennis",   "Aaron Cole",     "Decision", True),
    ("2020-05-16", "Luke Evans",    "Adam Price",     "KO/TKO",   True),
    ("2020-05-30", "Jack Steele",   "Lewis Brown",    "Decision", True),
    ("2020-06-13", "Ryan Booth",    "Dean Miles",     "Decision", True),
    ("2020-06-27", "Tom Hughes",    "Lee Young",      "Decision", True),
    ("2020-07-11", "Jordan Price",  "Nathan Wood",    "Decision", True),
    ("2020-07-25", "Jake Ross",     "Michael Osei",   "Decision", True),
    ("2020-08-08", "Mason Cole",    "Ryan Nash",      "KO/TKO",   True),
    ("2020-08-22", "Karl Dennis",   "Sam Hunt",       "Decision", True),
    ("2020-09-05", "Luke Evans",    "Billy Marsh",    "Decision", True),
    ("2020-09-19", "Tom Hughes",    "Aaron Cole",     "Decision", True),
    ("2020-10-03", "Ryan Booth",    "Nathan Wood",    "Decision", True),
    ("2020-10-17", "Jack Steele",   "Lee Young",      "Decision", True),
    ("2020-10-31", "Chris Blake",   "Lewis Brown",    "Decision", True),
    ("2020-11-14", "Jordan Price",  "Michael Osei",   "Decision", True),
    ("2020-11-28", "Jake Ross",     "Adam Price",     "Decision", True),
    ("2020-12-12", "Mason Cole",    "Dean Miles",     "KO/TKO",   True),
    # 2021
    ("2021-01-09", "Karl Dennis",   "Michael Osei",   "KO/TKO",   True),
    ("2021-01-23", "Luke Evans",    "Sam Hunt",       "Decision", True),
    ("2021-02-06", "Tom Hughes",    "Ryan Booth",     "Decision", True),
    ("2021-02-20", "Jordan Price",  "Aaron Cole",     "Decision", True),
    ("2021-03-06", "Jake Ross",     "Nathan Wood",    "Decision", True),
    ("2021-03-20", "Mason Cole",    "Jack Steele",    "Decision", True),
    ("2021-04-03", "Karl Dennis",   "Ryan Nash",      "Decision", True),
    ("2021-04-17", "Luke Evans",    "Steve Dorrell",  "KO/TKO",   True),
    ("2021-05-01", "Tom Hughes",    "Dean Miles",     "Decision", True),
    ("2021-05-15", "Jordan Price",  "Lewis Brown",    "KO/TKO",   True),
    ("2021-05-29", "Jake Ross",     "Lee Young",      "Decision", True),
    ("2021-06-12", "Mason Cole",    "Sam Hunt",       "Decision", True),
    ("2021-06-26", "Karl Dennis",   "Jack Steele",    "Decision", True),
    ("2021-07-10", "Luke Evans",    "Ryan Booth",     "Decision", True),
    ("2021-07-24", "Ryan Nash",     "Nathan Wood",    "Decision", True),
    ("2021-08-07", "Jack Steele",   "Adam Price",     "Decision", True),
    ("2021-08-21", "Tom Hughes",    "Michael Osei",   "Decision", True),
    ("2021-09-04", "Jordan Price",  "Dean Miles",     "Decision", True),
    ("2021-09-18", "Jake Ross",     "Aaron Cole",     "Decision", True),
    ("2021-10-02", "Mason Cole",    "Ryan Booth",     "KO/TKO",   True),
    ("2021-10-16", "Karl Dennis",   "Steve Dorrell",  "Decision", True),
    ("2021-10-30", "Luke Evans",    "Adam Price",     "KO/TKO",   True),
    ("2021-11-13", "Chris Blake",   "Lee Young",      "Decision", True),
    ("2021-11-27", "Tom Hughes",    "Ryan Nash",      "Decision", True),
    ("2021-12-11", "Jordan Price",  "Sam Hunt",       "KO/TKO",   True),
    # 2022
    ("2022-01-08", "Mason Cole",    "Karl Dennis",    "Decision", True),   # Mason beats Karl
    ("2022-01-22", "Luke Evans",    "Billy Marsh",    "KO/TKO",   True),
    ("2022-02-05", "Tom Hughes",    "Jack Steele",    "Decision", True),
    ("2022-02-19", "Jordan Price",  "Ryan Nash",      "Decision", True),
    ("2022-03-05", "Jake Ross",     "Lewis Brown",    "Decision", True),
    ("2022-03-19", "Karl Dennis",   "Dean Miles",     "KO/TKO",   True),
    ("2022-04-02", "Mason Cole",    "Jack Steele",    "KO/TKO",   True),
    ("2022-04-16", "Luke Evans",    "Sam Hunt",       "Decision", True),
    ("2022-04-30", "Tom Hughes",    "Ryan Booth",     "Decision", True),
    ("2022-05-14", "Jordan Price",  "Aaron Cole",     "Decision", True),
    ("2022-05-28", "Jake Ross",     "Nathan Wood",    "Decision", True),
    ("2022-06-11", "Karl Dennis",   "Sam Hunt",       "Decision", True),
    ("2022-06-25", "Mason Cole",    "Steve Dorrell",  "KO/TKO",   True),
    ("2022-07-09", "Luke Evans",    "Dean Miles",     "KO/TKO",   True),
    ("2022-07-23", "Tom Hughes",    "Aaron Cole",     "Decision", True),
    ("2022-08-06", "Ryan Booth",    "Lee Young",      "Decision", True),
    ("2022-08-20", "Jack Steele",   "Michael Osei",   "Decision", True),
    ("2022-09-03", "Jordan Price",  "Lewis Brown",    "Decision", True),
    ("2022-09-17", "Jake Ross",     "Chris Blake",    "Decision", True),
    ("2022-10-01", "Mason Cole",    "Ryan Booth",     "Decision", True),
    ("2022-10-15", "Karl Dennis",   "Billy Marsh",    "KO/TKO",   True),
    ("2022-10-29", "Luke Evans",    "Steve Dorrell",  "KO/TKO",   True),
    ("2022-11-12", "Tom Hughes",    "Sam Hunt",       "Decision", True),
    ("2022-11-26", "Jordan Price",  "Dean Miles",     "Decision", True),
    ("2022-12-10", "Jake Ross",     "Lee Young",      "Decision", True),
    ("2022-12-24", "Ryan Nash",     "Aaron Cole",     "Decision", True),
    # 2023
    ("2023-01-07", "Mason Cole",    "Luke Evans",     "Decision", True),   # Mason vs Luke: Mason wins
    ("2023-01-21", "Karl Dennis",   "Tom Hughes",     "Decision", True),   # Karl vs Tom: Karl wins
    ("2023-02-04", "Jordan Price",  "Jack Steele",    "Decision", True),
    ("2023-02-18", "Jake Ross",     "Ryan Booth",     "Decision", True),
    ("2023-03-04", "Luke Evans",    "Billy Marsh",    "KO/TKO",   True),
    ("2023-03-18", "Tom Hughes",    "Ryan Nash",      "Decision", True),
    ("2023-04-01", "Mason Cole",    "Jordan Price",   "Decision", True),   # Mason vs Jordan
    ("2023-04-15", "Karl Dennis",   "Jack Steele",    "Decision", True),
    ("2023-04-29", "Luke Evans",    "Sam Hunt",       "Decision", True),
    ("2023-05-13", "Jake Ross",     "Aaron Cole",     "Decision", True),
    ("2023-05-27", "Jordan Price",  "Ryan Booth",     "Decision", True),
    ("2023-06-10", "Tom Hughes",    "Dean Miles",     "Decision", True),
    ("2023-06-24", "Mason Cole",    "Ryan Nash",      "KO/TKO",   True),
    ("2023-07-08", "Karl Dennis",   "Luke Evans",     "Decision", False),  # Luke wins! upset
    ("2023-07-22", "Jordan Price",  "Nathan Wood",    "KO/TKO",   True),
    ("2023-08-05", "Jake Ross",     "Lewis Brown",    "Decision", True),
    ("2023-08-19", "Mason Cole",    "Sam Hunt",       "KO/TKO",   True),
    ("2023-09-02", "Tom Hughes",    "Michael Osei",   "Decision", True),
    ("2023-09-16", "Karl Dennis",   "Ryan Booth",     "Decision", True),
    ("2023-09-30", "Luke Evans",    "Billy Marsh",    "KO/TKO",   True),
    ("2023-10-14", "Jordan Price",  "Lee Young",      "Decision", True),
    ("2023-10-28", "Jake Ross",     "Chris Blake",    "Decision", True),
    ("2023-11-11", "Mason Cole",    "Karl Dennis",    "Decision", False),  # Karl wins! revenge
    ("2023-11-25", "Tom Hughes",    "Jack Steele",    "Decision", True),
    ("2023-12-09", "Luke Evans",    "Dean Miles",     "KO/TKO",   True),
    # 2024
    ("2024-01-06", "Mason Cole",    "Luke Evans",     "KO/TKO",   True),   # Mason vs Luke rematch
    ("2024-01-20", "Karl Dennis",   "Jordan Price",   "Decision", True),
    ("2024-02-03", "Tom Hughes",    "Ryan Booth",     "Decision", True),
    ("2024-02-17", "Jake Ross",     "Nathan Wood",    "KO/TKO",   True),
    ("2024-03-02", "Mason Cole",    "Jordan Price",   "Decision", True),
    ("2024-03-16", "Luke Evans",    "Sam Hunt",       "KO/TKO",   True),
    ("2024-03-30", "Karl Dennis",   "Jack Steele",    "Decision", True),
    ("2024-04-13", "Tom Hughes",    "Aaron Cole",     "Decision", True),
    ("2024-04-27", "Jordan Price",  "Chris Blake",    "Decision", True),
    ("2024-05-11", "Jake Ross",     "Michael Osei",   "Decision", True),
    ("2024-05-25", "Mason Cole",    "Karl Dennis",    "Decision", True),   # Third fight Mason wins
    ("2024-06-08", "Luke Evans",    "Tom Hughes",     "Decision", True),   # Luke beats Tom
    ("2024-06-22", "Jordan Price",  "Ryan Nash",      "Decision", True),
]


# ── Seed logic ──────────────────────────────────────────────────────────────

def build_fight_map(schedule):
    """Returns {name: [(opponent, result, method, date), ...]} for all fighters."""
    fights = {}
    for date_str, a, b, method, a_wins in schedule:
        if a not in fights: fights[a] = []
        if b not in fights: fights[b] = []
        if a_wins is True:
            fights[a].append((b, "W", method, date_str))
            fights[b].append((a, "L", method, date_str))
        elif a_wins is False:
            fights[a].append((b, "L", method, date_str))
            fights[b].append((a, "W", method, date_str))
        else:  # Draw
            fights[a].append((b, "D", method, date_str))
            fights[b].append((a, "D", method, date_str))
    return fights


def seed_sport(sport, fighter_defs, schedule):
    fight_map = build_fight_map(schedule)
    name_to_id = {}

    for name, weight, dob_str, county, desc in fighter_defs:
        dob = date.fromisoformat(dob_str) if dob_str else None
        f = Fighter(
            name=name, sport=sport, weight=weight,
            date_of_birth=dob, county=county, description=desc,
            created_at=datetime.utcnow(),
        )
        db.session.add(f)
        db.session.flush()
        rec = FighterRecord(fighter_id=f.id)
        db.session.add(rec)
        name_to_id[name] = f.id

    db.session.commit()

    for name, fid in name_to_id.items():
        f   = db.session.get(Fighter, fid)
        rec = f.record
        for opponent, result, method, fight_date in fight_map.get(name, []):
            h = FightHistory(
                fighter_id=fid,
                opponent_name=opponent,
                result=result,
                method=method,
                fight_date=fight_date,
            )
            db.session.add(h)
            if result == "W": rec.wins   += 1
            if result == "L": rec.losses += 1
            if result == "D": rec.draws  += 1

    db.session.commit()
    total_fights = sum(len(fight_map.get(n, [])) for n, *_ in fighter_defs)
    print(f"  {sport}: {len(fighter_defs)} fighters, {total_fights} fight records "
          f"({len(schedule)} bouts in schedule)")


def run():
    with app.app_context():
        print("Clearing existing fighters, records, and fight history...")
        FightHistory.query.delete()
        FighterRecord.query.delete()
        Fighter.query.delete()
        db.session.commit()

        seed_sport("boxing",     BOXING_FIGHTERS,     BOXING_SCHEDULE)
        seed_sport("mma",        MMA_FIGHTERS,        MMA_SCHEDULE)
        seed_sport("kickboxing", KICKBOXING_FIGHTERS, KICKBOXING_SCHEDULE)

        total = Fighter.query.count()
        print(f"\nDone. {total} fighters seeded across all sports.")


if __name__ == "__main__":
    run()
