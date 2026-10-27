import sqlite3
from contextlib import contextmanager
from pathlib import Path
from config import DATABASE_PATH

# Database file path
DATABASE = Path(__file__).parent / DATABASE_PATH

@contextmanager
def get_connection():
    """Yields a SQLite connection (dict-style rows) that commits on success,
    rolls back on error, and is always closed afterwards — sqlite3's own
    `with conn:` only does the commit/rollback part."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init_db():
    """Creates the required tables if they don't already exist."""
    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        # Users table (admin login)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Devices table (allowed RuuviTags)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT UNIQUE NOT NULL,
                name TEXT,
                location TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Measurements table (sensor readings)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                battery REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_measurements_mac_timestamp
            ON measurements (mac, timestamp)
        """)

        conn.commit()

def get_allowed_macs():
    """Fetches all allowed, active MAC addresses from the devices table and returns them as a set."""
    with get_connection() as conn:
        rows = conn.execute("SELECT mac FROM devices WHERE active = 1").fetchall()
        return {row["mac"] for row in rows}