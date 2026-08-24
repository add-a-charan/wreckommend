from pathlib import Path

from wreckommend import config
from wreckommend.subsonic.subsonic_client import SubsonicClient


def resolve_track_path(client: SubsonicClient, track: dict) -> Path:
    """Local file for this library track, downloading and caching it via
    Subsonic's stream endpoint if not already on disk. Streaming straight
    from the endpoint URL (e.g. via `afplay <url>`) doesn't work reliably
    for lossless formats served this way, so we always play a local copy."""
    suffix = track.get("suffix") or "audio"
    config.APP_STREAM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.APP_STREAM_CACHE_DIR / f"{track['id']}.{suffix}"
    if path.exists():
        return path

    audio = client.stream(track["id"])
    path.write_bytes(audio)
    return path
