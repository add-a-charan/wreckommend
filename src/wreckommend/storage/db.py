import sqlite3
from pathlib import Path

from wreckommend import config


def _migrate(conn):
    # useful for adding new columns to existing tables
    existing = {row[1] for row in conn.execute("PRAGMA table_info(artists)")}
    if "musicbrainz_id" not in existing:
        conn.execute("ALTER TABLE artists ADD COLUMN musicbrainz_id TEXT")
    if "latin_name" not in existing:
        conn.execute("ALTER TABLE artists ADD COLUMN latin_name TEXT")


def get_connection():
    path = Path(config.APP_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent / "schema.sql").read_text()

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    _migrate(conn)
    return conn
