from wreckommend.core.http_client import ApiClient


class MusicBrainzClient(ApiClient):
    def __init__(self, url: str, contact_email: str):
        super().__init__(url, contact_email, min_interval=1.0)

    def _request(self, path: str, params: dict) -> dict:
        request_params = params | {"fmt": "json"}
        return self._get(f"{self.url}{path}", request_params)

    def search_artist(self, name: str) -> dict:
        return self._request("artist/", {"query": f'artist:"{name}"', "limit": 5})

    def get_genres_page(self, offset: int, limit: int = 100) -> dict:
        return self._request("genre/all", {"limit": limit, "offset": offset})
