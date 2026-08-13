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
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL")
NAVIDROME_MUSIC_ROOT = os.getenv("NAVIDROME_MUSIC_ROOT")

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_BASE_URL = "http://ws.audioscrobbler.com/2.0/"
