"""
Windows media controller for the Spotify desktop client.

Reads the real playback state from the Windows Global System Media Transport
Controls (SMTC) session that Spotify registers, and sends true play / pause /
next / previous / seek commands to it. None of this needs Spotify Premium.

Volume commands are posted to Spotify's window. Playback commands use the SMTC
session and report failure when no session is available.
"""

import ctypes
import json
import os
import queue
import subprocess
import threading
import time
from ctypes import Structure, byref, wintypes

from media_controller import BaseMediaController

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
WM_APPCOMMAND = 0x0319
APPCOMMAND_VOL_UP = 10 << 16
APPCOMMAND_VOL_DOWN = 9 << 16
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SMTC_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smtc_helper.ps1")


class PROCESSENTRY32W(Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def get_spotify_pids():
    pids = set()
    TH32CS_SNAPPROCESS = 0x00000002
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return pids
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    if kernel32.Process32FirstW(snapshot, byref(entry)):
        while True:
            if entry.szExeFile.lower() == "spotify.exe":
                pids.add(entry.th32ProcessID)
            if not kernel32.Process32NextW(snapshot, byref(entry)):
                break
    kernel32.CloseHandle(snapshot)
    return pids


class SmtcClient:
    """Keeps one PowerShell process alive and talks to it with JSON lines."""

    def __init__(self, script_path):
        self._script = script_path
        self._proc = None
        self._queue = None
        self._io_lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._last_error = ""

    def warm_up(self):
        threading.Thread(target=self._warm_up, daemon=True).start()

    def _warm_up(self):
        reply = self.request("ping", timeout=25)
        if not reply.get("ok"):
            self._last_error = reply.get("error") or "PowerShell media-session helper did not start."

    def _spawn(self):
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        self._proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                self._script,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        self._queue = queue.Queue()
        proc, out_queue = self._proc, self._queue

        def _reader():
            try:
                for line in proc.stdout:
                    out_queue.put(line)
            except Exception:  # noqa: BLE001, S110
                pass
            out_queue.put(None)

        threading.Thread(target=_reader, daemon=True).start()

    def _kill(self):
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001, S110
                pass

    def request(self, op, timeout=8, **payload):
        with self._io_lock:
            with self._start_lock:
                if self._proc is None or self._proc.poll() is not None:
                    self._spawn()
            if self._proc is None or self._queue is None:
                return {}
            try:
                self._proc.stdin.write(json.dumps({"op": op, **payload}) + "\n")
                self._proc.stdin.flush()
            except Exception:  # noqa: BLE001
                self._kill()
                return {}
            try:
                raw = self._queue.get(timeout=timeout)
            except queue.Empty:
                self._kill()
                return {}
            if raw is None:
                self._kill()
                return {}
            try:
                return json.loads(raw)
            except Exception:  # noqa: BLE001
                return {}


class WindowsMediaController(BaseMediaController):
    backend = "smtc"
    supports_seek = True
    supports_volume = True

    def __init__(self):
        super().__init__()
        self._smtc = SmtcClient(SMTC_SCRIPT)
        self._smtc.warm_up()
        self._volume_lock = threading.Lock()
        self.spotify_volume = 70
        self.spotify_hwnd = 0

    # ----- state -----------------------------------------------------------
    def _smtc_ok(self, reply):
        return bool(reply.get("ok"))

    def state(self):
        reply = self._smtc.request("state")
        if not self._smtc_ok(reply) or not reply.get("active"):
            return {"active": False, "backend": self.backend}
        self.supports_shuffle = bool(reply.get("shuffle_supported"))
        self.supports_repeat = bool(reply.get("repeat_supported"))
        self.supports_seek = bool(reply.get("seek_supported"))
        return {
            "active": True,
            "backend": self.backend,
            "is_playing": bool(reply.get("playing")),
            "title": reply.get("title") or "",
            "artist": reply.get("artist") or "",
            "album": reply.get("album") or "",
            "duration_ms": int(reply.get("duration_ms") or 0),
            "progress_ms": int(reply.get("position_ms") or 0),
            "position_is_current": True,
            "shuffle": bool(reply.get("shuffle")),
            "repeat": reply.get("repeat") or "off",
            "volume": self.spotify_volume,
        }

    # ----- transport -------------------------------------------------------
    def _action(self, action, **payload):
        reply = self._smtc.request(action, timeout=5, **payload)
        if self._smtc_ok(reply):
            return True
        if action in ("play", "pause", "next", "prev"):
            return self._media_key(action)
        return False

    def play(self):
        return self._action("play")

    def pause(self):
        return self._action("pause")

    def next(self):
        return self._action("next")

    def previous(self):
        return self._action("prev")

    def seek(self, position_ms):
        return self._action("seek", ms=max(0, int(position_ms)))

    def set_shuffle(self, state):
        return self._action("shuffle", ms=int(bool(state)))

    def set_repeat(self, state):
        modes = {"off": 0, "track": 1, "context": 2}
        return state in modes and self._action("repeat", ms=modes[state])

    def set_volume(self, percent):
        percent = max(0, min(100, int(percent)))
        with self._volume_lock:
            previous = self.spotify_volume
            steps = max(1, abs(percent - previous) // 5)
            command = APPCOMMAND_VOL_UP if percent >= previous else APPCOMMAND_VOL_DOWN
            hwnd = self._spotify_window()
            if hwnd:
                for _ in range(steps):
                    user32.PostMessageW(hwnd, WM_APPCOMMAND, hwnd, command)
            self.spotify_volume = percent
        return bool(hwnd)

    def open_uri(self, uri):
        try:
            os.startfile(uri)
            return True, ""
        except Exception as exc:  # noqa: BLE001
            return False, f"Windows could not open {uri}: {exc}"

    # ----- helpers ---------------------------------------------------------
    def _media_key(self, action):
        key = {"play": VK_MEDIA_PLAY_PAUSE, "pause": VK_MEDIA_PLAY_PAUSE,
               "next": VK_MEDIA_NEXT_TRACK, "prev": VK_MEDIA_PREV_TRACK}[action]
        user32.keybd_event(key, 0, KEYEVENTF_EXTENDEDKEY, 0)
        time.sleep(0.01)
        user32.keybd_event(key, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        return True

    def _spotify_window(self):
        pids = get_spotify_pids()
        if not pids:
            return 0
        found = []

        def _callback(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, byref(pid))
            if pid.value not in pids:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                found.append(hwnd)
            return True

        callback = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(_callback)
        user32.EnumWindows(callback, 0)
        if found:
            self.spotify_hwnd = found[0]
        return self.spotify_hwnd

    def close(self):
        self._smtc.request("quit", timeout=2)
