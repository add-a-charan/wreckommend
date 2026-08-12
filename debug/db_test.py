from wreckommend import config
from wreckommend.navidrome.client import SubsonicClient
from wreckommend.navidrome.ingest import ingest
import json
from wreckommend.storage.db import get_connection

client = SubsonicClient(
    config.URL, config.USER, config.PASSWORD, config.VERSION, config.CLIENT_NAME
)

albums = []
page = client.getAlbumList2("alphabeticalByName", size=9, offset=0)
batch = page["albumList2"].get("album", [])
albums.extend(batch)

album = client.getAlbum(albums[8]["id"])
conn = get_connection()
ingest(conn, album["album"]["song"])
conn.close()
