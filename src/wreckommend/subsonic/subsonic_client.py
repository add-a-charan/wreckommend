import hashlib
import secrets

from wreckommend.core.http_client import ApiClient


class SubsonicClient(ApiClient):
    def __init__(
        self, url: str, user: str, password: str, version: str, client_name: str
    ):
        super().__init__(url)
        self.user = user
        self.password = password
        self.version = version
        self.client_name = client_name

    def _auth_params(self) -> dict:
        salt = secrets.token_hex(16)
        token = hashlib.md5((self.password + salt).encode("utf-8")).hexdigest()
        params = {
            "u": self.user,
            "t": token,
            "s": salt,
            "v": self.version,
            "c": self.client_name,
            "f": "json",
        }
        return params

    def _request(self, method: str, params: dict | None = None) -> dict:
        request_params = (params or {}) | self._auth_params()
        response = self._get(f"{self.url}/rest/{method}.view", request_params)
        data = response["subsonic-response"]
        if data["status"] != "ok":
            error = data.get("error", {})
            self._raise_error("Subsonic", error.get("code"), error.get("message"))
        return data

    def ping(self) -> dict:
        return self._request("ping")

    def get_album_list2(
        self,
        list_type: str,
        size: int = 10,
        offset: int = 0,
        from_year: int | None = None,
        to_year: int | None = None,
        genre: str | None = None,
        music_folder_id: str | None = None,
    ) -> dict:
        if list_type == "byYear" and (from_year is None or to_year is None):
            raise ValueError(
                "from_year and to_year are required when list_type is 'byYear'"
            )
        if list_type == "byGenre" and not genre:
            raise ValueError("genre is required when list_type is 'byGenre'")

        params = {
            "type": list_type,
            "size": size,
            "offset": offset,
            "fromYear": from_year,
            "toYear": to_year,
            "genre": genre,
            "musicFolderId": music_folder_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._request("getAlbumList2", params)

    def get_album(self, album_id: str) -> dict:
        return self._request("getAlbum", {"id": album_id})

    def get_playlists(self, username: str | None = None) -> dict:
        params = {"username": username} if username else None
        return self._request("getPlaylists", params)

    def get_playlist(self, playlist_id: str) -> dict:
        return self._request("getPlaylist", {"id": playlist_id})

    def get_cover_art(self, cover_art_id: str, size: int | None = None) -> bytes:
        params = {"id": cover_art_id} | self._auth_params()
        if size is not None:
            params["size"] = size
        return self._download(f"{self.url}/rest/getCoverArt.view", params)
