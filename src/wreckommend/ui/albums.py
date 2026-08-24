from io import BytesIO

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.widgets import Label, ListItem, ListView
from textual_image.widget import Image

from wreckommend.clients import build_subsonic_client
from wreckommend.subsonic.ingest import retrieve_all_albums
from wreckommend.ui.album_detail import AlbumDetailScreen
from wreckommend.ui.components.badges import heart_label_kwargs, rating_stars
from wreckommend.ui.components.modules.playlists import _cover_crop

# Taller than the playlist cover (10x5) since each row also carries year and
# rating/favorite badges beneath the name/artist line.
ALBUM_COVER_CELLS = (12, 6)
# How many AlbumItems (with cover art) are mounted per batch. Album
# *metadata* for the whole library is fetched eagerly up front (cheap, no
# cover art) so the true first/last album is always known for wrap-around;
# this only controls how much gets rendered/cover-fetched at a time.
BATCH_SIZE = 40


class AlbumItem(ListItem):
    def __init__(self, album: dict, cover_art: bytes | None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.album = album
        self.cover_art = cover_art

    def _meta_text(self) -> str:
        artist = self.album.get("artist") or "Unknown Artist"
        year = self.album.get("year")
        return f"{artist} · {year}" if year else artist

    def compose(self) -> ComposeResult:
        with Horizontal(classes="album-row"):
            if self.cover_art:
                yield Image(BytesIO(self.cover_art), classes="cover-art")
            with Vertical(classes="album-info"):
                yield Label(self.album.get("name") or "Untitled", classes="name")
                yield Label(self._meta_text(), classes="meta")
                with Horizontal(classes="album-badges"):
                    stars = rating_stars(self.album.get("userRating"))
                    if stars:
                        yield Label(stars, classes="rating")
                    glyph, heart_classes = heart_label_kwargs(self.album.get("starred"))
                    yield Label(glyph, classes=heart_classes)


class AlbumsList(ListView):
    def __init__(
        self,
        owner: "Albums",
        albums: list[dict],
        covers: dict[str, bytes],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            *[AlbumItem(album, covers.get(album.get("id"))) for album in albums],
            *args,
            id="albums-list",
            **kwargs,
        )
        self._owner = owner

    def on_mount(self) -> None:
        # ListView's `initial_index=0` only decides which row *looks*
        # highlighted; without an explicit focus() call, arrow keys go
        # nowhere until the user clicks into the list first.
        self.focus()

    def action_cursor_up(self) -> None:
        """Same as ListView's default, but wraps from the first album to the
        true last album in the library (mounting it first if needed)."""
        if self.index == 0 and self.children:
            self._owner.wrap_to_end()
        else:
            super().action_cursor_up()

    def action_cursor_down(self) -> None:
        """Same as ListView's default, but wraps from the last album back to
        the first once the whole library has been mounted."""
        if (
            self.children
            and self.index == len(self.children) - 1
            and self._owner.is_fully_loaded
        ):
            self.index = 0
        else:
            super().action_cursor_down()


class Albums(ScrollableContainer):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, id="albums")
        self._client = build_subsonic_client()
        self.albums: list[dict] = []
        self._covers: dict[str, bytes] = {}
        self._mounted_count = 0
        self._loading_more = False

    @property
    def is_fully_loaded(self) -> bool:
        return bool(self.albums) and self._mounted_count >= len(self.albums)

    async def on_mount(self) -> None:
        self.loading = True
        self.load_albums()

    def _fetch_cover(self, album: dict) -> bytes | None:
        cover_art_id = album.get("coverArt") or album.get("id")
        if not cover_art_id:
            return None
        try:
            raw = self._client.get_cover_art(cover_art_id, size=300)
            return _cover_crop(raw, *ALBUM_COVER_CELLS)
        except Exception:
            return None

    def _fetch_covers(self, albums: list[dict]) -> dict[str, bytes]:
        return {
            album["id"]: cover
            for album in albums
            if (cover := self._fetch_cover(album)) is not None
        }

    @work(thread=True, exclusive=True)
    def load_albums(self) -> None:
        try:
            albums = retrieve_all_albums(self._client)
        except Exception:
            albums = []
        first_batch = albums[:BATCH_SIZE]
        covers = self._fetch_covers(first_batch)
        self.app.call_from_thread(self._apply_albums, albums, covers)

    async def _apply_albums(self, albums: list[dict], covers: dict[str, bytes]) -> None:
        self.albums = albums
        self._covers.update(covers)
        self._mounted_count = min(BATCH_SIZE, len(albums))
        try:
            await self.query_one("#albums-list").remove()
        except NoMatches:
            pass
        await self.mount(AlbumsList(self, self.albums[: self._mounted_count], self._covers))
        self.loading = False

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        list_view = event.list_view
        if list_view.id != "albums-list" or not list_view.children:
            return
        if list_view.index == len(list_view.children) - 1:
            self.load_more()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "albums-list":
            return
        item = event.item
        if isinstance(item, AlbumItem):
            self.app.push_screen(AlbumDetailScreen(item.album))

    @work(thread=True, exclusive=True, group="load-more")
    def load_more(self) -> None:
        if self._loading_more or self._mounted_count >= len(self.albums):
            return
        self._loading_more = True

        start = self._mounted_count
        batch = self.albums[start : start + BATCH_SIZE]
        covers = self._fetch_covers(batch)
        self.app.call_from_thread(self._append_albums, batch, covers)

    async def _append_albums(
        self, batch: list[dict], covers: dict[str, bytes]
    ) -> None:
        self._loading_more = False
        if not batch:
            return

        self._covers.update(covers)
        self._mounted_count += len(batch)
        list_view = self.query_one("#albums-list", ListView)
        for album in batch:
            await list_view.append(AlbumItem(album, self._covers.get(album.get("id"))))

    def wrap_to_end(self) -> None:
        """Jump the cursor to the true last album, mounting whatever hasn't
        been mounted yet first."""
        list_view = self.query_one("#albums-list", ListView)
        if self.is_fully_loaded:
            list_view.index = len(list_view.children) - 1
            return
        self._load_remaining_and_jump()

    @work(thread=True, exclusive=True, group="load-more")
    def _load_remaining_and_jump(self) -> None:
        if self._loading_more:
            return
        self._loading_more = True

        start = self._mounted_count
        remaining = self.albums[start:]
        covers = self._fetch_covers(remaining)
        self.app.call_from_thread(self._append_and_jump, remaining, covers)

    async def _append_and_jump(
        self, remaining: list[dict], covers: dict[str, bytes]
    ) -> None:
        self._loading_more = False
        self._covers.update(covers)
        self._mounted_count += len(remaining)
        list_view = self.query_one("#albums-list", ListView)
        for album in remaining:
            await list_view.append(AlbumItem(album, self._covers.get(album.get("id"))))
        if list_view.children:
            list_view.index = len(list_view.children) - 1

    def compose(self) -> ComposeResult:
        yield AlbumsList(self, self.albums[: self._mounted_count], self._covers)
