from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.css.query import NoMatches
from textual.widgets import Label, ListItem, ListView, ProgressBar, Static

from wreckommend.audio.player import Player
from wreckommend.clients import build_deezer_client, build_lastfm_client
from wreckommend.deezer.preview import download_preview, fetch_preview
from wreckommend.lastfm.candidates import discover_candidates
from wreckommend.scoring import score_candidates, top_candidates
from wreckommend.storage.db import get_connection

_STATUS_ICONS = {
    "loading": "⏳",
    "downloading": "⬇",
    "playing": "▶",
    "paused": "⏸",
}


class RecommendationItem(ListItem):
    def __init__(self, candidate: tuple, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.candidate = candidate
        self.status = "idle"

    @property
    def candidate_id(self) -> str:
        return self.candidate[0]

    def compose(self) -> ComposeResult:
        _id, title, artist_name, tag_score, discovered_via, source, preview_url = (
            self.candidate
        )
        yield Label(self._name_text(), classes="name")
        yield Label(f"{tag_score:.2f} · {discovered_via} · {source}", classes="meta")
        yield ProgressBar(show_eta=False, classes="preview-progress")

    def on_mount(self) -> None:
        self.query_one(ProgressBar).display = False

    def _name_text(self) -> str:
        _id, title, artist_name, *_ = self.candidate
        icon = _STATUS_ICONS.get(self.status)
        prefix = f"{icon} " if icon else ""
        return f"{prefix}{title} — {artist_name}"

    def set_status(self, status: str) -> None:
        self.status = status
        try:
            self.query_one(".name", Label).update(self._name_text())
            meta_label = self.query_one(".meta", Label)
            progress_bar = self.query_one(ProgressBar)
        except NoMatches:
            return

        downloading = status == "downloading"
        meta_label.display = not downloading
        progress_bar.display = downloading
        if downloading:
            progress_bar.update(total=None, progress=0)

    def update_progress(self, downloaded: int, total: int) -> None:
        try:
            progress_bar = self.query_one(ProgressBar)
        except NoMatches:
            return
        progress_bar.update(total=total or None, progress=downloaded)


class RecommendationsList(ListView):
    def __init__(self, candidates: list[tuple], *args, **kwargs) -> None:
        super().__init__(
            *[RecommendationItem(candidate) for candidate in candidates],
            *args,
            id="recommendations-list",
            **kwargs,
        )


class Recommendations(ScrollableContainer):
    _pipeline_has_run = False
    PAGE_SIZE = 25

    def __init__(self, parent: Static, *args, **kwargs) -> None:
        super().__init__(
            *args,
            **kwargs,
            id="recommendations-container",
            classes="module-container",
        )
        self.candidates: list[tuple] = []
        self._offset = 0
        self._loading_more = False
        self._exhausted = False
        self._player = Player()
        self._now_playing_item: RecommendationItem | None = None

    async def on_mount(self) -> None:
        if Recommendations._pipeline_has_run:
            await self._load_from_db()
        else:
            self.loading = True
            self.run_pipeline()

    def on_unmount(self) -> None:
        self._player.stop()

    async def _load_from_db(self) -> None:
        conn = get_connection()
        try:
            candidates = top_candidates(conn, limit=self.PAGE_SIZE)
        except Exception:
            candidates = []
        finally:
            conn.close()
        await self._apply_candidates(candidates)

    @work(thread=True, exclusive=True)
    def run_pipeline(self) -> None:
        conn = get_connection()
        try:
            try:
                discover_candidates(conn, build_lastfm_client())
            except Exception:
                pass
            try:
                score_candidates(conn)
            except Exception:
                pass
            try:
                candidates = top_candidates(conn, limit=self.PAGE_SIZE)
            except Exception:
                candidates = []
        finally:
            conn.close()

        Recommendations._pipeline_has_run = True
        self.app.call_from_thread(self._apply_candidates, candidates)

    async def _apply_candidates(self, candidates: list[tuple]) -> None:
        self.candidates = candidates
        self._offset = len(candidates)
        self._exhausted = len(candidates) < self.PAGE_SIZE
        try:
            await self.query_one("#recommendations-list").remove()
        except NoMatches:
            pass
        await self.mount(RecommendationsList(self.candidates))
        self.loading = False

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        list_view = event.list_view
        if list_view.id != "recommendations-list" or not list_view.children:
            return
        if list_view.index == len(list_view.children) - 1:
            self.load_more()

    @work(thread=True, exclusive=True, group="load-more")
    def load_more(self) -> None:
        if self._loading_more or self._exhausted:
            return
        self._loading_more = True

        conn = get_connection()
        try:
            try:
                new_candidates = top_candidates(
                    conn, limit=self.PAGE_SIZE, offset=self._offset
                )
            except Exception:
                new_candidates = []

            if not new_candidates:
                # Local pool is exhausted — go fetch more from Last.fm before
                # giving up on this scroll-to-bottom request.
                try:
                    discover_candidates(conn, build_lastfm_client())
                except Exception:
                    pass
                try:
                    score_candidates(conn)
                except Exception:
                    pass
                try:
                    new_candidates = top_candidates(
                        conn, limit=self.PAGE_SIZE, offset=self._offset
                    )
                except Exception:
                    new_candidates = []
        finally:
            conn.close()

        self.app.call_from_thread(self._append_candidates, new_candidates)

    async def _append_candidates(self, new_candidates: list[tuple]) -> None:
        self._loading_more = False
        if not new_candidates:
            self._exhausted = True
            return

        self._offset += len(new_candidates)
        if len(new_candidates) < self.PAGE_SIZE:
            self._exhausted = True

        self.candidates.extend(new_candidates)
        list_view = self.query_one("#recommendations-list", ListView)
        for candidate in new_candidates:
            await list_view.append(RecommendationItem(candidate))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "recommendations-list":
            return
        item = event.item
        if isinstance(item, RecommendationItem):
            self._toggle_playback(item)

    def _toggle_playback(self, item: RecommendationItem) -> None:
        if self._now_playing_item is item:
            if self._player.is_paused:
                self._player.resume()
                item.set_status("playing")
            else:
                self._player.pause()
                item.set_status("paused")
            return

        if self._now_playing_item is not None:
            self._player.stop()
            self._now_playing_item.set_status("idle")

        self._now_playing_item = item
        item.set_status("loading")
        self._play_candidate(item)

    @work(thread=True, exclusive=True, group="playback")
    def _play_candidate(self, item: RecommendationItem) -> None:
        candidate_id, title, artist_name, tag_score, discovered_via, source, _ = (
            item.candidate
        )
        conn = get_connection()
        error = None
        try:
            path = self._resolve_preview_path(conn, item, candidate_id, artist_name, title)
        except Exception as exc:
            path = None
            error = str(exc) or exc.__class__.__name__
        finally:
            conn.close()

        if path is None:
            self.app.call_from_thread(
                self._playback_failed, item, error or "No preview available"
            )
            return

        self._player.play(path)
        self.app.call_from_thread(self._playback_started, item)

    def _resolve_preview_path(
        self, conn, item: RecommendationItem, candidate_id: str, artist_name: str, title: str
    ) -> Path | None:
        row = conn.execute(
            "SELECT preview_path FROM candidate_tracks WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        preview_path = row[0] if row else None

        if preview_path and Path(preview_path).exists():
            return Path(preview_path)

        # Deezer preview URLs are signed and expire ~15 minutes after being
        # issued, so any cached preview_url may be stale by the time the user
        # clicks play. Always fetch a live one right before downloading.
        client = build_deezer_client()
        preview_url = fetch_preview(
            conn, client, candidate_id, artist_name, title, force=True
        )
        if not preview_url:
            return None

        self.app.call_from_thread(self._set_item_status_if_current, item, "downloading")

        def on_progress(downloaded: int, total: int) -> None:
            self.app.call_from_thread(
                self._update_item_progress_if_current, item, downloaded, total
            )

        return download_preview(
            conn, client, candidate_id, preview_url, on_progress=on_progress
        )

    def _set_item_status_if_current(self, item: RecommendationItem, status: str) -> None:
        if self._now_playing_item is item:
            item.set_status(status)

    def _update_item_progress_if_current(
        self, item: RecommendationItem, downloaded: int, total: int
    ) -> None:
        if self._now_playing_item is item:
            item.update_progress(downloaded, total)

    def _playback_started(self, item: RecommendationItem) -> None:
        if self._now_playing_item is item:
            item.set_status("playing")

    def _playback_failed(self, item: RecommendationItem, error: str | None = None) -> None:
        if self._now_playing_item is item:
            self._now_playing_item = None
        item.set_status("idle")
        if error:
            self.app.notify(error, title="Playback failed", severity="error")

    def compose(self) -> ComposeResult:
        yield RecommendationsList(self.candidates)
