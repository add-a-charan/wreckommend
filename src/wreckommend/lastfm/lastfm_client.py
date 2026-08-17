import time

from wreckommend.core.http_client import ApiClient


class LastfmClient(ApiClient):
    def __init__(self, url: str, api_key: str, contact_email: str):
        super().__init__(url, contact_email, min_interval=0.2)
        self.api_key = api_key

    def _request(
        self, method: str, params: dict | None = None, retry: bool = True
    ) -> dict:
        request_params = (params or {}) | {
            "method": method,
            "api_key": self.api_key,
            "format": "json",
        }
        data = self._get(self.url, request_params)
        if "error" in data:
            code = data["error"]
            message = data.get("message", "unknown error")
            if code == 29 and retry:
                time.sleep(1.0)
                return self._request(method, params, retry=False)
            self._raise_error("Last.fm", code, f"{message} (method: {method})")
        return data

    def get_track_top_tags(self, artist: str, track: str) -> dict:
        return self._request("track.getTopTags", {"artist": artist, "track": track})

    def get_artist_top_tags(self, artist: str) -> dict:
        return self._request("artist.getTopTags", {"artist": artist})

    def get_similar_artists(self, artist: str, limit: int = 15) -> dict:
        return self._request("artist.getSimilar", {"artist": artist, "limit": limit})

    def get_artist_top_tracks(self, artist: str, limit: int = 10) -> dict:
        return self._request("artist.getTopTracks", {"artist": artist, "limit": limit})

    def get_similar_tracks(self, artist: str, track: str, limit: int = 15) -> dict:
        return self._request(
            "track.getSimilar", {"artist": artist, "track": track, "limit": limit}
        )
