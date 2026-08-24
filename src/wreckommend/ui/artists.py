from textual.widgets import Static


class Artists(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Artists", *args, **kwargs)
