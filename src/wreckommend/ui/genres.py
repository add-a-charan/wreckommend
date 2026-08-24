from textual.widgets import Static


class Genres(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Genres", *args, **kwargs)
