from datetime import UTC, datetime

from wreckommend.lastfm.enrich import tag_entity
from wreckommend.lastfm.lastfm_client import LastfmClient
from wreckommend.lastfm.tags import load_artist_names, normalize
from wreckommend.storage import cache

# Seed discovery from artists the user has rated highly, and never surface
# artists the user has rated poorly, even if Last.fm considers them similar
# to a liked artist.
LIKED_RATING_THRESHOLD = 4
DISLIKED_RATING_THRESHOLD = 2


def get_similar_artists(
    conn, client: LastfmClient, artist: str, limit: int = 15
) -> dict:
    return cache.get_or_fetch(
        conn,
        "lastfm",
        "artist.getSimilar",
        (artist, str(limit)),
        lambda: client.get_similar_artists(artist, limit=limit),
    )


def get_artist_top_tracks(
    conn, client: LastfmClient, artist: str, limit: int = 10
) -> dict:
    return cache.get_or_fetch(
        conn,
        "lastfm",
        "artist.getTopTracks",
        (artist, str(limit)),
        lambda: client.get_artist_top_tracks(artist, limit=limit),
    )


def get_similar_tracks(
    conn, client: LastfmClient, artist: str, track: str, limit: int = 15
) -> dict:
    return cache.get_or_fetch(
        conn,
        "lastfm",
        "track.getSimilar",
        (artist, track, str(limit)),
        lambda: client.get_similar_tracks(artist, track, limit=limit),
    )


def _extract_similar_artists(response: dict) -> list[dict]:
    artists = response.get("similarartists", {}).get("artist", [])
    if isinstance(artists, dict):
        artists = [artists]
    return artists


def _extract_top_tracks(response: dict) -> list[dict]:
    tracks = response.get("toptracks", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]
    return tracks


def _extract_similar_tracks(response: dict) -> list[dict]:
    tracks = response.get("similartracks", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]
    return tracks


def _rated_library_artists(conn) -> list[tuple[str, float]]:
    return conn.execute(
        """
        SELECT a.name, AVG(t.user_rating)
        FROM artists a
        JOIN track_artists ta ON ta.artist_id = a.id AND ta.role = 'artist'
        JOIN tracks t ON t.id = ta.track_id
        WHERE t.user_rating IS NOT NULL
        GROUP BY a.id
        """
    ).fetchall()


def _rated_library_tracks(conn) -> list[tuple[str, str]]:
    return conn.execute(
        """
        SELECT t.title, a.name
        FROM tracks t
        JOIN artists a ON a.id = (
            SELECT ta.artist_id FROM track_artists ta
            WHERE ta.track_id = t.id AND ta.role = 'artist'
            ORDER BY ta.rowid LIMIT 1
        )
        WHERE t.user_rating >= ?
        """,
        (LIKED_RATING_THRESHOLD,),
    ).fetchall()


def _seed_and_excluded_artists(conn) -> tuple[list[str], set[str]]:
    rated = _rated_library_artists(conn)
    owned = load_artist_names(conn)

    liked = [name for name, avg in rated if avg >= LIKED_RATING_THRESHOLD]
    disliked = {
        normalize(name) for name, avg in rated if avg <= DISLIKED_RATING_THRESHOLD
    }
    return liked, owned | disliked


