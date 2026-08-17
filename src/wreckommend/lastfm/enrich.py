from wreckommend.lastfm.lastfm_client import LastfmClient
from wreckommend.storage import cache

# Last.fm tag `count` is relative to the track's top tag.
# Used to drop noisy tags (things that don't actually describe the track, like "fav" or "seen live")
_MIN_TAG_COUNT = 25


def get_track_top_tags(conn, client: LastfmClient, artist: str, track: str) -> dict:
    return cache.get_or_fetch(
        conn,
        "lastfm",
        "track.getTopTags",
        (artist, track),
        lambda: client.get_track_top_tags(artist, track),
    )


def get_artist_top_tags(conn, client: LastfmClient, artist: str) -> dict:
    return cache.get_or_fetch(
        conn,
        "lastfm",
        "artist.getTopTags",
        (artist,),
        lambda: client.get_artist_top_tags(artist),
    )


def _extract_tags(response: dict) -> list[dict]:
    # Last.fm returns a single tag as a dict instead of a one-item list, so just normalizing for consistency
    tags = response.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        tags = [tags]
    return tags


def _filter_relevant_tag_names(response: dict) -> list[str]:
    names = []
    for tag in _extract_tags(response):
        name = (tag.get("name") or "").strip().lower()
        if not name:
            continue
        try:
            count = float(tag.get("count", 0))
        except (TypeError, ValueError):
            continue
        if count < _MIN_TAG_COUNT:
            continue
        names.append(name)
    return names


def insert_track_tags(
    conn, entity_type: str, entity_id: str, response: dict, source: str
) -> None:
    for name in _filter_relevant_tag_names(response):
        track_tag_dict = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "tag": name,
            "weight": 1.0,
            "source": source,
        }
        track_tag_sql = """
            INSERT INTO track_tags (
                entity_type,
                entity_id,
                tag,
                weight,
                source
            )
            VALUES (
                :entity_type,
                :entity_id,
                :tag,
                :weight,
                :source
            )
            ON CONFLICT(entity_type, entity_id, tag, source) DO UPDATE SET
                weight = excluded.weight
        """
        conn.execute(track_tag_sql, track_tag_dict)


def tag_entity(
    conn,
    client: LastfmClient,
    entity_type: str,
    entity_id: str,
    artist_name: str,
    title: str,
) -> str:
    """Tags one entity via track tags, falling back to artist tags. Returns 'track' or 'artist'."""
    response = get_track_top_tags(conn, client, artist_name, title)
    if _filter_relevant_tag_names(response):
        with conn:
            insert_track_tags(conn, entity_type, entity_id, response, "lastfm_track")
        return "track"

    artist_response = get_artist_top_tags(conn, client, artist_name)
    with conn:
        insert_track_tags(
            conn, entity_type, entity_id, artist_response, "lastfm_artist"
        )
    return "artist"


def _get_library_tracks(conn) -> list[tuple[str, str, str]]:
    return conn.execute(
        """
        SELECT t.id, t.title, a.name
        FROM tracks t
        JOIN artists a ON a.id = (
            SELECT ta.artist_id FROM track_artists ta
            WHERE ta.track_id = t.id AND ta.role = 'artist'
            ORDER BY ta.rowid LIMIT 1
        )
        """
    ).fetchall()


def enrich_library_tracks(conn, client: LastfmClient) -> None:
    tracks = _get_library_tracks(conn)
    total = len(tracks)
    track_tag_count = 0
    artist_tag_count = 0
    failed_count = 0

    for i, (track_id, title, artist_name) in enumerate(tracks, start=1):
        try:
            source = tag_entity(
                conn, client, "library_track", track_id, artist_name, title
            )
            if source == "track":
                track_tag_count += 1
            else:
                artist_tag_count += 1
        except RuntimeError as e:
            failed_count += 1
            print(f"[{i}/{total}] FAILED '{artist_name} - {title}': {e}")
            continue

        if i % 25 == 0 or i == total:
            print(
                f"[{i}/{total}] track-tags={track_tag_count} "
                f"artist-fallback={artist_tag_count} failed={failed_count}"
            )

    print(
        f"Done. {track_tag_count} via track tags, {artist_tag_count} via artist "
        f"fallback, {failed_count} failed, out of {total} tracks."
    )
