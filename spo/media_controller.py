"""
Platform media-session controller for the Spotify desktop client.

Spotify's Web API refuses every player command for free accounts
(HTTP 403 PREMIUM_REQUIRED), so the deck drives the desktop client through the
operating system's media session instead:

    Windows -> Global System Media Transport Controls (SMTC)
    Linux   -> MPRIS (org.mpris.MediaPlayer2.spotify)
    macOS   -> not implemented (falls back to the Web API only)

Both give real playback state and transport control without Premium.
"""

import sys
import threading


class BaseMediaController:
    """No-op controller used when no native media session backend exists."""

    backend = "none"
    supports_seek = False
    supports_volume = False
    supports_shuffle = False
    supports_repeat = False

    def __init__(self):
        self._lock = threading.Lock()

    def state(self):
        return {"active": False, "backend": self.backend}

    def play(self):
        return False

    def pause(self):
        return False

    def next(self):
        return False

    def previous(self):
        return False

    def seek(self, position_ms):
        return False

    def set_volume(self, percent):
        return False

    def set_shuffle(self, enabled):
        return False

    def set_repeat(self, state):
        return False

    def open_uri(self, uri):
        """Ask the Spotify client to open a track/album/playlist URI."""
        return False, "Native playback control is not available on this system."

    def close(self):
        pass


def create_controller():
    if sys.platform == "win32":
        try:
            from windows_controller import WindowsMediaController
            return WindowsMediaController()
        except Exception as exc:  # pragma: no cover - Windows only  # noqa: BLE001
            print(f"[Media] Windows media controller unavailable: {exc}")
    elif sys.platform.startswith("linux"):
        try:
            from linux_controller import LinuxMediaController
            return LinuxMediaController()
        except Exception as exc:  # noqa: BLE001
            print(f"[Media] MPRIS controller unavailable: {exc}")
    return BaseMediaController()
