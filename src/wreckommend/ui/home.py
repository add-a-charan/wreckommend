from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from wreckommend.storage.db import get_connection


class Home(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Home", *args, **kwargs)
