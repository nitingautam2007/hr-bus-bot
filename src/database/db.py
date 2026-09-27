import sqlite3
import os
from pathlib import Path
from src.config import DB_PATH

def get_db_connection(db_path: Path | str = None) -> sqlite3.Connection:
    """Returns a SQLite connection with foreign keys enabled and row_factory set."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Path | str = None):
    """Initializes tables and indexes in the SQLite database."""
    conn = get_db_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL COLLATE NOCASE,
            aliases TEXT DEFAULT '',
            depot TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            depot TEXT NOT NULL,
            from_station_id INTEGER NOT NULL REFERENCES stations(id),
            to_station_id INTEGER NOT NULL REFERENCES stations(id),
            via_station_id INTEGER REFERENCES stations(id),
            bus_type TEXT DEFAULT 'ORDINARY',
            operator TEXT DEFAULT 'HR',
            service_day TEXT DEFAULT 'ALL DAY',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(depot, from_station_id, to_station_id, via_station_id, bus_type, service_day)
        );

        CREATE TABLE IF NOT EXISTS departures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
            departure_time TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL,
            last_verified_at TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(route_id, departure_time)
        );

        CREATE INDEX IF NOT EXISTS idx_stations_name ON stations(name);
        CREATE INDEX IF NOT EXISTS idx_routes_from_to ON routes(from_station_id, to_station_id);
        CREATE INDEX IF NOT EXISTS idx_routes_via ON routes(via_station_id);
        CREATE INDEX IF NOT EXISTS idx_departures_route ON departures(route_id);
        CREATE INDEX IF NOT EXISTS idx_departures_time ON departures(departure_time);
        """)

        # Standardize common aliases
        conn.execute("UPDATE stations SET aliases = 'CHARKHI DADRI, DADRI' WHERE name = 'DADRI'")
        conn.execute("UPDATE stations SET aliases = 'BAHADURGARH, BHADURGARH' WHERE name = 'BHADURGARH'")
        conn.execute("UPDATE stations SET aliases = 'DELHI, ISBT DELHI, KASHMERE GATE' WHERE name = 'DELHI (ISBT)'")
        conn.execute("UPDATE stations SET aliases = 'GURGAON, GURUGRAM' WHERE name = 'GURUGRAM'")
        conn.execute("UPDATE stations SET aliases = 'AMBALA, AMBALA CANTT' WHERE name = 'AMBALA CANTT'")
        conn.execute("UPDATE stations SET aliases = 'AMBALA, AMBALA CITY' WHERE name = 'AMBALA CITY'")
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
