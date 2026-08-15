import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SUBSONIC_VERSION = "1.16.1"
SUBSONIC_URL = os.environ["SUBSONIC_URL"]
SUBSONIC_USER = os.environ["SUBSONIC_USER"]
SUBSONIC_PASSWORD = os.environ["SUBSONIC_PASSWORD"]
SUBSONIC_MUSIC_ROOT = os.environ["NAVIDROME_MUSIC_ROOT"]

APP_CLIENT_NAME = "wreckommend"
APP_DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "wreckommend.db"))
APP_CONTACT_EMAIL = os.environ["CONTACT_EMAIL"]

LASTFM_API_KEY = os.environ["LASTFM_API_KEY"]
LASTFM_URL = "http://ws.audioscrobbler.com/2.0/"

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/"
