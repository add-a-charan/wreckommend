import time

import requests


class LastfmClient:
    def __init__(self, url: str, api_key: str, contact_email: str):
        self.url = url
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": f"wreckommend/0.1 ({contact_email})"}
        )
        self._last_request_time = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        self._last_request_time = time.monotonic()

    def _request(
        self, method: str, params: dict | None = None, retry: bool = True
    ) -> dict:
        self._throttle()
        request_params = (params or {}) | {
            "method": method,
            "api_key": self.api_key,
            "format": "json",
        }
        response = self.session.get(self.url, params=request_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            code = data["error"]
            message = data.get("message", "unknown error")
            if code == 29 and retry:
                time.sleep(1.0)
                return self._request(method, params, retry=False)
            raise RuntimeError(f"Last.fm error {code} on {method}: {message}")
        return data

    def get_track_top_tags(self, artist: str, track: str) -> dict:
        return self._request("track.getTopTags", {"artist": artist, "track": track})

    def get_artist_top_tags(self, artist: str) -> dict:
        return self._request("artist.getTopTags", {"artist": artist})
