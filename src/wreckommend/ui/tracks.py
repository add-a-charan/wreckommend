from textual.widgets import Static


class Tracks(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Tracks", *args, **kwargs)
