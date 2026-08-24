from io import BytesIO

from PIL import Image as PILImage
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.widgets import Label, ListItem, ListView, Static
from textual_image._terminal import get_cell_size
from textual_image.widget import Image

from wreckommend.clients import build_subsonic_client

# Must match the `.cover-art` width/height (in terminal cells) set in
# styles/discover_modules.tcss, so the pre-cropped image's aspect ratio
# exactly matches the box it's rendered into.
COVER_ART_CELLS = (10, 5)


def _cover_crop(image_bytes: bytes, cell_width: int, cell_height: int) -> bytes:
    """Scale up/down (preserving aspect ratio, never stretching) and
    center-crop image bytes to exactly fill a box of `cell_width` x
    `cell_height` terminal cells."""
    cell = get_cell_size()
    target_w = max(1, cell_width * cell.width)
    target_h = max(1, cell_height * cell.height)

    with PILImage.open(BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        scale = max(target_w / img.width, target_h / img.height)
        scaled_size = (round(img.width * scale), round(img.height * scale))
        img = img.resize(scaled_size, PILImage.Resampling.LANCZOS)

        left = (img.width - target_w) // 2
        top = (img.height - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


class PlaylistItem(ListItem):
    def __init__(
        self, playlist: dict, cover_art: bytes | None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.playlist = playlist
        self.cover_art = cover_art

    def compose(self) -> ComposeResult:
        with Horizontal(classes="playlist-row"):
            if self.cover_art:
                yield Image(BytesIO(self.cover_art), classes="cover-art")
            with Vertical(classes="playlist-info"):
                yield Label(self.playlist.get("name", "Untitled"), classes="name")
                yield Label(
                    f"{self.playlist.get('songCount', 0)} tracks", classes="meta"
                )


class PlaylistsList(ListView):
    def __init__(
        self,
        playlists: list[dict],
        covers: dict[str, bytes],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            *[
                PlaylistItem(playlist, covers.get(playlist.get("id")))
                for playlist in playlists
            ],
            *args,
            id="playlists-list",
            **kwargs,
        )


class Playlists(ScrollableContainer):
    def __init__(self, parent: Static, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="playlists-container", classes="module-container"
        )
        self._client = build_subsonic_client()
        self.playlists: list[dict] = []
        self._covers: dict[str, bytes] = {}

    async def on_mount(self) -> None:
        await self.rebuild()

    def _fetch_cover(self, playlist: dict) -> bytes | None:
        cover_art_id = playlist.get("coverArt") or playlist.get("id")
        if not cover_art_id:
            return None
        try:
            raw = self._client.get_cover_art(cover_art_id, size=300)
            return _cover_crop(raw, *COVER_ART_CELLS)
        except Exception:
            return None

    async def rebuild(self) -> None:
        try:
            response = self._client.get_playlists()
            self.playlists = response.get("playlists", {}).get("playlist", []) or []
        except Exception:
            self.playlists = []

        for playlist in self.playlists:
            playlist_id = playlist.get("id")
            if playlist_id and playlist_id not in self._covers:
                cover = self._fetch_cover(playlist)
                if cover is not None:
                    self._covers[playlist_id] = cover

        try:
            await self.query_one("#playlists-list").remove()
        except NoMatches:
            pass
        await self.mount(PlaylistsList(self.playlists, self._covers))

    def compose(self) -> ComposeResult:
        yield PlaylistsList(self.playlists, self._covers)
