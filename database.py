from contextlib import contextmanager
import logging
import sqlite3
# Set up logging to record error messages
logger = logging.getLogger(__name__)
# Name of the SQLite database file where data will be stored
DB_PATH = "environment.db"
# Default min/max alert thresholds for temperature, humidity, and atmospheric pressure
DEFAULT_THRESHOLDS = {
    "temp_min": 0,
    "temp_max": 40,
    "humidity_min": 10,
    "humidity_max": 90,
    "pressure_min": 970,
    "pressure_max": 1030,
}
@contextmanager
def get_conn():
    """Helper function to automatically connect, commit changes, roll back errors, and close the database connection safely."""
    conn = sqlite3.connect(DB_PATH)
    # Enable accessing query results using column names (like a dictionary)
    conn.row_factory = sqlite3.Row
    try:
        yield conn  # Hand off the open connection to the code block using it
        conn.commit()  # Save changes if everything went smoothly
    except Exception:
        conn.rollback()  # Undo any partial changes if an error occurred
        raise  # Re-raise the exception so callers know something went wrong
    finally:
        conn.close()  # Always close the connection when done


def init_db():
    """Set up the SQLite database structure (tables) and insert initial settings if they don't exist yet."""
    with get_conn() as conn:
        # Create a table to store sensor measurements over time
        conn.execute("""CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            temperature REAL, humidity REAL, pressure REAL
        )""")

        # Create a table to store key-value configuration settings
        conn.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value REAL
        )""")

        # Populate settings with default threshold limits (only if keys don't already exist)
        for k, v in DEFAULT_THRESHOLDS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v),
            )


def save_reading(temp, humidity, pressure, timestamp):
    """Insert a single new sensor reading into the 'readings' table."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO readings (timestamp, temperature, humidity, pressure)"
                " VALUES (?, ?, ?, ?)",
                (timestamp, temp, humidity, pressure),
            )
    except Exception as e:
        logger.error(f"Failed to save reading: {e}")


def get_recent_readings(limit=100):
    """Fetch the latest sensor readings from the database, returned in chronological order (oldest to newest)."""
    with get_conn() as conn:
        # Retrieve the newest records first (ORDER BY id DESC) up to the specified limit
        rows = conn.execute(
            "SELECT * FROM readings ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    # Convert SQLite row objects to Python dictionaries and reverse the list so it's ordered chronologically
    return [dict(r) for r in reversed(rows)]


def get_thresholds():
    """Fetch all threshold setting values as a Python dictionary (e.g., {'temp_min': 0, ...})."""
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()

    # Convert the key-value rows into a standard dictionary
    return {r["key"]: r["value"] for r in rows}


def update_thresholds(new_values: dict):
    """Update threshold values in the 'settings' table using a dictionary of new values."""
    with get_conn() as conn:
        for k, v in new_values.items():
            # Only update values for valid/known threshold keys
            if k in DEFAULT_THRESHOLDS:
                conn.execute(
                    "UPDATE settings SET value = ? WHERE key = ?", (float(v), k)
                )
