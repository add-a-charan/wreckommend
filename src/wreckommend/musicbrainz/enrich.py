import unicodedata

import requests

from wreckommend.musicbrainz.musicbrainz_client import MusicBrainzClient
from wreckommend.storage import cache

# how trustworthy a match is
_MIN_MATCH_SCORE = 90


def search_artist(conn, client: MusicBrainzClient, name: str) -> dict:
    return cache.get_or_fetch(
        conn,
        "musicbrainz",
        "artist.search",
        (name,),
        lambda: client.search_artist(name),
    )


def is_latin_script(text: str) -> bool:
    return all(
        not ch.isalpha() or unicodedata.name(ch, "").startswith("LATIN") for ch in text
    )


def _pick_latin_alias(artist_json: dict) -> str | None:
    candidates = []
    for alias in artist_json.get("aliases") or []:
        name = alias.get("name", "")
        if name and alias.get("type") == "Artist name" and is_latin_script(name):
            candidates.append((alias.get("primary") is True, name))
    if candidates:
        candidates.sort(key=lambda c: not c[0])
        return candidates[0][1]

    sort_name = artist_json.get("sort-name")
    if sort_name and is_latin_script(sort_name):
        return sort_name
    return None


def resolve_latin_name(
    conn, client: MusicBrainzClient, artist_name: str
) -> tuple[str | None, str | None]:
    response = search_artist(conn, client, artist_name)
    results = response.get("artists") or []
    if not results:
        return None, None

    best = max(results, key=lambda a: a.get("score", 0))
    if best.get("score", 0) < _MIN_MATCH_SCORE:
        return None, None
    return best.get("id"), _pick_latin_alias(best)


def enrich_artist_latin_names(conn, client: MusicBrainzClient) -> None:
    rows = conn.execute(
        "SELECT id, name FROM artists WHERE latin_name IS NULL"
    ).fetchall()
    targets = [
        (artist_id, name) for artist_id, name in rows if not is_latin_script(name)
    ]
    total = len(targets)
    resolved = 0

    for i, (artist_id, name) in enumerate(targets, start=1):
        try:
            mbid, latin_name = resolve_latin_name(conn, client, name)
        except requests.RequestException as e:
            print(f"[{i}/{total}] FAILED '{name}': {e}")
            continue

        if latin_name:
            resolved += 1
            with conn:
                conn.execute(
                    "UPDATE artists SET musicbrainz_id = ?, latin_name = ? WHERE id = ?",
                    (mbid, latin_name, artist_id),
                )

        if i % 10 == 0 or i == total:
            print(f"[{i}/{total}] resolved={resolved}")

    print(f"Done. {resolved}/{total} artists resolved to a Latin-script name.")


def fetch_all_genres(client: MusicBrainzClient) -> list[str]:
    names = []
    offset = 0
    while True:
        page = client.get_genres_page(offset)
        batch = page.get("genres") or []
        names.extend(g["name"] for g in batch)
        offset += len(batch)
        if offset >= page.get("genre-count", 0) or not batch:
            break
    return names


def sync_genre_whitelist(conn, client: MusicBrainzClient) -> int:
    names = fetch_all_genres(client)
    with conn:
        cache.put(conn, "musicbrainz", "genres", "all", {"genres": names})
    return len(names)
