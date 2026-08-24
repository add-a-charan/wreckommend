from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.geometry import Size
from textual.theme import Theme
from textual.widgets import Footer, Label, Tab, Tabs

from wreckommend.ui.home import Home
from wreckommend.ui.discover import Discover
from wreckommend.ui.albums import Albums
from wreckommend.ui.tracks import Tracks
from wreckommend.ui.artists import Artists
from wreckommend.ui.genres import Genres
from wreckommend.ui.folders import Folders
from wreckommend.ui.radiostations import RadioStations

CATPPUCCIN_MOCHA_THEME = Theme(
    name="catppuccin-mocha",
    primary="#f5c2e7",
    secondary="#cba6f7",
    warning="#fae3b0",
    error="#f28fad",
    success="#abe9b3",
    accent="#fab387",
    foreground="#cdd6f4",
    background="#1e1e2e",  # catppuccin mocha "base"
    surface="#313244",
    panel="#45475a",
    dark=True,
    variables={
        "input-cursor-foreground": "#11111b",
        "input-cursor-background": "#f5e0dc",
        "input-selection-background": "#9399b2 30%",
        "border": "#b4befe",
        "border-blurred": "#585b70",
        "footer-background": "#45475a",
        "block-cursor-foreground": "#1e1e2e",
        "block-cursor-background": "#cba6f7",  # mauve, drives active tab styling
        "block-cursor-text-style": "none",
        "button-color-foreground": "#181825",
    },
)

PAGES = [
    {"name": "Home", "class": Home},
    {"name": "Discover", "class": Discover},
    {"name": "Albums", "class": Albums},
    {"name": "Tracks", "class": Tracks},
    {"name": "Artists", "class": Artists},
    {"name": "Genres", "class": Genres},
    {"name": "Folders", "class": Folders},
    {"name": "Radio Stations", "class": RadioStations},
]


class WreckommendApp(App):
    """A music player with elite recommendations."""

    CSS_PATH = [
        "./styles/index.tcss",
        "./styles/modals.tcss",
        "./styles/home.tcss",
        "./styles/home_modules.tcss",
        "./styles/discover.tcss",
        "./styles/discover_modules.tcss",
    ]

    BINDINGS = [
        ("ctrl+l", "cycle_tabs", "Next tab"),
        ("ctrl+h", "cycle_tabs(-1)", "Previous tab"),
        ("ctrl+q", "quit", "Quit"),
    ]

    TITLE = "wreckommend"
    current_tab = 0
    layout = "h"

    def _tab_id(self, name: str) -> str:
        return f"tab-{name.lower().replace(' ', '-')}"

    def on_mount(self) -> None:
        self.register_theme(CATPPUCCIN_MOCHA_THEME)
        self.theme = "catppuccin-mocha"

    def compose(self) -> ComposeResult:
        with Container(classes="header"):
            yield Label(self.TITLE, classes="title")
            tabs = Tabs(
                *[Tab(page["name"], id=self._tab_id(page["name"])) for page in PAGES],
                classes="root-tabs",
            )
            tabs.can_focus = False
            yield tabs
        yield Footer()

    async def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Swap the mounted page when a tab becomes active."""
        page = next(
            page for page in PAGES if self._tab_id(page["name"]) == event.tab.id
        )
        self.current_tab = PAGES.index(page)

        try:
            self.query_one(".content").remove()
        except NoMatches:
            pass

        await self.mount(page["class"](classes=f"content {self.layout}"))

    def action_cycle_tabs(self, direction: int = 1) -> None:
        """Cycle to the next (or previous) tab."""
        self.current_tab = (self.current_tab + direction) % len(PAGES)
        tabs = self.query_one(Tabs)
        tabs.active = self._tab_id(PAGES[self.current_tab]["name"])

    def on_resize(self, event: events.Resize) -> None:
        size: Size = event.size
        aspect_ratio = (size.width / 2) / size.height
        self.layout = "v" if aspect_ratio < 1 else "h"
        try:
            self.query_one(".content").set_classes(f"content {self.layout}")
        except NoMatches:
            pass


if __name__ == "__main__":
    app = WreckommendApp()
    app.run()
