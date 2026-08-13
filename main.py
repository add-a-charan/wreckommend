import argparse

from wreckommend import config
from wreckommend.navidrome.client import SubsonicClient
from wreckommend.navidrome.ingest import retrieve_all_albums, ingest
from wreckommend.lastfm.lastfm_client import LastfmClient
from wreckommend.lastfm.enrich import enrich_library_tracks
from wreckommend.storage.db import get_connection


def build_subsonic_client() -> SubsonicClient:
    return SubsonicClient(
        config.URL, config.USER, config.PASSWORD, config.VERSION, config.CLIENT_NAME
    )


def build_lastfm_client() -> LastfmClient:
    return LastfmClient(
        config.LASTFM_BASE_URL, config.LASTFM_API_KEY, config.CONTACT_EMAIL
    )


def cmd_ingest(args):
    client = build_subsonic_client()
    albums = retrieve_all_albums(client)
    print(f"Found {len(albums)} albums")

    conn = get_connection()
    try:
        for i, album in enumerate(albums, start=1):
            tracks = client.getAlbum(album["id"])["album"]["song"]
            ingest(conn, tracks)
            print(
                f"[{i}/{len(albums)}] Ingested '{album.get('name')}' ({len(tracks)} tracks)"
            )
    finally:
        conn.close()


def cmd_enrich(args):
    client = build_lastfm_client()
    conn = get_connection()
    try:
        enrich_library_tracks(conn, client)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(prog="wreckommend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ingest", help="Ingest tracks from Navidrome")
    subparsers.add_parser("enrich", help="Enrich library tracks with Last.fm tags")

    args = parser.parse_args()

    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "enrich":
        cmd_enrich(args)


if __name__ == "__main__":
    main()
