from wreckommend import config
from wreckommend.navidrome.client import SubsonicClient
import json

client = SubsonicClient(
    config.URL, config.USER, config.PASSWORD, config.VERSION, config.CLIENT_NAME
)


def main():
    albums = client.getAlbumList2("random")["albumList2"].get("album", [])
    print(json.dumps(client.getAlbum(albums[0]["id"]), indent=2))


if __name__ == "__main__":
    main()
