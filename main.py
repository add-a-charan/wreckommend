from wreckommend import config
from wreckommend.navidrome.client import SubsonicClient
from wreckommend.navidrome.ingest import retrieve_all_albums, ingest
from wreckommend.storage.db import get_connection

client = SubsonicClient(
    config.URL, config.USER, config.PASSWORD, config.VERSION, config.CLIENT_NAME
)


def main():
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


if __name__ == "__main__":
    main()
