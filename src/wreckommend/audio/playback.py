from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from textual import work

from wreckommend.audio.player import Player

STATUS_ICONS = {
    "loading": "⏳",
    "downloading": "⬇",
    "playing": "▶",
    "paused": "⏸",
}


class Playable(Protocol):
    status: str

    def set_status(self, status: str) -> None: ...


# A resolver gets (report_status, report_progress) — both safe to call from
# a background thread — and returns a local Path to play, downloading/
# caching whatever it needs to along the way. Callers that don't need
# intermediate status/progress reporting (e.g. an already-local file) can
# just ignore the callbacks.
ResolvePath = Callable[[Callable[[str], None], Callable[[int, int], None]], Path]


class PlaybackMixin:
    """Single-track-at-a-time play/pause/stop state machine, shared by any
    Widget/Screen that lists playable items and needs to resolve (and maybe
    download/cache) a local file before handing it to `audio.player.Player`.

    Mix in alongside a real Textual Widget/Screen base — relies on
    `self.app`/`self.run_worker` from that base, e.g.:

        class SomeList(ScrollableContainer, PlaybackMixin):
            def __init__(self, ...):
                super().__init__(...)
                self.init_playback()

            def on_unmount(self):
                self.stop_playback()

            def on_list_view_selected(self, event):
                item = event.item
                self.toggle_playback(item, self._resolve_path_for(item))
    """

    def init_playback(self) -> None:
        self._player = Player()
        self._now_playing_item: Playable | None = None

    def stop_playback(self) -> None:
        self._player.stop()

    def toggle_playback(self, item: Playable, resolve_path: ResolvePath) -> None:
        if self._now_playing_item is item:
            if self._player.is_paused:
                self._player.resume()
                item.set_status("playing")
            else:
                self._player.pause()
                item.set_status("paused")
            return

        if self._now_playing_item is not None:
            self._now_playing_item.set_status("idle")

        self._now_playing_item = item
        item.set_status("loading")
        self._play(item, resolve_path)

    @work(thread=True, exclusive=True, group="playback")
    def _play(self, item: Playable, resolve_path: ResolvePath) -> None:
        def report_status(status: str) -> None:
            self.app.call_from_thread(self._set_status_if_current, item, status)

        def report_progress(downloaded: int, total: int) -> None:
            self.app.call_from_thread(
                self._update_progress_if_current, item, downloaded, total
            )

        try:
            path = resolve_path(report_status, report_progress)
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            self.app.call_from_thread(self._playback_failed, item, error)
            return

        self._player.play(path)
        self.app.call_from_thread(self._playback_started, item)

    def _set_status_if_current(self, item: Playable, status: str) -> None:
        if self._now_playing_item is item:
            item.set_status(status)

    def _update_progress_if_current(
        self, item: Playable, downloaded: int, total: int
    ) -> None:
        if self._now_playing_item is item:
            update = getattr(item, "update_progress", None)
            if update is not None:
                update(downloaded, total)

    def _playback_started(self, item: Playable) -> None:
        if self._now_playing_item is item:
            item.set_status("playing")

    def _playback_failed(self, item: Playable, error: str) -> None:
        if self._now_playing_item is item:
            self._now_playing_item = None
        item.set_status("idle")
        self.app.notify(error, title="Playback failed", severity="error")
