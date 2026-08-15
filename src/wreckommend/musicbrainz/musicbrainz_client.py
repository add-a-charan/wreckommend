import time

import requests


class MusicBrainzClient:
    _MIN_INTERVAL = 1.0

    def __init__(self, url: str, contact_email: str):
        self.url = url
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": f"wreckommend/0.1 ({contact_email})"}
        )
        self._last_request_time = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    def _request(self, path: str, params: dict) -> dict:
        self._throttle()
        request_params = params | {"fmt": "json"}
        response = self.session.get(
            f"{self.url}{path}", params=request_params, timeout=10
        )
        response.raise_for_status()
        return response.json()

    def search_artist(self, name: str) -> dict:
        return self._request("artist/", {"query": f'artist:"{name}"', "limit": 5})

    def get_genres_page(self, offset: int, limit: int = 100) -> dict:
        return self._request("genre/all", {"limit": limit, "offset": offset})
