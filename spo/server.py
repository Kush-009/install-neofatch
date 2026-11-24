import base64
import concurrent.futures
import hashlib
import http.server
import json
import os
import socket
import socketserver
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from media_controller import create_controller

# Fix SSL certificate verification on Windows
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()
    SSL_CONTEXT.check_hostname = False
    SSL_CONTEXT.verify_mode = ssl.CERT_NONE

media = create_controller()

PORT = int(os.environ.get("PORT", "5000"))
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public')

# Detect local IP address
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:  # noqa: BLE001
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

LOCAL_IP = get_local_ip()

# Load / Save Config
def load_config():
    default_config = {
        "client_id": "",
        "client_secret": "",
        "redirect_uri": f"http://{LOCAL_IP}:{PORT}/callback",
        "access_token": "",
        "refresh_token": "",
        "expires_at": 0,
        "demo_mode": False
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:  # noqa: BLE001
            print(f"[Config] Error loading {CONFIG_FILE}: {e}")
    # Always ensure redirect_uri points to current IP or user custom
    if not default_config.get("redirect_uri"):
        default_config["redirect_uri"] = f"http://{LOCAL_IP}:{PORT}/callback"
    return default_config

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:  # noqa: BLE001
        print(f"[Config] Error saving config: {e}")

CONFIG = load_config()

# Demo state for offline/demo mode (matching user's reference mockup!)
DEMO_TRACKS = [
    {
        "id": "demo_1",
        "title": "Night Changes",
        "artist": "One Direction",
        "album": "FOUR",
        "duration_ms": 226000,
        "cover_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=500&auto=format&fit=crop&q=80",
        "lyrics_synced": """[00:00.00]Goin' out tonight, changes into something red
[00:08.50]Her mother doesn't like that kind of dress
[00:13.20]Everything she never had, she's showin' off
[00:19.40]Drivin' too fast, moon is breakin' through her hair
[00:27.50]She's headin' for somethin' that she won't forget
[00:32.40]Havin' no regrets is all that she really wants
[00:38.20]We're only gettin' older, baby
[00:43.00]And I've been thinkin' about it lately
[00:47.80]Does it ever drive you crazy
[00:52.20]Just how fast the night changes?
[00:57.40]Everything that you've ever dreamed of
[01:02.10]Disappearin' when you wake up
[01:06.80]But there's nothin' to be afraid of
[01:11.40]Even when the night changes
[01:16.20]It will never change me and you
[01:24.00]Turn around, every now and then
[01:29.50]I get a little bit lonely
[01:34.20]And you're never coming round
[01:39.10]Turn around, every now and then
[01:44.00]Chasin' her tonight, doubts are runnin' 'round her head
[01:52.40]He's waitin', hides behind a cigarette
[01:57.20]Heart is beatin' loud and she doesn't want it to stop
[02:03.00]We're only gettin' older, baby
[02:07.80]And I've been thinkin' about it lately
[02:12.60]Does it ever drive you crazy
[02:17.10]Just how fast the night changes?
[02:22.20]It will never change me and you"""
    },
    {
        "id": "demo_2",
        "title": "Starboy",
        "artist": "The Weeknd, Daft Punk",
        "album": "Starboy",
        "duration_ms": 230000,
        "cover_url": "https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=500&auto=format&fit=crop&q=80",
        "lyrics_synced": """[00:00.00]I'm tryna put you in the worst mood, ah
[00:04.20]P1 cleaner than your church shoes, ah
[00:08.50]Milli point two just to hurt you, ah
[00:12.60]All red Lamb' just to tease you, ah
[00:16.80]None of these toys on lease too, ah
[00:21.00]Made your whole year in a week too, yah
[00:25.20]Main bitch out your league too, ah
[00:29.50]Side bitch out of your league too, ah
[00:33.80]Look what you've done
[00:37.40]I'm a motherfuckin' starboy
[00:41.80]Look what you've done
[00:45.60]I'm a motherfuckin' starboy"""
    },
    {
        "id": "demo_3",
        "title": "Midnight City",
        "artist": "M83",
        "album": "Hurry Up, We're Dreaming",
        "duration_ms": 243000,
        "cover_url": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500&auto=format&fit=crop&q=80",
        "lyrics_synced": """[00:00.00]Waiting in a car
[00:15.50]Waiting for a ride in the dark
[00:30.00]The night city grows
[00:45.20]Look and see her eyes, they glow
[01:00.50]Waiting in a car
[01:15.00]Waiting for a ride in the dark
[01:30.20]The city is my church
[01:45.50]It wraps me in the blinding twilight"""
    }
]

DEMO_PLAYLISTS = [
    {
        "id": "liked",
        "name": "Liked Songs",
        "type": "liked",
        "track_count": 1248,
        "cover_url": "gradient-purple",
        "tracks": DEMO_TRACKS
    },
    {
        "id": "pl_1",
        "name": "Chill Vibes",
        "type": "playlist",
        "track_count": 87,
        "cover_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=300&auto=format&fit=crop&q=80",
        "tracks": [DEMO_TRACKS[0], DEMO_TRACKS[2]]
    },
    {
        "id": "pl_2",
        "name": "Gaming Music",
        "type": "playlist",
        "track_count": 142,
        "cover_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=300&auto=format&fit=crop&q=80",
        "tracks": [DEMO_TRACKS[1]]
    },
    {
        "id": "pl_3",
        "name": "Anime OP/ED",
        "type": "playlist",
        "track_count": 73,
        "cover_url": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=300&auto=format&fit=crop&q=80",
        "tracks": [DEMO_TRACKS[0], DEMO_TRACKS[1]]
    }
]

class DemoState:
    def __init__(self):
        self.track_index = 0
        self.is_playing = True
        self.progress_ms = 84000  # 1:24 like reference!
        self.volume = 70
        self.shuffle = False
        self.repeat = "off"
        self.last_update = time.time()
        self.liked_track_ids = {"demo_1"}
        self.queue = [DEMO_TRACKS[1], DEMO_TRACKS[2]]

    def get_current_track(self):
        return DEMO_TRACKS[self.track_index % len(DEMO_TRACKS)]

    def tick(self):
        now = time.time()
        if self.is_playing:
            elapsed = int((now - self.last_update) * 1000)
            self.progress_ms += elapsed
            cur_track = self.get_current_track()
            if self.progress_ms >= cur_track["duration_ms"]:
                if self.repeat == "track":
                    self.progress_ms = 0
                else:
                    self.next()
        self.last_update = now

    def play(self):
        self.is_playing = True
        self.last_update = time.time()

    def pause(self):
        self.tick()
        self.is_playing = False

    def toggle(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def next(self):
        self.track_index = (self.track_index + 1) % len(DEMO_TRACKS)
        self.progress_ms = 0
        self.last_update = time.time()

    def prev(self):
        if self.progress_ms > 3000:
            self.progress_ms = 0
        else:
            self.track_index = (self.track_index - 1 + len(DEMO_TRACKS)) % len(DEMO_TRACKS)
            self.progress_ms = 0
        self.last_update = time.time()

    def seek(self, pos_ms):
        cur_track = self.get_current_track()
        self.progress_ms = max(0, min(pos_ms, cur_track["duration_ms"]))
        self.last_update = time.time()

    def to_playback_dict(self):
        self.tick()
        t = self.get_current_track()
        return {
            "is_playing": self.is_playing,
            "progress_ms": self.progress_ms,
            "item": {
                "id": t["id"],
                "name": t["title"],
                "artists": [{"name": a.strip()} for a in t["artist"].split(",")],
                "album": {
                    "name": t["album"],
                    "images": [{"url": t["cover_url"]}]
                },
                "duration_ms": t["duration_ms"]
            },
            "device": {
                "name": "Tablet Deck Simulator",
                "volume_percent": self.volume
            },
            "shuffle_state": self.shuffle,
            "repeat_state": self.repeat,
            "is_demo": True
        }

demo_state = DemoState()

# Spotify API Helper
class SpotifyClient:
    def __init__(self):
        self.is_premium = True
        self.product = None
        self.api_error = None
        self._last_check = 0
        self._product_lock = threading.Lock()

    def detect_product(self):
        """Read /me to learn whether this is a Premium or free account.

        Since March 2026 Spotify refuses every Web API call from apps whose
        owner has no Premium subscription, so a 403 here means the API is
        unusable and the deck has to rely on the local media session.
        """
        token = self.get_token()
        if not token:
            return None
        self._last_check = time.time()
        url = "https://api.spotify.com/v1/me"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            body = he.read().decode("utf-8", errors="replace")
            with self._product_lock:
                self.is_premium = False
                self.product = None
                self.api_error = (
                    "Spotify Premium is required for the Web API (playlists, search, queue)."
                    if "premium" in body.lower()
                    else f"Spotify Web API error {he.code}."
                )
            print(f"[Spotify] Web API unavailable: {he.code} {body[:200]}")
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"[Spotify] Could not read account type: {exc}")
            return None
        with self._product_lock:
            self.product = data.get("product")
            self.is_premium = self.product == "premium"
            self.api_error = None if self.is_premium else "Spotify Premium is required for playlists and search."
        print(f"[Spotify] Account type: {self.product or 'unknown'}")
        return self.product

    def ensure_product(self):
        with self._product_lock:
            recent = (time.time() - self._last_check) < 600
            known = self.product is not None and self.is_premium
        if known or recent:
            return self.product
        return self.detect_product()

    def api_ready(self):
        """True only when the Web API is known to answer (Premium account)."""
        return bool(self.product == "premium" and self.is_premium and self.get_token())

    def get_token(self):
        if not CONFIG.get("access_token"):
            return None
        
        # Check if expired
        now = time.time()
        if now > CONFIG.get("expires_at", 0) - 60:
            if CONFIG.get("refresh_token"):
                success = self.refresh_token()
                if not success:
                    return None
            else:
                return None
        return CONFIG.get("access_token")

    def refresh_token(self):
        refresh_token = CONFIG.get("refresh_token")
        client_id = CONFIG.get("client_id")
        client_secret = CONFIG.get("client_secret")
        if not (refresh_token and client_id and client_secret):
            return False

        url = "https://accounts.spotify.com/api/token"
        payload = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }).encode("utf-8")

        auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Basic {auth_header}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                CONFIG["access_token"] = data.get("access_token")
                if "refresh_token" in data:
                    CONFIG["refresh_token"] = data["refresh_token"]
                CONFIG["expires_at"] = time.time() + data.get("expires_in", 3600)
                save_config(CONFIG)
                print("[Spotify] Token successfully refreshed.")
                return True
        except Exception as e:  # noqa: BLE001
            print(f"[Spotify] Error refreshing token: {e}")
            return False

    def api_request(self, endpoint, method="GET", body=None, params=None):
        token = self.get_token()
        if not token:
            return None, 401

        url = f"https://api.spotify.com/v1/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
                status = resp.status
                if status == 204:
                    return {}, 204
                content = resp.read()
                if not content:
                    return {}, status
                return json.loads(content.decode("utf-8")), status
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001, S110
                pass
            if e.code == 403 and "premium" in error_body.lower():
                self.is_premium = False
                self.api_error = "Spotify requires Premium for this request or the owner of this development app."
            else:
                print(f"[Spotify API] {method} {endpoint} -> {e.code} {error_body[:120]}")
            if e.code == 401:  # noqa: SIM102
                # Retry once after refresh
                if self.refresh_token():
                    token = self.get_token()
                    req.headers["Authorization"] = f"Bearer {token}"
                    try:
                        with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
                            if resp.status == 204:
                                return {}, 204
                            return json.loads(resp.read().decode("utf-8")), resp.status
                    except Exception as retry_err:  # noqa: BLE001
                        print(f"[Spotify API] Retry failed: {retry_err}")
                        return None, getattr(retry_err, 'code', 500)
            return None, e.code
        except Exception as err:  # noqa: BLE001
            print(f"[Spotify API] {method} {endpoint} -> Exception: {err}")
            return None, 500

