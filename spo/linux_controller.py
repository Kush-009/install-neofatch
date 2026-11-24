"""
Linux media controller for the Spotify desktop client (and any MPRIS player).

Chats through the session D-Bus to read the MPRIS media player state and send
real transport commands. Works with free Spotify accounts because it never
touches the Premium-only Web API player endpoints.
"""

import shutil
import subprocess

from media_controller import BaseMediaController

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"


class LinuxMediaController(BaseMediaController):
    backend = "mpris"
    supports_seek = True
    supports_volume = True
    supports_shuffle = True
    supports_repeat = True

    def __init__(self):
        super().__init__()
        self._available = False
        try:
            from gi.repository import Gio, GLib
            self._Gio = Gio
            self._GLib = GLib
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self._available = self._bus is not None
        except Exception:  # noqa: BLE001
            self._bus = None
        self._volume = 70

    # ----- discovery -------------------------------------------------------
    def _players(self):
        reply = self._call(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "ListNames", None, "(as)",
        )
        if not reply:
            return []
        names = [name for name in reply[0] if name.startswith(MPRIS_PREFIX)]
        names.sort(key=lambda name: (0 if "spotify" in name.lower() else 1, name))
        return names

    def _player(self):
        for name in self._players():
            props = self._properties(name)
            if props:
                return name
        return None

    # ----- dbus helpers ----------------------------------------------------
    def _call(self, bus_name, path, iface, method, params=None, reply_signature=None, timeout=1500):
        if not self._available:
            return None
        try:
            reply_type = self._GLib.VariantType(reply_signature) if reply_signature else None
            return self._bus.call_sync(
                bus_name, path, iface, method, params, reply_type,
                self._Gio.DBusCallFlags.NONE, timeout, None,
            ).unpack()
        except Exception:  # noqa: BLE001
            return None

    def _properties(self, player):
        reply = self._call(player, MPRIS_PATH, PROPS_IFACE, "GetAll",
                           self._GLib.Variant("(s)", (PLAYER_IFACE,)), "(a{sv})")
        if not reply or not isinstance(reply[0], dict):
            return None
        return reply[0]

    def _property(self, player, name):
        reply = self._call(player, MPRIS_PATH, PROPS_IFACE, "Get",
                           self._GLib.Variant("(ss)", (PLAYER_IFACE, name)), "(v)")
        return reply[0] if reply else None

    def _set_property(self, player, name, variant):
        return self._call(player, MPRIS_PATH, PROPS_IFACE, "Set",
                          self._GLib.Variant("(ssv)", (PLAYER_IFACE, name, variant)), None)

    def _player_method(self, player, method, params=None):
        return self._call(player, MPRIS_PATH, PLAYER_IFACE, method, params, None)

    # ----- state -----------------------------------------------------------
    def state(self):
        player = self._player()
        if not player:
            return {"active": False, "backend": self.backend}

        props = self._properties(player) or {}
        metadata = props.get("Metadata") or {}
        status = props.get("PlaybackStatus") or "Stopped"

        artist = metadata.get("xesam:artist") or metadata.get("xesam:artistName") or ""
        if isinstance(artist, (list, tuple)):
            artist = ", ".join(str(part) for part in artist)
        title = metadata.get("xesam:title") or ""
        album = metadata.get("xesam:album") or ""
        length_us = metadata.get("mpris:length") or 0
        art_url = metadata.get("mpris:artUrl") or ""
        try:
            duration_ms = int(length_us) // 1000
        except (TypeError, ValueError):
            duration_ms = 0

        position_ms = self._property(player, "Position") or 0
        try:
            position_ms = int(position_ms) // 1000
        except (TypeError, ValueError):
            position_ms = 0

        volume = props.get("Volume")
        try:
            volume_percent = round(float(volume) * 100)
        except (TypeError, ValueError):
            volume_percent = self._volume

        loop = props.get("LoopStatus") or "None"
        repeat = {"Track": "track", "Playlist": "context"}.get(loop, "off")

        return {
            "active": True,
            "backend": self.backend,
            "is_playing": status == "Playing",
            "title": str(title),
            "artist": str(artist),
            "album": str(album),
            "duration_ms": duration_ms,
            "progress_ms": position_ms,
            "art_url": str(art_url) or None,
            "volume": volume_percent,
            "shuffle": bool(props.get("Shuffle")),
            "repeat": repeat,
            "track_id": str(metadata.get("mpris:trackid") or ""),
        }

    # ----- transport -------------------------------------------------------
    def play(self):
        return self._transport("Play")

    def pause(self):
        return self._transport("Pause")

    def next(self):
        return self._transport("Next")

    def previous(self):
        return self._transport("Previous")

    def _transport(self, method):
        player = self._player()
        if not player:
            return False
        return self._player_method(player, method) is not None

    def seek(self, position_ms):
        player = self._player()
        if not player:
            return False
        metadata = (self._properties(player) or {}).get("Metadata") or {}
        track_id = str(metadata.get("mpris:trackid") or "")
        microseconds = max(0, int(position_ms)) * 1000
        if track_id:
            result = self._player_method(player, "SetPosition",
                                         self._GLib.Variant("(ox)", (track_id, microseconds)))
            if result is not None:
                return True
        return self._player_method(player, "Seek", self._GLib.Variant("(x)", (microseconds,))) is not None

    def set_volume(self, percent):
        player = self._player()
        if not player:
            return False
        value = max(0.0, min(1.0, float(percent) / 100.0))
        ok = self._set_property(player, "Volume", self._GLib.Variant("d", value)) is not None
        if ok:
            self._volume = int(percent)
        return ok

    def set_shuffle(self, enabled):
        player = self._player()
        if not player:
            return False
        return self._set_property(player, "Shuffle", self._GLib.Variant("b", bool(enabled))) is not None

    def set_repeat(self, state):
        player = self._player()
        if not player:
            return False
        loop = {"track": "Track", "context": "Playlist"}.get(str(state), "None")
        return self._set_property(player, "LoopStatus", self._GLib.Variant("s", loop)) is not None

    def open_uri(self, uri):
        friendly = "No app on this PC can open Spotify links — is the Spotify client installed?"
        try:
            if self._Gio.AppInfo.launch_default_for_uri(uri, None):
                return True, ""
        except Exception:  # noqa: BLE001, S110
            pass
        if shutil.which("xdg-open"):
            try:
                result = subprocess.run(
                    ["xdg-open", uri],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                )
                if result.returncode == 0:
                    return True, ""
            except Exception:  # noqa: BLE001, S110
                pass
        return False, friendly
