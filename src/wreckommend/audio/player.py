import signal
import subprocess
from pathlib import Path


class Player:
    """Plays one local audio file at a time via the system `mpv` binary.

    Pause/resume works by suspending the player process with SIGSTOP/SIGCONT
    rather than killing it, so resuming continues from the same position.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    def play(self, path: Path) -> None:
        self.stop()
        self._process = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._paused = False

    def pause(self) -> None:
        if self._process is None or self._paused or self._process.poll() is not None:
            return
        try:
            self._process.send_signal(signal.SIGSTOP)
        except ProcessLookupError:
            return
        self._paused = True

    def resume(self) -> None:
        if self._process is None or not self._paused:
            return
        try:
            self._process.send_signal(signal.SIGCONT)
        except ProcessLookupError:
            pass
        self._paused = False

    def stop(self) -> None:
        if self._process is not None:
            try:
                self._process.kill()
                self._process.wait()
            except ProcessLookupError:
                pass
        self._process = None
        self._paused = False
