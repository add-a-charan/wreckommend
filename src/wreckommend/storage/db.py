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

    existing_candidates = {
        row[1] for row in conn.execute("PRAGMA table_info(candidate_tracks)")
    }
    if "tag_score" not in existing_candidates:
        conn.execute("ALTER TABLE candidate_tracks ADD COLUMN tag_score REAL")
    if "tag_score_nearest_track_id" not in existing_candidates:
        conn.execute(
            "ALTER TABLE candidate_tracks ADD COLUMN tag_score_nearest_track_id TEXT"
        )
    if "tag_score_computed_at" not in existing_candidates:
        conn.execute(
            "ALTER TABLE candidate_tracks ADD COLUMN tag_score_computed_at TEXT"
        )
    if "preview_url" not in existing_candidates:
        conn.execute("ALTER TABLE candidate_tracks ADD COLUMN preview_url TEXT")
    if "preview_fetched_at" not in existing_candidates:
        conn.execute(
            "ALTER TABLE candidate_tracks ADD COLUMN preview_fetched_at TEXT"
        )
    if "preview_path" not in existing_candidates:
        conn.execute("ALTER TABLE candidate_tracks ADD COLUMN preview_path TEXT")
    if "preview_downloaded_at" not in existing_candidates:
        conn.execute(
            "ALTER TABLE candidate_tracks ADD COLUMN preview_downloaded_at TEXT"
        )


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
