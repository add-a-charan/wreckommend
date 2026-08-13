from wreckommend import config
from wreckommend.lastfm.lastfm_client import LastfmClient
from wreckommend.lastfm.enrich import (
    get_track_top_tags,
    get_artist_top_tags,
    insert_track_tags,
)
from wreckommend.storage.db import get_connection

# Stankonia (OutKast) — 32 tracks, mainstream enough to sanity-check real tag data
ALBUM_ID = "46LaKE4a9GaNp2U6y4rXgz"


def _tag_names(response: dict) -> list[str]:
    tags = response.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        tags = [tags]
    return [t["name"] for t in tags]


client = LastfmClient(
    config.LASTFM_BASE_URL, config.LASTFM_API_KEY, config.CONTACT_EMAIL
)
conn = get_connection()

tracks = conn.execute(
    """
    SELECT t.id, t.title, a.name
    FROM tracks t
    JOIN artists a ON a.id = (
        SELECT ta.artist_id FROM track_artists ta
        WHERE ta.track_id = t.id AND ta.role = 'artist'
        ORDER BY ta.rowid LIMIT 1
    )
    WHERE t.album_id = ?
    """,
    (ALBUM_ID,),
).fetchall()

print(f"Testing {len(tracks)} tracks\n")

for track_id, title, artist_name in tracks:
    try:
        response = get_track_top_tags(conn, client, artist_name, title)
        names = _tag_names(response)
        if names:
            insert_track_tags(conn, "library_track", track_id, response, "lastfm_track")
            print(f"[track]  {artist_name} - {title}: {names[:5]}")
        else:
            artist_response = get_artist_top_tags(conn, client, artist_name)
            names = _tag_names(artist_response)
            insert_track_tags(
                conn, "library_track", track_id, artist_response, "lastfm_artist"
            )
            print(f"[artist] {artist_name} - {title}: {names[:5]}")
        conn.commit()
    except RuntimeError as e:
        print(f"[FAILED] {artist_name} - {title}: {e}")

conn.close()