spotify_client = SpotifyClient()

# ---- Native playback helpers (free accounts) ----------------------------

_artwork_cache = {}
_artwork_pending = set()
_artwork_lock = threading.Lock()


def _fetch_artwork(key, artist, title):
    url = ""
    try:
        term = urllib.parse.quote(f"{artist} {title}".strip())
        req = urllib.request.Request(
            f"https://itunes.apple.com/search?term={term}&entity=song&limit=1",
            headers={"User-Agent": "SpotifyTabletDeck/1.0"},
        )
        with urllib.request.urlopen(req, timeout=6, context=SSL_CONTEXT) as resp:
            results = json.loads(resp.read().decode("utf-8")).get("results") or []
        if results:
            artwork = results[0].get("artworkUrl100") or ""
            url = artwork.replace("100x100bb", "600x600bb")
    except Exception:  # noqa: BLE001
        url = ""
    with _artwork_lock:
        _artwork_cache[key] = url
        _artwork_pending.discard(key)


def artwork_url_for(artist, title):
    key = f"{artist}|{title}".strip().lower()
    if not key.strip("|"):
        return ""
    with _artwork_lock:
        if key in _artwork_cache:
            return _artwork_cache[key]
        if key not in _artwork_pending:
            _artwork_pending.add(key)
            threading.Thread(target=_fetch_artwork, args=(key, artist, title), daemon=True).start()
    return ""


