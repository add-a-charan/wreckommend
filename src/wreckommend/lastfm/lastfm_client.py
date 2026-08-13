import requests
import time


class LastfmClient:
    def __init__(self, base_url: str, api_key: str, contact_email: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.base_url = base_url
        self.session.headers.update(
            {"User-Agent": f"wreckommend/0.1 ({contact_email})"}
        )
        self._last_request_time = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        self._last_request_time = time.monotonic()

    # Helper Method For All API Methods
    def _request(self, method: str, params: dict, retry: bool = True) -> dict:
        self._throttle()
        merged = params | {"method": method, "api_key": self.api_key, "format": "json"}
        response = self.session.get(self.base_url, params=merged, timeout=10)
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
