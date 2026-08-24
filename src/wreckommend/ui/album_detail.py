from io import BytesIO

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer, Label, ListItem, ListView
from textual_image.widget import Image

from wreckommend.audio.playback import STATUS_ICONS, PlaybackMixin
from wreckommend.clients import build_subsonic_client
from wreckommend.subsonic.ingest import retrieve_album_tracks
from wreckommend.subsonic.stream import resolve_track_path
from wreckommend.ui.components.badges import heart_label_kwargs, rating_stars
from wreckommend.ui.components.modules.playlists import _cover_crop

# Bigger than the album-list row cover (12x6) since this is the page's hero
# image rather than a small thumbnail next to a list row.
HERO_COVER_CELLS = (24, 12)


def _format_duration(seconds: int | None) -> str:
    if not seconds:
        return "0:00"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_size(num_bytes: int | None) -> str:
    if not num_bytes:
        return "0 B"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


class TrackItem(ListItem):
    def __init__(self, track: dict, position: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.track = track
        self.position = position
        self.status = "idle"

    def compose(self) -> ComposeResult:
        track_number = self.track.get("track") or self.position
        with Horizontal(classes="track-row"):
            yield Label(f"{track_number:>2}", classes="track-number")
            yield Label(self._title_text(), classes="track-title")
            yield Label(rating_stars(self.track.get("userRating")), classes="rating")
            glyph, heart_classes = heart_label_kwargs(self.track.get("starred"))
            yield Label(glyph, classes=heart_classes)
            yield Label(
                _format_duration(self.track.get("duration")), classes="track-duration"
            )

    def _title_text(self) -> str:
        icon = STATUS_ICONS.get(self.status)
        prefix = f"{icon} " if icon else ""
        return f"{prefix}{self.track.get('title') or 'Untitled'}"

    def set_status(self, status: str) -> None:
        self.status = status
        try:
            self.query_one(".track-title", Label).update(self._title_text())
        except NoMatches:
            pass


class TracksList(ListView):
    def __init__(self, tracks: list[dict], *args, **kwargs) -> None:
        super().__init__(
            *[
                TrackItem(track, position)
                for position, track in enumerate(tracks, start=1)
            ],
            *args,
            id="album-tracks-list",
            **kwargs,
        )

    def on_mount(self) -> None:
        # ListView's `initial_index=0` only decides which row *looks*
        # highlighted; without an explicit focus() call, arrow keys go
        # nowhere until the user clicks into the list first.
        self.focus()


class AlbumDetailScreen(Screen, PlaybackMixin):
    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, album: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, id="album-detail")
        self.album = album
        self._client = build_subsonic_client()
        self.tracks: list[dict] = []
        self.init_playback()

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_mount(self) -> None:
        self.loading = True
        self.load_details()

    def on_unmount(self) -> None:
        self.stop_playback()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "album-tracks-list":
            return
        item = event.item
        if isinstance(item, TrackItem):
            self.toggle_playback(
                item, lambda _status, _progress: resolve_track_path(self._client, item.track)
            )

    def _info_line(self, total_size: int | None = None) -> str:
        parts = []
        year = self.album.get("year")
        if year:
            parts.append(str(year))
        song_count = self.album.get("songCount")
        if song_count:
            parts.append(f"{song_count} tracks")
        duration = self.album.get("duration")
        if duration:
            parts.append(_format_duration(duration))
        if total_size:
            parts.append(_format_size(total_size))
        play_count = self.album.get("playCount") or 0
        parts.append(f"{play_count} plays")
        return " · ".join(parts)

    @work(thread=True, exclusive=True)
    def load_details(self) -> None:
        try:
            tracks = retrieve_album_tracks(self._client, self.album)
        except Exception:
            tracks = []
        total_size = sum(track.get("size") or 0 for track in tracks)

        cover_art = None
        cover_art_id = self.album.get("coverArt") or self.album.get("id")
        if cover_art_id:
            try:
                raw = self._client.get_cover_art(cover_art_id, size=600)
                cover_art = _cover_crop(raw, *HERO_COVER_CELLS)
            except Exception:
                cover_art = None

        self.app.call_from_thread(self._apply_details, tracks, total_size, cover_art)

    async def _apply_details(
        self, tracks: list[dict], total_size: int, cover_art: bytes | None
    ) -> None:
        self.tracks = tracks

        if cover_art:
            try:
                await self.query_one(".album-header").mount(
                    Image(BytesIO(cover_art), classes="hero-cover-art"), before=0
                )
            except NoMatches:
                pass

        self.query_one(".album-info", Label).update(self._info_line(total_size))

        try:
            await self.query_one("#album-tracks-list").remove()
        except NoMatches:
            pass
        await self.query_one("#album-detail-body").mount(
            TracksList(self.tracks, classes="module-container")
        )
        self.loading = False

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="album-detail-body", classes="content"):
            with Horizontal(classes="album-header"):
                with Vertical(classes="album-meta"):
                    yield Label(self.album.get("name") or "Untitled", classes="album-title")
                    yield Label(
                        self.album.get("artist") or "Unknown Artist",
                        classes="album-artist",
                    )
                    yield Label(self._info_line(), classes="album-info")
        yield Footer()