_last_state = {"at": 0.0, "state": None, "raw": None}
_native_state_lock = threading.Lock()


def smooth_native_state(state):
    with _native_state_lock:
        now = time.monotonic()
        prev = _last_state["state"]
        if not state or not state.get("active"):
            _last_state.update(at=now, state=None, raw=None)
            return state
        raw = max(0, int(state.get("progress_ms") or 0))
        progress = raw
        same_track = prev and all(
            prev.get(field) == state.get(field)
            for field in ("title", "artist", "album", "duration_ms")
        )
        if (
            same_track and prev.get("is_playing") and state.get("is_playing")
            and not state.get("position_is_current") and raw == _last_state["raw"]
        ):
            progress = int(prev.get("progress_ms") or 0) + round((now - _last_state["at"]) * 1000)
        duration = int(state.get("duration_ms") or 0)
        if duration:
            progress = min(progress, duration)
        state = {**state, "progress_ms": progress}
        _last_state.update(at=now, state=state, raw=raw)
        return state


def native_playback_payload(state, shuffle_supported=False, repeat_supported=False):
    """Shape a native media-session state like the Web API player JSON."""
    if not state or not state.get("active"):
        return {
            "is_playing": False,
            "progress_ms": 0,
            "item": None,
            "device": {"name": "Open Spotify on this PC", "volume_percent": 0},
            "shuffle_state": False,
            "repeat_state": "off",
            "shuffle_supported": shuffle_supported,
            "repeat_supported": repeat_supported,
            "is_local_control": True,
            "player_available": False,
        }

    title = state.get("title") or "Spotify"
    artist = state.get("artist") or "Spotify"
    album = state.get("album") or ""
    duration = int(state.get("duration_ms") or 0)
    art = state.get("art_url") or artwork_url_for(artist, title)
    item_id = "local_" + hashlib.md5(f"{artist}|{title}".encode()).hexdigest()[:12]
    return {
        "is_playing": bool(state.get("is_playing")),
        "progress_ms": int(state.get("progress_ms") or 0),
        "item": {
            "id": item_id,
            "name": title,
            "duration_ms": duration,
            "artists": [{"name": artist}],
            "album": {
                "name": album or title,
                "images": [{"url": art, "width": 600, "height": 600}] if art else [],
            },
        },
        "device": {
            "name": "Spotify desktop" if state.get("backend") == "smtc" else "Spotify (MPRIS)",
            "volume_percent": int(state.get("volume") or 0),
        },
        "shuffle_state": bool(state.get("shuffle", False)),
        "repeat_state": state.get("repeat") or "off",
        "shuffle_supported": shuffle_supported,
        "repeat_supported": repeat_supported,
        "is_local_control": True,
        "player_available": True,
    }


