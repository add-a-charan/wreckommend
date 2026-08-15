import argparse

from wreckommend.clients import build_lastfm_client, build_subsonic_client
from wreckommend.lastfm import tags
from wreckommend.lastfm.enrich import enrich_library_tracks
from wreckommend.subsonic.ingest import (
    is_album_unchanged,
    ingest,
    insert_album,
    retrieve_album_tracks,
    retrieve_all_albums,
)
from wreckommend.storage.db import get_connection


def cmd_ping(args):
    client = build_subsonic_client()
    response = client.ping()
    print(f"Navidrome reachable (status={response['status']})")
    print(response)


def cmd_ingest(args):
    client = build_subsonic_client()
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


def cmd_enrich(args):
    client = build_lastfm_client()
    conn = get_connection()
    try:
        enrich_library_tracks(conn, client)
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

    subparsers.add_parser("ping", help="Check connectivity to the Navidrome server")
    subparsers.add_parser("ingest", help="Ingest tracks from Navidrome")
    subparsers.add_parser("enrich", help="Enrich library tracks with Last.fm tags")

    report_parser = subparsers.add_parser(
        "report-top-tags",
        help="Dump top library tags by frequency for stoplist/synonym curation",
    )
    report_parser.add_argument("--limit", type=int, default=200)

    nearest_parser = subparsers.add_parser(
        "nearest", help="Find nearest library tracks by tag vector for a given track"
    )
    nearest_parser.add_argument("query", help="Substring to match against track title")
    nearest_parser.add_argument("--top-n", type=int, default=10)

    args = parser.parse_args()

    if args.command == "ping":
        cmd_ping(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "enrich":
        cmd_enrich(args)
    elif args.command == "report-top-tags":
        cmd_report_top_tags(args)
    elif args.command == "nearest":
        cmd_nearest(args)


if __name__ == "__main__":
    main()
