import requests
import secrets
import hashlib


class SubsonicClient:
    def __init__(
        self, base_url: str, user: str, password: str, version: str, client_name: str
    ):
        self.base_url = base_url
        self.user = user
        self.password = password
        self.version = version
        self.client_name = client_name
        self.session = requests.Session()

    # Helper Method For All API Methods
    def _request(self, method: str, params: dict | None = None) -> dict:
        if params is None:
            params = {}
        salt = secrets.token_hex(16)
        token = hashlib.md5((self.password + salt).encode("utf-8")).hexdigest()
        request_params = {
            "u": self.user,
            "t": token,
            "s": salt,
            "v": self.version,
            "c": self.client_name,
            "f": "json",
        }
        merged_params = params | request_params

        response = self.session.get(
            f"{self.base_url}/rest/{method}.view", params=merged_params, timeout=10
        )
        response.raise_for_status()
        data = response.json()["subsonic-response"]
        if data["status"] != "ok":
            error = data.get("error", {})
            raise RuntimeError(
                f"Subsonic error {error.get('code')}: {error.get('message')}"
            )

        return data

    # System
    def ping(self) -> dict:
        return self._request("ping")

    # Album/song lists
    def getAlbumList2(
        self,
        type: str,
        size: str = "10",
        offset: str = "0",
        fromYear: str = "",
        toYear: str = "",
        genre: str = "",
        musicFolderId: str = "",
    ) -> dict:
        params = {
            "type": type,
            "size": size,
            "offset": offset,
            "fromYear": fromYear,
            "toYear": toYear,
            "genre": genre,
            "musicFolderId": musicFolderId,
        }
        params = {k: v for k, v in params.items() if v}
        return self._request("getAlbumList2", params)

    def getAlbum(self, id: str) -> dict:
        return self._request("getAlbum", {"id": id})
