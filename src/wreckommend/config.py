import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

URL = os.getenv("SUBSONIC_URL")
USER = os.getenv("SUBSONIC_USER")
PASSWORD = os.getenv("SUBSONIC_PASSWORD")
VERSION = "1.16.1"
CLIENT_NAME = "wreckommend"
DB_PATH = os.getenv("DB_PATH", "wreckommend.db")
