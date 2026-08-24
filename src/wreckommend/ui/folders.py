from textual.widgets import Static


class Folders(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Folders", *args, **kwargs)
