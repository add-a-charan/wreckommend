import argparse

from wreckommend.clients import (
    build_deezer_client,
    build_lastfm_client,
    build_musicbrainz_client,
    build_subsonic_client,
)
from wreckommend.deezer.preview import download_previews, fetch_previews
from wreckommend.lastfm import tags
from wreckommend.lastfm.candidates import discover_candidates
from wreckommend.lastfm.enrich import enrich_library_tracks
from wreckommend.musicbrainz.enrich import sync_genre_whitelist
from wreckommend.scoring import score_candidates, top_candidates
from wreckommend.subsonic.ingest import (
    is_album_unchanged,
    ingest,
    insert_album,
    retrieve_album_tracks,
    retrieve_all_albums,
)
from wreckommend.storage.db import get_connection


def cmd_ping(args, client):
    response = client.ping()
    print(f"Navidrome reachable (status={response['status']})")
    print(response)


def cmd_ingest(args, client):
    albums = retrieve_all_albums(client)
    print(f"Found {len(albums)} albums")

    conn = get_connection()
    try:
        skipped = 0
        for i, album in enumerate(albums, start=1):
            if is_album_unchanged(conn, album):
                skipped += 1
                continue
            tracks = retrieve_album_tracks(client, album)
            ingest(conn, tracks)
            with conn:
                insert_album(conn, album)
            print(
                f"[{i}/{len(albums)}] Ingested '{album.get('name')}' ({len(tracks)} tracks)"
            )
        print(f"Skipped {skipped} unchanged albums")
    finally:
        conn.close()


def cmd_enrich(args, client):
    conn = get_connection()
    try:
        enrich_library_tracks(conn, client)
    finally:
        conn.close()


def cmd_discover(args, client):
    conn = get_connection()
    try:
        discover_candidates(conn, client)
    finally:
        conn.close()


def cmd_score(args):
    conn = get_connection()
    try:
        score_candidates(conn)
    finally:
        conn.close()


def cmd_top_candidates(args):
    conn = get_connection()
    try:
        rows = top_candidates(conn, limit=args.limit)
        if not rows:
            print("No scored candidates yet. Run `score` first.")
            return
        for title, artist_name, tag_score, discovered_via, source, preview_url in rows:
            line = f"{tag_score:.3f}  {artist_name} - {title}  (via {discovered_via}, {source})"
            if preview_url:
                line += f"\n           {preview_url}"
            print(line)
    finally:
        conn.close()


def cmd_fetch_previews(args, client):
    conn = get_connection()
    try:
        fetch_previews(conn, client, limit=args.limit)
    finally:
        conn.close()


def cmd_download_previews(args, client):
    conn = get_connection()
    try:
        download_previews(conn, client, limit=args.limit)
    finally:
        conn.close()


def cmd_sync_genres(args, client):
    conn = get_connection()
    try:
        count = sync_genre_whitelist(conn, client)
        print(f"Synced {count} MusicBrainz genres into the local whitelist.")
    finally:
        conn.close()


def cmd_report_top_tags(args):
    conn = get_connection()
    try:
        for tag, n in tags.report_top_tags(conn, limit=args.limit):
            print(f"{n:5d}  {tag}")
    finally:
        conn.close()


def cmd_nearest(args):
    conn = get_connection()
    try:
        entity_ids, _vectorizer, matrix = tags.vectorize_library(conn)

        row = conn.execute(
            "SELECT id FROM tracks WHERE title LIKE ? LIMIT 1", (f"%{args.query}%",)
        ).fetchone()
        if row is None:
            print(f"No track matching '{args.query}'")
            return

        target_id = row[0]
        if target_id not in entity_ids:
            print(
                f"'{args.query}' matched a track with no tags after cleaning; can't vectorize."
            )
            return

        tags.print_nearest(conn, entity_ids, matrix, target_id, top_n=args.top_n)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(prog="wreckommend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ping_parser = subparsers.add_parser(
        "ping", help="Check connectivity to the Navidrome server"
    )
    ping_parser.set_defaults(func=cmd_ping, client_builder=build_subsonic_client)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest tracks from Navidrome")
    ingest_parser.set_defaults(func=cmd_ingest, client_builder=build_subsonic_client)

    enrich_parser = subparsers.add_parser(
        "enrich", help="Enrich library tracks with Last.fm tags"
    )
    enrich_parser.set_defaults(func=cmd_enrich, client_builder=build_lastfm_client)

    discover_parser = subparsers.add_parser(
        "discover",
        help="Discover candidate tracks outside the library via Last.fm similar artists",
    )
    discover_parser.set_defaults(func=cmd_discover, client_builder=build_lastfm_client)

    score_parser = subparsers.add_parser(
        "score",
        help="Score candidate tracks against liked library tracks in shared tag space",
    )
    score_parser.set_defaults(func=cmd_score, client_builder=None)

    top_candidates_parser = subparsers.add_parser(
        "top-candidates", help="List highest-scored candidate tracks"
    )
    top_candidates_parser.add_argument("--limit", type=int, default=25)
    top_candidates_parser.set_defaults(func=cmd_top_candidates, client_builder=None)

    fetch_previews_parser = subparsers.add_parser(
        "fetch-previews",
        help="Fetch Deezer 30s preview URLs for the top-scored candidate tracks",
    )
    fetch_previews_parser.add_argument("--limit", type=int, default=25)
    fetch_previews_parser.set_defaults(
        func=cmd_fetch_previews, client_builder=build_deezer_client
    )

    download_previews_parser = subparsers.add_parser(
        "download-previews",
        help="Download preview MP3s to disk for candidates that already have a preview_url",
    )
    download_previews_parser.add_argument("--limit", type=int, default=25)
    download_previews_parser.set_defaults(
        func=cmd_download_previews, client_builder=build_deezer_client
    )

    sync_genres_parser = subparsers.add_parser(
        "sync-genres",
        help="Refresh the local MusicBrainz genre whitelist used to clean tags",
    )
    sync_genres_parser.set_defaults(
        func=cmd_sync_genres, client_builder=build_musicbrainz_client
    )

    report_parser = subparsers.add_parser(
        "report-top-tags",
        help="Dump top library tags by frequency for stoplist/synonym curation",
    )
    report_parser.add_argument("--limit", type=int, default=200)
    report_parser.set_defaults(func=cmd_report_top_tags, client_builder=None)

    nearest_parser = subparsers.add_parser(
        "nearest", help="Find nearest library tracks by tag vector for a given track"
    )
    nearest_parser.add_argument("query", help="Substring to match against track title")
    nearest_parser.add_argument("--top-n", type=int, default=10)
    nearest_parser.set_defaults(func=cmd_nearest, client_builder=None)

    args = parser.parse_args()

    if args.client_builder is None:
        args.func(args)
    else:
        args.func(args, args.client_builder())


if __name__ == "__main__":
    main()
