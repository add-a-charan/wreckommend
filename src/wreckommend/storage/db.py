import sqlite3
from wreckommend import config
from pathlib import Path


def get_connection():
    path = Path(config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent / "schema.sql").read_text()

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    return conn
