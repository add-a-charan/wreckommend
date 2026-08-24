from textual.widgets import Static


class Albums(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Albums", *args, **kwargs)
