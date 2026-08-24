import time
from collections.abc import Callable

import requests


class ApiClient:
    def __init__(
        self, url: str, contact_email: str | None = None, min_interval: float = 0.0
    ):
        self.url = url
        self.session = requests.Session()
        if contact_email:
            self.session.headers.update(
                {"User-Agent": f"wreckommend/0.1 ({contact_email})"}
            )
        self._min_interval = min_interval
        self._last_request_time = 0.0

    def _throttle(self):
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def _get(self, url: str, params: dict) -> dict:
        self._throttle()
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def _download(
        self,
        url: str,
        params: dict | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> bytes:
        self._throttle()
        response = self.session.get(url, params=params, timeout=15, stream=True)
        response.raise_for_status()

        if on_progress is None:
            return response.content

        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunks = []
        for chunk in response.iter_content(chunk_size=8192):
            chunks.append(chunk)
            downloaded += len(chunk)
            on_progress(downloaded, total)
        return b"".join(chunks)

    def _raise_error(self, service: str, code, message: str) -> None:
        raise RuntimeError(f"{service} error {code}: {message}")
