from wreckommend.lastfm.lastfm_client import LastfmClient
from wreckommend.storage import cache


def _params_key(*parts: str) -> str:
    return "|".join(part.strip().lower() for part in parts)


def get_track_top_tags(conn, client: LastfmClient, artist: str, track: str) -> dict:
    params_key = _params_key(artist, track)
    cached = cache.get(conn, "lastfm", "track.getTopTags", params_key)
    if cached is not None:
        return cached

    response = client.get_track_top_tags(artist, track)
    with conn:
        cache.put(conn, "lastfm", "track.getTopTags", params_key, response)
    return response


def get_artist_top_tags(conn, client: LastfmClient, artist: str) -> dict:
    params_key = _params_key(artist)
    cached = cache.get(conn, "lastfm", "artist.getTopTags", params_key)
    if cached is not None:
        return cached

    response = client.get_artist_top_tags(artist)
    with conn:
        cache.put(conn, "lastfm", "artist.getTopTags", params_key, response)
    return response


def _extract_tags(response: dict) -> list[dict]:
    # Last.fm returns a single tag as a dict instead of a one-item list, so just normalizing for consistency
    tags = response.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        tags = [tags]
    return tags


def insert_track_tags(
    conn, entity_type: str, entity_id: str, response: dict, source: str
) -> None:
    for tag in _extract_tags(response):
        name = (tag.get("name") or "").strip().lower()
        if not name:
            continue
        try:
            weight = min(float(tag.get("count", 0)) / 100.0, 1.0)
        except (TypeError, ValueError):
            weight = 0.0

        track_tag_dict = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "tag": name,
            "weight": weight,
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
            response = get_track_top_tags(conn, client, artist_name, title)
            if _extract_tags(response):
                with conn:
                    insert_track_tags(
                        conn, "library_track", track_id, response, "lastfm_track"
                    )
                track_tag_count += 1
            else:
                artist_response = get_artist_top_tags(conn, client, artist_name)
                with conn:
                    insert_track_tags(
                        conn,
                        "library_track",
                        track_id,
                        artist_response,
                        "lastfm_artist",
                    )
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