# Lyrics fetcher (LRCLIB + fallback)
def get_lyrics(title, artist, duration_ms=0):
    if not title or title.lower() in ("spotify pc client", "ready to play"):
        return {"syncedLyrics": None, "plainLyrics": "Play a song in Spotify to load lyrics.", "source": "none"}

    print(f"[Lyrics] Fetching lyrics for: '{title}' by '{artist}'...")

    # Helper function to query lrclib
    def query_lrclib(params):
        url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "SpotifyTabletDeck/1.0"})
        with urllib.request.urlopen(req, timeout=4, context=SSL_CONTEXT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("syncedLyrics"):
                return {"syncedLyrics": data["syncedLyrics"], "plainLyrics": data.get("plainLyrics", ""), "source": "lrclib"}
            elif data.get("plainLyrics"):
                return {"syncedLyrics": None, "plainLyrics": data["plainLyrics"], "source": "lrclib_plain"}
        return None

    # 1. Try exact title & artist
    try:
        p = {"track_name": title, "artist_name": artist}
        if duration_ms > 0:
            p["duration"] = int(duration_ms / 1000)
        res = query_lrclib(p)
        if res:
            print(f"[Lyrics] Exact match found ({'Synced' if res['syncedLyrics'] else 'Plain'}).")
            return res
    except Exception:  # noqa: BLE001, S110
        pass

    # 2. Try swapped (in case title is formatted Artist - Title vs Title - Artist)
    try:
        p = {"track_name": artist, "artist_name": title}
        if duration_ms > 0:
            p["duration"] = int(duration_ms / 1000)
        res = query_lrclib(p)
        if res:
            print(f"[Lyrics] Swapped match found ({'Synced' if res['syncedLyrics'] else 'Plain'}).")
            return res
    except Exception:  # noqa: BLE001, S110
        pass

    # 3. Fallback to LRCLIB Search
    try:
        search_url = "https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": f"{title} {artist}"})
        req = urllib.request.Request(search_url, headers={"User-Agent": "SpotifyTabletDeck/1.0"})
        with urllib.request.urlopen(req, timeout=4, context=SSL_CONTEXT) as resp:
            results = json.loads(resp.read().decode("utf-8"))
            if results and isinstance(results, list):
                for r in results:
                    if r.get("syncedLyrics"):
                        print("[Lyrics] Search match found (Synced).")
                        return {"syncedLyrics": r["syncedLyrics"], "plainLyrics": r.get("plainLyrics", ""), "source": "lrclib_search"}
                if results[0].get("plainLyrics"):
                    print("[Lyrics] Search match found (Plain).")
                    return {"syncedLyrics": None, "plainLyrics": results[0]["plainLyrics"], "source": "lrclib_search_plain"}
    except Exception:  # noqa: BLE001, S110
        pass

    print(f"[Lyrics] No lyrics found online for '{title}'.")
    return {
        "syncedLyrics": None,
        "plainLyrics": f"Playing: {title}\nby {artist}\n\n(No synchronized lyrics available for this song)",
        "source": "none"
    }

_playlist_items = {}
_playlist_items_lock = threading.Lock()
_demo_playlist_tracks = {}


def valid_spotify_id(value):
    return len(value) == 22 and value.isascii() and value.isalnum()


def playlist_track_uris(playlist_id, snapshot_id):
    """URIs in a playlist, cached until its snapshot changes. None when unreadable."""
    with _playlist_items_lock:
        cached = _playlist_items.get(playlist_id)
        if cached and snapshot_id and cached["snapshot"] == snapshot_id:
            return set(cached["uris"])
    uris = set()
    offset = 0
    for _page in range(200):
        data, status = spotify_client.api_request(
            f"playlists/{playlist_id}/items", params={"limit": 50, "offset": offset})
        if status != 200:
            return None
        entries = (data or {}).get("items") or []
        for entry in entries:
            track = (entry or {}).get("item") or (entry or {}).get("track") or {}
            if track.get("uri"):
                uris.add(track["uri"])
        if not entries or not (data or {}).get("next"):
            break
        offset += len(entries)
    with _playlist_items_lock:
        _playlist_items[playlist_id] = {"snapshot": snapshot_id, "uris": set(uris)}
    return uris


def remember_playlist_change(playlist_id, uri, added, snapshot_id):
    with _playlist_items_lock:
        cached = _playlist_items.get(playlist_id)
        if not cached:
            return
        if not snapshot_id:
            del _playlist_items[playlist_id]
            return
        (cached["uris"].add if added else cached["uris"].discard)(uri)
        cached["snapshot"] = snapshot_id


def editable_playlists():
    """Playlists the signed-in user may change, as (list, status)."""
    me, status = spotify_client.api_request("me")
    if status != 200:
        return [], status
    user_id = (me or {}).get("id")
    playlists = []
    offset = 0
    for _page in range(4):
        data, status = spotify_client.api_request("me/playlists", params={"limit": 50, "offset": offset})
        if status != 200:
            return [], status
        entries = (data or {}).get("items") or []
        for playlist in entries:
            if not playlist or not playlist.get("id"):
                continue
            owner_id = (playlist.get("owner") or {}).get("id")
            if owner_id != user_id and not playlist.get("collaborative"):
                continue
            images = playlist.get("images") or []
            playlists.append({
                "id": playlist["id"], "name": playlist.get("name") or "Playlist",
                "cover_url": images[0]["url"] if images else "",
                "snapshot_id": playlist.get("snapshot_id"),
            })
        if not entries or not (data or {}).get("next"):
            break
        offset += len(entries)
    return playlists, 200


