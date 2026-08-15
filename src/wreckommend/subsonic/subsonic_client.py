import hashlib
import secrets

import requests


class SubsonicClient:
    def __init__(
        self, url: str, user: str, password: str, version: str, client_name: str
    ):
        self.url = url
        self.user = user
        self.password = password
        self.version = version
        self.client_name = client_name
        self.session = requests.Session()

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
        response = self.session.get(
            f"{self.url}/rest/{method}.view", params=request_params, timeout=10
        )
        response.raise_for_status()
        data = response.json()["subsonic-response"]
        if data["status"] != "ok":
            error = data.get("error", {})
            raise RuntimeError(
                f"Subsonic error {error.get('code')}: {error.get('message')}"
            )
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

    def get_album(self, id: str) -> dict:
        return self._request("getAlbum", {"id": id})
