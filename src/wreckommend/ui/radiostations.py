from textual.widgets import Static


class RadioStations(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Radio Stations", *args, **kwargs)