def find_track_id(title, artist):
    """Look a song up by name when the local media session gives no Spotify ID."""
    query = " ".join(part for part in (title, artist) if part).strip()
    if not query:
        return None, 404
    data, status = spotify_client.api_request("search", params={"q": query, "type": "track", "limit": 5})
    if status != 200:
        return None, status
    tracks = ((data or {}).get("tracks") or {}).get("items") or []
    for track in tracks:
        if track and track.get("id"):
            return track["id"], 200
    return None, 404


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # Silence routine static polling requests
        pass

    def send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception:  # noqa: BLE001, S110
            pass

    def spotify_error(self, status):
        if status == 401:
            return "Connect Spotify in Settings, then try again."
        if status == 403:
            return spotify_client.api_error or "Spotify denied access. Reconnect for updated permissions; app-owner or account restrictions may still apply."
        if status == 429:
            return "Spotify rate limit reached. Try again later."
        return f"Spotify request failed (HTTP {status})."

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # Spotify OAuth Callback
        if path == "/callback":
            code = qs.get("code", [None])[0]
            error = qs.get("error", [None])[0]
            if code:
                # Exchange code for token
                client_id = CONFIG.get("client_id")
                client_secret = CONFIG.get("client_secret")
                redirect_uri = CONFIG.get("redirect_uri")
                payload = urllib.parse.urlencode({
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri
                }).encode("utf-8")
                auth_str = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("utf-8")
                req = urllib.request.Request("https://accounts.spotify.com/api/token", data=payload, method="POST")
                req.add_header("Authorization", f"Basic {auth_str}")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                try:
                    with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
                        token_data = json.loads(resp.read().decode("utf-8"))
                        CONFIG["access_token"] = token_data.get("access_token")
                        CONFIG["refresh_token"] = token_data.get("refresh_token")
                        CONFIG["expires_at"] = time.time() + token_data.get("expires_in", 3600)
                        CONFIG["demo_mode"] = False
                        save_config(CONFIG)
                        print("[Auth] Successfully logged into Spotify!")
                        self.send_response(302)
                        self.send_header("Location", "/?auth=success")
                        self.end_headers()
                        return
                except urllib.error.HTTPError as he:
                    error_body = he.read().decode("utf-8", errors="replace")
                    print(f"[Auth] Token exchange failed: {he.code} {error_body}")
                    self.send_response(302)
                    self.send_header("Location", f"/?auth=error&msg={urllib.parse.quote(f'{he.code}: {error_body}')}")
                    self.end_headers()
                    return
                except Exception as e:  # noqa: BLE001
                    print(f"[Auth] Token exchange failed: {e}")
                    self.send_response(302)
                    self.send_header("Location", f"/?auth=error&msg={urllib.parse.quote(str(e))}")
                    self.end_headers()
                    return
            else:
                self.send_response(302)
                self.send_header("Location", f"/?auth=denied&msg={error}")
                self.end_headers()
                return

        # Status endpoint
        if path == "/api/status":
            token = spotify_client.get_token()
            if token:
                spotify_client.ensure_product()
            player = media.state()
            self.send_json({
                "connected": bool(token) and not CONFIG.get("demo_mode", False),
                "demo_mode": CONFIG.get("demo_mode", False),
                "premium": bool(token) and spotify_client.is_premium,
                "account_type": spotify_client.product,
                "api_error": spotify_client.api_error,
                "native_control": media.backend != "none",
                "backend": media.backend,
                "player_available": bool(player.get("active")),
                "local_ip": LOCAL_IP,
                "port": PORT,
                "client_id": CONFIG.get("client_id", ""),
                "redirect_uri": CONFIG.get("redirect_uri", f"http://{LOCAL_IP}:{PORT}/callback")
            })
            return

        # Auth Login URL
        if path == "/api/auth/url":
            client_id = CONFIG.get("client_id")
            redirect_uri = CONFIG.get("redirect_uri", f"http://{LOCAL_IP}:{PORT}/callback")
            if not client_id:
                self.send_json({"error": "Client ID is not configured. Go to Settings to add it."}, status=400)
                return
            scopes = [
                "user-read-playback-state",
                "user-modify-playback-state",
                "user-read-currently-playing",
                "playlist-read-private",
                "playlist-read-collaborative",
                "playlist-modify-private",
                "playlist-modify-public",
                "user-library-read",
                "user-library-modify",
                "user-read-recently-played"
            ]
            auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
                "response_type": "code",
                "client_id": client_id,
                "scope": " ".join(scopes),
                "redirect_uri": redirect_uri
            })
            self.send_json({"url": auth_url})
            return

        # Spotify Playback
        if path == "/api/playback":
            if CONFIG.get("demo_mode", False):
                self.send_json(demo_state.to_playback_dict())
                return
            
            # 1. Spotify Web API (only answers player reads for Premium)
            if spotify_client.get_token():
                spotify_client.ensure_product()
            if spotify_client.api_ready():
                data, status = spotify_client.api_request("me/player")
                if status == 200 and data:
                    self.send_json(data)
                    return

            # 2. Native media session (free accounts, no Premium needed)
            state = smooth_native_state(media.state())
            self.send_json(native_playback_payload(state, media.supports_shuffle, media.supports_repeat))
            return

        if path == "/api/playlists":
            if CONFIG.get("demo_mode", False):
                self.send_json({"items": DEMO_PLAYLISTS})
                return
            data, status = spotify_client.api_request("me/playlists", params={"limit": 50})
            if status != 200:
                self.send_json({"items": [], "api_error": self.spotify_error(status)}, status=status)
                return
            playlists = [{"id": "liked", "name": "Liked Songs", "type": "liked",
                          "track_count": None, "cover_url": "gradient-purple"}]
            for playlist in (data or {}).get("items", []):
                if not playlist:
                    continue
                images = playlist.get("images") or []
                playlists.append({
                    "id": playlist.get("id"), "name": playlist.get("name"),
                    "type": "playlist", "uri": playlist.get("uri"),
                    "track_count": (playlist.get("items") or playlist.get("tracks") or {}).get("total"),
                    "cover_url": images[0]["url"] if images else "",
                })
            self.send_json({"items": playlists, "next": (data or {}).get("next")})
            return

        if path in ("/api/playlist/tracks", "/api/library"):
            playlist_id = qs.get("id", ["liked"])[0]
            kind = qs.get("kind", ["liked"])[0]
            if path == "/api/library":
                endpoint = "me/player/recently-played" if kind == "recent" else "me/tracks"
            elif playlist_id == "liked":
                endpoint = "me/tracks"
            elif len(playlist_id) == 22 and playlist_id.isascii() and playlist_id.isalnum():
                endpoint = f"playlists/{playlist_id}/items"
            else:
                self.send_json({"items": [], "error": "Invalid playlist ID."}, status=400)
                return
            data, status = spotify_client.api_request(endpoint, params={"limit": 50})
            if status != 200:
                self.send_json({"items": [], "error": self.spotify_error(status)}, status=status)
                return
            tracks = [entry.get("item") or entry.get("track") for entry in (data or {}).get("items", []) if entry]
            self.send_json({"items": [track for track in tracks if track], "next": (data or {}).get("next")})
            return

        # Search
        if path == "/api/search":
            query = qs.get("q", [""])[0].strip()
            search_type = qs.get("type", ["track,playlist,artist"])[0]
            if not query:
                self.send_json({"tracks": [], "playlists": [], "artists": []})
                return

            if CONFIG.get("demo_mode", False):
                q_low = query.lower()
                matched_tracks = [t for t in DEMO_TRACKS
                                  if q_low in t["title"].lower() or q_low in t["artist"].lower()]
                matched_pl = [p for p in DEMO_PLAYLISTS if q_low in p["name"].lower()]
                self.send_json({
                    "tracks": {"items": matched_tracks},
                    "playlists": {"items": matched_pl},
                    "artists": {"items": []},
                })
                return

            if not spotify_client.get_token():
                self.send_json({"tracks": {"items": []}, "playlists": {"items": []},
                                "artists": {"items": []}, "needs_login": True})
                return
            if spotify_client.api_error:
                self.send_json({"tracks": {"items": []}, "playlists": {"items": []},
                                "artists": {"items": []}, "api_error": spotify_client.api_error})
                return

            data, status = spotify_client.api_request("search", params={"q": query, "type": search_type, "limit": 10})
            if status == 200 and data:
                self.send_json(data)
            else:
                self.send_json({"tracks": {"items": []}, "playlists": {"items": []},
                                "api_error": spotify_client.api_error or "Spotify search is not available."})
            return

        # Lyrics
        if path == "/api/lyrics":
            title = qs.get("title", [""])[0]
            artist = qs.get("artist", [""])[0]
            duration_ms = int(qs.get("duration", [0])[0] or 0)
            res = get_lyrics(title, artist, duration_ms)
            self.send_json(res)
            return

        # Queue
        if path == "/api/queue":
            if CONFIG.get("demo_mode", False):
                self.send_json({"queue": demo_state.queue})
                return
            data, status = spotify_client.api_request("me/player/queue")
            if status == 200 and data:
                self.send_json(data)
            else:
                self.send_json({"queue": [], "api_error": self.spotify_error(status)}, status=status)
            return

        # Static files fallback
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Parse JSON body
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:  # noqa: BLE001
                body = {}

        # Save credentials
        if path == "/api/config":
            if "client_id" in body:
                CONFIG["client_id"] = body["client_id"].strip()
            if "client_secret" in body and body["client_secret"].strip():
                CONFIG["client_secret"] = body["client_secret"].strip()
            if body.get("redirect_uri"):
                CONFIG["redirect_uri"] = body["redirect_uri"].strip()
            if "demo_mode" in body:
                CONFIG["demo_mode"] = bool(body["demo_mode"])
            save_config(CONFIG)
            self.send_json({"success": True, "config": {
                "client_id": CONFIG.get("client_id"),
                "redirect_uri": CONFIG.get("redirect_uri"),
                "demo_mode": CONFIG.get("demo_mode")
            }})
            return

        # Logout / Disconnect
        if path == "/api/auth/logout":
            CONFIG["access_token"] = ""
            CONFIG["refresh_token"] = ""
            CONFIG["expires_at"] = 0
            CONFIG["demo_mode"] = True
            save_config(CONFIG)
            self.send_json({"success": True})
            return

        # Play/Pause/Resume
        if path == "/api/play":
            if CONFIG.get("demo_mode", False):
                demo_state.play()
                self.send_json({"success": True})
                return
            context_uri = body.get("context_uri")
            uris = body.get("uris")
            offset = body.get("offset")
            payload = {}
            if context_uri:
                payload["context_uri"] = context_uri
            if uris:
                payload["uris"] = uris
            if offset:
                payload["offset"] = offset
            
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request("me/player/play", method="PUT", body=payload if payload else None)
                if status in (200, 204):
                    self.send_json({"success": True, "method": "api"})
                    return

            # Free account: hand the track/album/playlist to the desktop client.
            uri = (uris[0] if uris else None) or context_uri
            if uri:
                opened, error = media.open_uri(uri)
                if opened:
                    self.send_json({"success": True, "method": "native", "message": "Opened in Spotify"})
                else:
                    self.send_json({
                        "success": False,
                        "error": error or "Could not open that item in the Spotify desktop app.",
                    }, status=409)
                return

            if media.play():
                self.send_json({"success": True, "method": "native"})
            else:
                self.send_json({
                    "success": False,
                    "error": "Spotify is not running on this PC, or it exposes no media session.",
                }, status=409)
            return

        if path == "/api/pause":
            if CONFIG.get("demo_mode", False):
                demo_state.pause()
                self.send_json({"success": True})
                return
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request("me/player/pause", method="PUT")
                if status in (200, 204):
                    self.send_json({"success": True, "method": "api"})
                    return
            if media.pause():
                self.send_json({"success": True, "method": "native"})
            else:
                self.send_json({"success": False, "error": "Spotify is not running on this PC."}, status=409)
            return

        if path == "/api/next":
            if CONFIG.get("demo_mode", False):
                demo_state.next()
                self.send_json({"success": True})
                return
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request("me/player/next", method="POST")
                if status in (200, 204):
                    self.send_json({"success": True, "method": "api"})
                    return
            if media.next():
                self.send_json({"success": True, "method": "native"})
            else:
                self.send_json({"success": False, "error": "Spotify is not running on this PC."}, status=409)
            return

        if path == "/api/previous":
            if CONFIG.get("demo_mode", False):
                demo_state.prev()
                self.send_json({"success": True})
                return
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request("me/player/previous", method="POST")
                if status in (200, 204):
                    self.send_json({"success": True, "method": "api"})
                    return
            if media.previous():
                self.send_json({"success": True, "method": "native"})
            else:
                self.send_json({"success": False, "error": "Spotify is not running on this PC."}, status=409)
            return

        if path == "/api/seek":
            pos_ms = int(body.get("position_ms", 0))
            if CONFIG.get("demo_mode", False):
                demo_state.seek(pos_ms)
                self.send_json({"success": True})
                return
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request("me/player/seek", method="PUT", params={"position_ms": pos_ms})
                if status in (200, 204):
                    self.send_json({"success": True, "method": "api"})
                    return
            if media.supports_seek and media.seek(pos_ms):
                with _native_state_lock:
                    _last_state.update(at=0.0, state=None, raw=None)
                self.send_json({"success": True, "method": "native"})
            else:
                self.send_json({"success": False, "error": "Seeking is not available for this player."}, status=409)
            return

        if path == "/api/volume":
            volume_percent = int(body.get("volume_percent", 50))
            if CONFIG.get("demo_mode", False):
                demo_state.volume = volume_percent
                self.send_json({"success": True, "volume": volume_percent})
                return
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request(
                    "me/player/volume", method="PUT", params={"volume_percent": volume_percent})
                if status in (200, 204):
                    self.send_json({"success": True, "volume": volume_percent, "method": "api"})
                    return
            # Controls only Spotify's own volume; the PC master volume is untouched.
            applied = media.supports_volume and media.set_volume(volume_percent)
            self.send_json({"success": bool(applied), "volume": volume_percent, "method": "native"})
            return

        if path == "/api/shuffle":
            state = bool(body.get("state", False))
            if CONFIG.get("demo_mode", False):
                demo_state.shuffle = state
                self.send_json({"success": True, "shuffle": state})
                return
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request(
                    "me/player/shuffle", method="PUT", params={"state": "true" if state else "false"})
                if status in (200, 204):
                    self.send_json({"success": True, "shuffle": state, "method": "api"})
                    return
            if media.supports_shuffle and media.set_shuffle(state):
                self.send_json({"success": True, "shuffle": state, "method": "native"})
            else:
                self.send_json({
                    "success": False,
                    "shuffle": not state,
                    "error": "Spotify did not accept shuffle through the API or local media session.",
                }, status=409)
            return

        if path == "/api/repeat":
            state = body.get("state", "off") # 'off', 'track', 'context'
            if CONFIG.get("demo_mode", False):
                demo_state.repeat = state
                self.send_json({"success": True, "repeat": state})
                return
            if spotify_client.api_ready():
                _res, status = spotify_client.api_request("me/player/repeat", method="PUT", params={"state": state})
                if status in (200, 204):
                    self.send_json({"success": True, "repeat": state, "method": "api"})
                    return
            if media.supports_repeat and media.set_repeat(state):
                self.send_json({"success": True, "repeat": state, "method": "native"})
            else:
                self.send_json({
                    "success": False,
                    "error": "Spotify did not accept repeat through the API or local media session.",
                }, status=409)
            return

        if path == "/api/playlists/create":
            name = str(body.get("name") or "").strip()
            if not name:
                self.send_json({"success": False, "error": "Playlist name required."}, status=400)
                return
            result, status = spotify_client.api_request(
                "me/playlists", method="POST", body={"name": name, "public": False})
            success = status in (200, 201)
            self.send_json({"success": success, "playlist": result if success else None,
                            "error": None if success else self.spotify_error(status)},
                           status=200 if success else status)
            return

        if path == "/api/playlists/options":
            track_id = str(body.get("id") or "")
            if CONFIG.get("demo_mode", False):
                self.send_json({"success": True, "track_id": track_id, "playlists": [
                    {"id": p["id"], "name": p["name"], "cover_url": "",
                     "contains": track_id in _demo_playlist_tracks.get(p["id"], set())}
                    for p in DEMO_PLAYLISTS if p["type"] == "playlist"]})
                return
            if not valid_spotify_id(track_id):
                track_id, status = find_track_id(str(body.get("title") or ""), str(body.get("artist") or ""))
                if not track_id:
                    error = "Could not find this song on Spotify." if status == 404 else self.spotify_error(status)
                    self.send_json({"success": False, "playlists": [], "error": error}, status=status)
                    return
            playlists, status = editable_playlists()
            if status != 200:
                self.send_json({"success": False, "playlists": [], "error": self.spotify_error(status)}, status=status)
                return
            uri = f"spotify:track:{track_id}"
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                contents = list(pool.map(
                    lambda p: playlist_track_uris(p["id"], p.get("snapshot_id")), playlists))
            for playlist, uris in zip(playlists, contents, strict=True):
                playlist.pop("snapshot_id", None)
                playlist["contains"] = None if uris is None else uri in uris
            self.send_json({"success": True, "track_id": track_id, "playlists": playlists})
            return

        if path in ("/api/playlists/add", "/api/playlists/remove"):
            adding = path == "/api/playlists/add"
            track_id = str(body.get("id") or "")
            playlist_id = str(body.get("playlist_id") or "")
            if CONFIG.get("demo_mode", False):
                if not track_id or not any(p["id"] == playlist_id and p["type"] == "playlist" for p in DEMO_PLAYLISTS):
                    self.send_json({"success": False, "error": "Choose a Spotify playlist."}, status=400)
                    return
                tracks = _demo_playlist_tracks.setdefault(playlist_id, set())
                (tracks.add if adding else tracks.discard)(track_id)
                self.send_json({"success": True, "contains": adding})
                return
            if not valid_spotify_id(track_id):
                self.send_json({"success": False, "error":
                    "The local media session has no Spotify track ID. Select a track from search first."}, status=409)
                return
            if not valid_spotify_id(playlist_id):
                self.send_json({"success": False, "error": "Choose a Spotify playlist."}, status=400)
                return
            uri = f"spotify:track:{track_id}"
            if adding:
                result, status = spotify_client.api_request(
                    f"playlists/{playlist_id}/items", method="POST", body={"uris": [uri]})
            else:
                result, status = spotify_client.api_request(
                    f"playlists/{playlist_id}/items", method="DELETE", body={"items": [{"uri": uri}]})
            success = status in (200, 201, 204)
            if success:
                remember_playlist_change(playlist_id, uri, adding, (result or {}).get("snapshot_id"))
            self.send_json({"success": success, "contains": adding if success else None,
                            "error": None if success else self.spotify_error(status)},
                           status=200 if success else status)
            return

        if path == "/api/like":
            track_id = str(body.get("id") or "")
            if not valid_spotify_id(track_id):
                self.send_json({"success": False, "error":
                    "The local media session has no Spotify track ID. Select a track from search first."}, status=409)
                return
            uri = f"spotify:track:{track_id}"
            _result, status = spotify_client.api_request(
                "me/library", method="PUT", params={"uris": uri})
            success = status in (200, 201, 204)
            self.send_json({"success": success, "error": None if success else self.spotify_error(status)},
                           status=200 if success else status)
            return

        if path == "/api/queue/add":
            uri = body.get("uri")
            if not uri:
                self.send_json({"error": "URI required"}, status=400)
                return
            if CONFIG.get("demo_mode", False):
                demo_state.queue.append({
                    "id": f"q_{time.time()}",
                    "title": body.get("title", "Queued Track"),
                    "artist": body.get("artist", "Artist"),
                    "album": "Album",
                    "duration_ms": 200000,
                    "cover_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=300&auto=format&fit=crop&q=80"
                })
                self.send_json({"success": True})
                return
            _result, status = spotify_client.api_request("me/player/queue", method="POST", params={"uri": uri})
            success = status in (200, 204)
            self.send_json({"success": success, "error": None if success else self.spotify_error(status)},
                           status=200 if success else status)
            return

        if path == "/api/open":
            uri = (body.get("uri") or "").strip()
            if not uri.startswith("spotify:"):
                self.send_json({"success": False, "error": "Only Spotify links can be opened."}, status=400)
                return
            opened, error = media.open_uri(uri)
            if opened:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": error or "Could not open that in Spotify."}, status=502)
            return

        self.send_json({"error": "Not Found"}, status=404)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

def run():
    server_address = ('0.0.0.0', PORT)
    httpd = ThreadedHTTPServer(server_address, RequestHandler)
    print("=" * 64)
    print(" 🎵 SPOTIFY TABLET STREAM DECK IS ONLINE!")
    print(f" 💻 On this PC:      http://localhost:{PORT}")
    print(f" 📱 On your Tablet:  http://{LOCAL_IP}:{PORT}")
    print("=" * 64)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    run()