def insert_candidate_track(
    conn,
    candidate_id: str,
    title: str,
    artist_name: str,
    artist_mbid: str | None,
    track_mbid: str | None,
    discovered_via: str,
    source: str,
) -> None:
    candidate_dict = {
        "id": candidate_id,
        "title": title,
        "artist_name": artist_name,
        "artist_mbid": artist_mbid,
        "track_mbid": track_mbid,
        "discovered_via": discovered_via,
        "source": source,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    sql = """
        INSERT INTO candidate_tracks (
            id, title, artist_name, artist_mbid, track_mbid, discovered_via, source, fetched_at
        )
        VALUES (
            :id, :title, :artist_name, :artist_mbid, :track_mbid, :discovered_via, :source, :fetched_at
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            artist_name = excluded.artist_name,
            artist_mbid = excluded.artist_mbid,
            track_mbid = excluded.track_mbid,
            discovered_via = excluded.discovered_via,
            fetched_at = excluded.fetched_at
    """
    conn.execute(sql, candidate_dict)


def _find_candidate_artists(
    conn,
    client: LastfmClient,
    seeds: list[str],
    excluded: set[str],
    similar_per_seed: int,
) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for seed in seeds:
        try:
            response = get_similar_artists(conn, client, seed, limit=similar_per_seed)
        except RuntimeError as e:
            print(f"FAILED similar-artists for '{seed}': {e}")
            continue

        for entry in _extract_similar_artists(response):
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            key = normalize(name)
            if key in excluded or key in found:
                continue
            found[key] = (name, seed)
    return found


def _find_candidate_tracks(
    conn,
    client: LastfmClient,
    seed_tracks: list[tuple[str, str]],
    excluded: set[str],
    similar_per_seed: int,
) -> dict[str, tuple[str, str, str | None, str | None, str]]:
    found: dict[str, tuple[str, str, str | None, str | None, str]] = {}
    for title, artist in seed_tracks:
        try:
            response = get_similar_tracks(
                conn, client, artist, title, limit=similar_per_seed
            )
        except RuntimeError as e:
            print(f"FAILED similar-tracks for '{artist} - {title}': {e}")
            continue

        seed_label = f"{artist} - {title}"
        for entry in _extract_similar_tracks(response):
            name = (entry.get("name") or "").strip()
            entry_artist = entry.get("artist") or {}
            artist_name = (entry_artist.get("name") or "").strip()
            if not name or not artist_name:
                continue
            artist_key = normalize(artist_name)
            if artist_key in excluded:
                continue
            candidate_id = f"lastfm:{artist_key}:{normalize(name)}"
            if candidate_id in found:
                continue
            found[candidate_id] = (
                name,
                artist_name,
                entry_artist.get("mbid") or None,
                entry.get("mbid") or None,
                seed_label,
            )
    return found


def _insert_and_tag_candidate(
    conn,
    client: LastfmClient,
    candidate_id: str,
    title: str,
    artist_name: str,
    artist_mbid: str | None,
    track_mbid: str | None,
    discovered_via: str,
    source: str,
) -> None:
    with conn:
        insert_candidate_track(
            conn,
            candidate_id=candidate_id,
            title=title,
            artist_name=artist_name,
            artist_mbid=artist_mbid,
            track_mbid=track_mbid,
            discovered_via=discovered_via,
            source=source,
        )
    tag_entity(conn, client, "candidate_track", candidate_id, artist_name, title)


def discover_candidates(
    conn,
    client: LastfmClient,
    similar_per_seed: int = 15,
    tracks_per_artist: int = 10,
) -> None:
    seeds, excluded = _seed_and_excluded_artists(conn)
    if not seeds:
        print(
            "No library artists rated >= "
            f"{LIKED_RATING_THRESHOLD} stars; nothing to seed discovery with."
        )
        return

    track_count = 0
    failed_count = 0

    print(
        f"Seeding artist-level discovery from {len(seeds)} liked artists "
        f"({len(excluded)} owned/disliked artists excluded from results)"
    )
    candidate_artists = _find_candidate_artists(
        conn, client, seeds, excluded, similar_per_seed
    )
    print(f"Found {len(candidate_artists)} new candidate artists")

    total = len(candidate_artists)
    for i, (artist_name, seed) in enumerate(candidate_artists.values(), start=1):
        try:
            response = get_artist_top_tracks(
                conn, client, artist_name, limit=tracks_per_artist
            )
        except RuntimeError as e:
            failed_count += 1
            print(f"FAILED top-tracks for '{artist_name}': {e}")
            continue

        for track in _extract_top_tracks(response):
            title = (track.get("name") or "").strip()
            if not title:
                continue
            candidate_id = f"lastfm:{normalize(artist_name)}:{normalize(title)}"
            try:
                _insert_and_tag_candidate(
                    conn,
                    client,
                    candidate_id,
                    title,
                    artist_name,
                    (track.get("artist") or {}).get("mbid") or None,
                    track.get("mbid") or None,
                    seed,
                    "lastfm_similar_artist",
                )
                track_count += 1
            except RuntimeError as e:
                failed_count += 1
                print(f"FAILED tagging '{artist_name} - {title}': {e}")

        if i % 10 == 0 or i == total:
            print(f"[{i}/{total}] candidate tracks tagged so far: {track_count}")

    print(f"Done with artist-level discovery. {total} candidate artists processed.")

    seed_tracks = _rated_library_tracks(conn)
    print(
        f"Seeding track-level discovery from {len(seed_tracks)} liked tracks "
        f"({len(excluded)} owned/disliked artists excluded from results)"
    )
    candidate_tracks = _find_candidate_tracks(
        conn, client, seed_tracks, excluded, similar_per_seed
    )
    print(f"Found {len(candidate_tracks)} new candidate tracks via track similarity")

    total_tt = len(candidate_tracks)
    for i, (candidate_id, candidate) in enumerate(candidate_tracks.items(), start=1):
        title, artist_name, artist_mbid, track_mbid, seed_label = candidate
        try:
            _insert_and_tag_candidate(
                conn,
                client,
                candidate_id,
                title,
                artist_name,
                artist_mbid,
                track_mbid,
                seed_label,
                "lastfm_similar_track",
            )
            track_count += 1
        except RuntimeError as e:
            failed_count += 1
            print(f"FAILED tagging '{artist_name} - {title}': {e}")

        if i % 10 == 0 or i == total_tt:
            print(f"[{i}/{total_tt}] track-similarity candidates tagged so far")

    print(
        f"Done. {track_count} total candidate tracks tagged ({failed_count} failures)."
    )
