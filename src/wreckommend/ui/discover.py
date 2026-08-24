from textual.widgets import Static
from textual.app import ComposeResult

from wreckommend.ui.components.modules.playlists import Playlists
from wreckommend.ui.components.modules.recommendations import Recommendations


class Discover(Static):
    # More BINDINGS?

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, id="discover")
        self.playlist_module = Playlists(parent=self)
        self.recommendations_module = Recommendations(parent=self)

    def compose(self) -> ComposeResult:
        with Static(classes="discover-modules-container"):
            with Static(classes="left"):
                yield self.playlist_module
            with Static(classes="right"):
                yield self.recommendations_module
