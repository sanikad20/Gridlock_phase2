import sqlite3, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "gridlock_memory.db")
conn = sqlite3.connect(DB_PATH)

# Make sure tables exist even if main.py hasn't been imported yet
conn.executescript("""
CREATE TABLE IF NOT EXISTS events (
    id                    TEXT PRIMARY KEY,
    event_type            TEXT,
    event_cause           TEXT,
    latitude              REAL,
    longitude             REAL,
    zone                  TEXT,
    corridor              TEXT,
    priority              TEXT,
    requires_road_closure INTEGER,
    veh_type              TEXT,
    police_station        TEXT,
    junction              TEXT,
    hour                  INTEGER,
    day_of_week           INTEGER,
    month                 INTEGER,
    pred_severity         TEXT,
    pred_delay_mins       REAL,
    created_at            TEXT
);
CREATE TABLE IF NOT EXISTS outcomes (
    id                  TEXT PRIMARY KEY,
    event_id            TEXT REFERENCES events(id),
    actual_severity     TEXT,
    actual_delay_mins   REAL,
    officers_deployed   INTEGER,
    barricades_used     INTEGER,
    delay_reduced_pct   REAL,
    plan_used           TEXT,
    notes               TEXT,
    logged_at           TEXT
);
""")
conn.commit()

events = [
    ("EV-SEED01", "unplanned", "procession",       12.9000, 77.5700, "South Zone 1",  "Mysore Road",    "High", 1, "none", "Basavanagudi PS", None, 18, 6, 9,  "Severe",   123.0),
    ("EV-SEED02", "planned",   "public_event",      12.8700, 77.6000, "South Zone 2",  "Hosur Road",     "High", 1, "none", "Cubbon Park PS",  None, 19, 5, 4,  "Severe",   145.0),
    ("EV-SEED03", "unplanned", "protest",           13.0500, 77.5800, "North Zone 1",  "Bellary Road 1", "High", 1, "none", "Hebbal PS",       None, 10, 1, 3,  "Severe",   110.0),
    ("EV-SEED04", "unplanned", "accident",          12.9800, 77.6000, "Central Zone 2","ORR East 1",     "High", 0, "none", "Whitefield PS",   None, 9,  0, 6,  "Moderate", 78.0),
    ("EV-SEED05", "unplanned", "vehicle_breakdown", 12.9900, 77.6500, "East Zone 1",   "ORR East 1",     "High", 0, "truck","Whitefield PS",   None, 9,  0, 6,  "Moderate", 65.0),
]

outcomes = [
    ("EV-SEED01", "Severe",   120.0, 8,  4, 54.0, "Plan B — Mysore Road diversion via Kanakapura Road", "Ganesh Visarjan. Plan B reduced delay by 54%."),
    ("EV-SEED02", "Severe",   140.0, 10, 5, 41.0, "Plan A — Hosur Road alternate via Electronic City",  "IPL Chinnaswamy. Extra officers helped manage crowd."),
    ("EV-SEED03", "Moderate", 95.0,  6,  3, 38.0, "Plan C — Bellary Road diversion via Hebbal flyover", "Political rally near Mekhri Circle. Resolved faster."),
    ("EV-SEED04", "Moderate", 70.0,  4,  2, 32.0, "Plan A — Standard traffic management",               "Accident on ORR cleared faster than predicted."),
    ("EV-SEED05", "Moderate", 60.0,  4,  2, 28.0, "Plan A — Standard monitoring",                       "Truck breakdown on ORR. Tow truck dispatched quickly."),
]

for ev in events:
    try:
        conn.execute("""
            INSERT INTO events (
                id, event_type, event_cause, latitude, longitude,
                zone, corridor, priority, requires_road_closure,
                veh_type, police_station, junction,
                hour, day_of_week, month,
                pred_severity, pred_delay_mins, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (*ev, datetime.utcnow().isoformat()))
        print(f"✅ Inserted event {ev[0]}")
    except Exception as ex:
        print(f"⚠️ Skipped {ev[0]}: {ex}")

for i, oc in enumerate(outcomes):
    try:
        conn.execute("""
            INSERT INTO outcomes (
                id, event_id, actual_severity, actual_delay_mins,
                officers_deployed, barricades_used, delay_reduced_pct,
                plan_used, notes, logged_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (f"OUT-SEED0{i+1}", *oc, datetime.utcnow().isoformat()))
        print(f"✅ Inserted outcome OUT-SEED0{i+1}")
    except Exception as ex:
        print(f"⚠️ Skipped outcome {i+1}: {ex}")

conn.commit()
conn.close()
print("\n✅ 5 demo events seeded!")
