# 🎵 Spotify Tablet Stream Deck

Transform any tablet (iPad, Android, Fire HD, Surface) into a dedicated **Stream Deck controller** for your PC's Spotify!

Designed faithfully after the clean modular dashboard design with full touch controls, real-time synchronized lyrics, volume scrubbing, playlist & search browsing, and screen wake lock.

---

## ⚡ Quick Start

### 1. Launch the Server on your PC
Double-click **`start.bat`** (or right-click `start.ps1` -> *Run with PowerShell*).

This will:
- Detect Python on your PC.
- Start the lightweight local server on port `5000`.
- Automatically open `http://localhost:5000` in your PC browser.

### 2. Connect from your Tablet
Make sure your tablet is connected to the same Wi-Fi network as your PC, then open your tablet's browser (Safari, Chrome, etc.) and go to:

👉 **`http://192.168.31.197:5000`**

*(If your PC's local IP changes, the terminal window and the in-app Settings modal always show your updated IP address!)*

---

## 🌟 Features Included

1. **Now Playing Card**:
   - High-res album art with smooth animations.
   - Song title, artists, and live duration.
   - Interactive scrub bar with elapsed and remaining timestamps.
   - **Shuffle**, **Previous**, **Big Play/Pause**, **Next**, and **Repeat** buttons.

2. **Playlists & Search Card**:
   - Instant search bar (`Search songs, artists, or playlists...`).
   - Category filter pills: `Playlists`, `Songs`, `Artists`, `Albums`.
   - Scrollable list with **Liked Songs**, custom playlists, or search results.
   - 1-tap to play any song or playlist, plus a `...` button to add to queue.

3. **Volume & Quick Controls Card**:
   - Real-time Volume slider with numeric percentage badge (`70%`).
   - **Shuffle** quick action with an iOS-style interactive green toggle switch!
   - **Add to Playlist** quick button.
   - **Queue** button to open the live upcoming queue drawer.

4. **Synchronized Lyrics Card**:
   - Auto-scrolling, word/line-synchronized lyrics powered by **LRCLIB**!
   - Current line is bolded and highlighted; clicking any lyric line jumps playback straight to that part of the song!
   - **Expand Button**: Tap to open full-screen lyrics mode on your tablet.

5. **Tablet Stream Deck Optimizations**:
   - ☀️ / 🌙 **Dark & Light Mode**: Default clean light theme matching the mockup, with a dark OLED theme toggle.
   - 💡 **Screen Wake Lock**: Tap the sun icon in the top bar to keep your tablet screen awake while gaming or working.
   - ⛶ **Fullscreen Mode**: Tap the fullscreen icon to hide browser tabs and turn your tablet into a hardware deck.
   - 🕹️ **Simulation / Demo Mode**: Pre-loaded with demo tracks, playlists, and synced lyrics so you can test immediately without any setup.

---

## 🔗 Connecting to Real Spotify (Optional)

The app works right out of the box in **Simulation Mode**. To control your actual PC Spotify app:

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in with your Spotify account.
2. Click **Create app**:
   - **App name**: `Tablet Stream Deck`
   - **Redirect URI**: Add `http://192.168.31.197:5000/callback` and `http://localhost:5000/callback`
   - **APIs used**: Check *Web API*
3. Copy your **Client ID** and **Client Secret**.
4. In the Tablet Stream Deck web page, tap **Settings** in the bottom left sidebar:
   - Paste your **Client ID** and **Client Secret**.
   - Click **Save Settings**, then click **Connect Spotify**.
   - Authorize the app once, and you're good to go!

### No Spotify Premium?

The deck reads playback and sends supported transport commands to the desktop
client through Windows SMTC or Linux MPRIS, without depending on the Web API.
Windows shuffle and repeat are available only when Spotify exposes those controls.

Library, playlist and queue requests use Spotify's Web API and report access
errors. Development-mode app owners require Premium; this is separate from the
listener's subscription and OAuth permissions. There is no local media-session
API for reading Spotify's queue or modifying its playlists.

- Keep `smtc_helper.ps1` next to `server.py` on Windows.
- Reconnect Spotify after updating to grant playlist modification permissions.
- A native session without a Spotify track ID cannot save or add that track to a
  playlist; the deck reports this instead of guessing a matching recording.
- Native position smoothing cannot recover elapsed playback before the deck
  connected if the player supplies neither a current position nor a timestamp.
- Restart the server and reload the browser after updating.
