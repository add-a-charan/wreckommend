from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable

from wreckommend import config
from wreckommend.deezer.deezer_client import DeezerClient
from wreckommend.storage import cache


def search_track(
    conn, client: DeezerClient, artist: str, title: str, force: bool = False
) -> dict:
    if force:
        response = client.search_track(artist, title)
        with conn:
            cache.put(
                conn, "deezer", "search", cache.params_key(artist, title), response
            )
        return response

    return cache.get_or_fetch(
        conn,
        "deezer",
        "search",
        (artist, title),
        lambda: client.search_track(artist, title),
    )


def _best_match(response: dict) -> dict | None:
    results = response.get("data") or []
    return results[0] if results else None


def _persist_preview(conn, candidate_id: str, preview_url: str | None) -> None:
    conn.execute(
        """
        UPDATE candidate_tracks
        SET preview_url = ?, preview_fetched_at = ?
        WHERE id = ?
        """,
        (preview_url, datetime.now(UTC).isoformat(), candidate_id),
    )


def fetch_preview(
    conn,
    client: DeezerClient,
    candidate_id: str,
    artist_name: str,
    title: str,
    force: bool = False,
) -> str | None:
    response = search_track(conn, client, artist_name, title, force=force)
    match = _best_match(response)
    preview_url = (match or {}).get("preview") or None
    with conn:
        _persist_preview(conn, candidate_id, preview_url)
    return preview_url


def _persist_download(conn, candidate_id: str, path: Path) -> None:
    conn.execute(
        """
        UPDATE candidate_tracks
        SET preview_path = ?, preview_downloaded_at = ?
        WHERE id = ?
        """,
        (str(path), datetime.now(UTC).isoformat(), candidate_id),
    )


def download_preview(
    conn,
    client: DeezerClient,
    candidate_id: str,
    preview_url: str,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Download 30s MP3 preview for candidate with existing
    preview_url. Saved at config.APP_PREVIEW_DIR."""
    audio = client.download_preview(preview_url, on_progress=on_progress)

    config.APP_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path = config.APP_PREVIEW_DIR / f"{candidate_id}.mp3"
    path.write_bytes(audio)

    with conn:
        _persist_download(conn, candidate_id, path)
    return path


def _undownloaded_previews(conn, limit: int) -> list[tuple[str, str, str, str]]:
    return conn.execute(
        """
        SELECT id, title, artist_name, preview_url
        FROM candidate_tracks
        WHERE preview_url IS NOT NULL AND preview_path IS NULL
        ORDER BY tag_score DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def download_previews(conn, client: DeezerClient, limit: int = 25) -> None:
    """Download preview MP3s for all candidates that have a
    preview_url but haven't been downloaded yet. Run `fetch-previews` first
    to populate preview_url."""
    rows = _undownloaded_previews(conn, limit)
    if not rows:
        print(
            "Nothing to download: run `fetch-previews` first, or all fetched "
            "previews are already downloaded."
        )
        return

    total = len(rows)
    downloaded = 0
    failed = 0

    for i, (candidate_id, title, artist_name, preview_url) in enumerate(rows, start=1):
        try:
            download_preview(conn, client, candidate_id, preview_url)
            downloaded += 1
        except Exception as e:
            failed += 1
            print(f"[{i}/{total}] FAILED '{artist_name} - {title}': {e}")
            continue

        if i % 10 == 0 or i == total:
            print(f"[{i}/{total}] downloaded={downloaded} failed={failed}")

    print(f"Done. {downloaded} previews downloaded, {failed} failed, out of {total}.")


def _unfetched_top_candidates(conn, limit: int) -> list[tuple[str, str, str]]:
    return conn.execute(
        """
        SELECT id, title, artist_name
        FROM candidate_tracks
        WHERE tag_score IS NOT NULL AND preview_fetched_at IS NULL
        ORDER BY tag_score DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def fetch_previews(conn, client: DeezerClient, limit: int = 25) -> None:
    """Fetch Deezer preview URLs for top-scored candidates that don't have
    one yet. Do not fetch previews for the entire candidate pool, this is a reranking step, not data enrichment."""
    rows = _unfetched_top_candidates(conn, limit)
    if not rows:
        print(
            "Nothing to fetch: run `score` first, or all top candidates already "
            "have a preview lookup on file."
        )
        return

    total = len(rows)
    found = 0
    missing = 0
    failed = 0

    for i, (candidate_id, title, artist_name) in enumerate(rows, start=1):
        try:
            preview_url = fetch_preview(conn, client, candidate_id, artist_name, title)
        except RuntimeError as e:
            failed += 1
            print(f"[{i}/{total}] FAILED '{artist_name} - {title}': {e}")
            continue

        if preview_url:
            found += 1
        else:
            missing += 1

        if i % 10 == 0 or i == total:
            print(f"[{i}/{total}] found={found} missing={missing} failed={failed}")

    print(
        f"Done. {found} previews found, {missing} with no Deezer match, "
        f"{failed} failed, out of {total}."
    )
