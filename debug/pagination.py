from wreckommend import config
from wreckommend.navidrome.client import SubsonicClient
import json

client = SubsonicClient(
    config.URL, config.USER, config.PASSWORD, config.VERSION, config.CLIENT_NAME
)

albums = []
offset = 0
size = 500
while True:
    page = client.getAlbumList2("alphabeticalByName", size=size, offset=offset)
    batch = page["albumList2"].get("album", [])
    albums.extend(batch)
    if len(batch) < size:
        break
    offset += size

album = client.getAlbum(albums[0]["id"])
print(json.dumps(album["album"]["song"][0], indent=2))
