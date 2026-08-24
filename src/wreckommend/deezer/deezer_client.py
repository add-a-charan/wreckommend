from collections.abc import Callable

from wreckommend.core.http_client import ApiClient


class DeezerClient(ApiClient):
    def __init__(self, url: str, contact_email: str):
        super().__init__(url, contact_email, min_interval=0.1)

    def search_track(self, artist: str, title: str, limit: int = 5) -> dict:
        query = f'artist:"{artist}" track:"{title}"'
        data = self._get(f"{self.url}search", {"q": query, "limit": limit})
        if isinstance(data, dict) and "error" in data:
            error = data["error"]
            self._raise_error(
                "Deezer", error.get("code"), error.get("message", "unknown error")
            )
        return data

    def download_preview(
        self, url: str, on_progress: Callable[[int, int], None] | None = None
    ) -> bytes:
        return self._download(url, on_progress=on_progress)
