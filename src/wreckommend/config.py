import os
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(PROJECT_ROOT / ".env")

URL = os.getenv("SUBSONIC_URL")
USER = os.getenv("SUBSONIC_USER")
PASSWORD = os.getenv("SUBSONIC_PASSWORD")
VERSION = "1.16.1"
CLIENT_NAME = "wreckommend"
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "wreckommend.db"))
NAVIDROME_MUSIC_ROOT = os.getenv("NAVIDROME_MUSIC_ROOT")
