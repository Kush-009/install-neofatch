/**
 * Spotify API Client and State Manager
 */

class SpotifyService {
  constructor() {
    this.status = {
      connected: false,
      demo_mode: false,
      premium: false,
      native_control: false,
      backend: 'none',
      player_available: false,
      api_error: null,
      local_ip: '127.0.0.1',
      port: 5000,
      client_id: '',
      redirect_uri: ''
    };

    this.playback = null;
    this.pollInterval = null;
    this.timerInterval = null;
    this.listeners = [];
    this.lastFetchedAt = 0;
    this.localProgressMs = 0;
    this.anchorProgressMs = 0;
    this.isPlaying = false;
    this.currentTrackId = null;
  }

  onUpdate(callback) {
    this.listeners.push(callback);
  }

  notify() {
    for (const cb of this.listeners) {
      cb({
        playback: this.playback,
        progressMs: this.localProgressMs,
        status: this.status
      });
    }
  }

  async init() {
    await this.fetchStatus();
    await this.fetchPlayback();

    // Start background poll every 1.5 seconds
    this.pollInterval = setInterval(() => this.fetchPlayback(), 1500);

    // High frequency smooth progress ticker every 100ms
    this.timerInterval = setInterval(() => {
      if (this.isPlaying && this.playback && this.playback.item) {
        const duration = this.playback.item.duration_ms || 1;
        // Anchor to the last server reading so a throttled tab or a slow
        // poll cannot make the clock drift away from the Spotify client.
        this.localProgressMs = Math.min(this.anchorProgressMs + (Date.now() - this.lastFetchedAt), duration);
        this.notify();
      }
    }, 100);
  }

  async fetchStatus() {
    try {
      const res = await fetch('/api/status');
      this.status = await res.json();
      return this.status;
    } catch (err) {
      console.error('[Spotify] fetchStatus error:', err);
    }
  }

  async fetchPlayback() {
    const requestId = this.playbackRequestId = (this.playbackRequestId || 0) + 1;
    try {
      const res = await fetch('/api/playback');
      if (!res.ok) return;
      const data = await res.json();
      if (requestId !== this.playbackRequestId || !data || Object.keys(data).length === 0) return;

      const duration = (data.item && data.item.duration_ms) || 0;
      this.playback = data;
      this.isPlaying = Boolean(data.is_playing);
      this.anchorProgressMs = data.progress_ms || 0;
      this.lastFetchedAt = Date.now();
      this.localProgressMs = duration ? Math.min(this.anchorProgressMs, duration) : this.anchorProgressMs;

      const trackKey = data.item ? `${data.item.id}|${data.item.name}|${(data.item.artists || []).map(a => a.name).join('|')}|${duration}` : null;
      const trackChanged = trackKey !== this.currentTrackKey;
      this.currentTrackKey = trackKey;
      this.currentTrackId = data.item ? data.item.id : null;
      this.notify();

      if (trackChanged) {
        window.dispatchEvent(new CustomEvent('trackchange', { detail: data.item || null }));
      }
    } catch (err) {
      console.warn('[Spotify] fetchPlayback error:', err);
    }
  }

  async play(params = {}) {
    try {
      const res = await fetch('/api/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      const data = await res.json().catch(() => ({}));
      setTimeout(() => this.fetchPlayback(), 400);
      return data;
    } catch (err) {
      console.error(err);
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async pause() {
    try {
      const res = await fetch('/api/pause', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      setTimeout(() => this.fetchPlayback(), 400);
      return data;
    } catch (err) {
      console.error(err);
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async togglePlay() {
    if (this.isPlaying) {
      return this.pause();
    }
    return this.play();
  }

  async next() {
    try {
      const res = await fetch('/api/next', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      setTimeout(() => this.fetchPlayback(), 400);
      return data;
    } catch (err) {
      console.error(err);
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async previous() {
    try {
      const res = await fetch('/api/previous', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      setTimeout(() => this.fetchPlayback(), 400);
      return data;
    } catch (err) {
      console.error(err);
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async seek(positionMs) {
    this.playbackRequestId = (this.playbackRequestId || 0) + 1;
    try {
      const res = await fetch('/api/seek', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_ms: positionMs })
      });
      const result = await res.json();
      await this.fetchPlayback();
      return result;
    } catch (err) {
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async setVolume(volumePercent) {
    if (this.playback && this.playback.device) {
      this.playback.device.volume_percent = volumePercent;
    }
    this.notify();
    try {
      await fetch('/api/volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume_percent: volumePercent })
      });
    } catch (err) {
      console.error(err);
    }
  }

  async setShuffle(state) {
    try {
      const res = await fetch('/api/shuffle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state })
      });
      const data = await res.json().catch(() => ({}));
      if (data.success) {
        if (this.playback) this.playback.shuffle_state = state;
        this.notify();
      }
      return data;
    } catch (err) {
      console.error(err);
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async setRepeat(state) {
    try {
      const res = await fetch('/api/repeat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state })
      });
      const data = await res.json().catch(() => ({}));
      if (data.success) {
        if (this.playback) this.playback.repeat_state = state;
        this.notify();
      }
      return data;
    } catch (err) {
      console.error(err);
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async getPlaylists() {
    try {
      const res = await fetch('/api/playlists');
      return await res.json();
    } catch (err) {
      return { items: [] };
    }
  }

  async getPlaylistTracks(playlistId) {
    try {
      const res = await fetch(`/api/playlist/tracks?id=${encodeURIComponent(playlistId)}`);
      return await res.json();
    } catch (err) {
      return { items: [] };
    }
  }

  async search(query, type = 'track,playlist,artist,album') {
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&type=${encodeURIComponent(type)}`);
      return await res.json();
    } catch (err) {
      return { tracks: { items: [] }, playlists: { items: [] } };
    }
  }

  async getLyrics(title, artist, durationMs = 0) {
    try {
      const res = await fetch(`/api/lyrics?title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}&duration=${durationMs}`);
      return await res.json();
    } catch (err) {
      return { syncedLyrics: null, plainLyrics: "Unable to load lyrics." };
    }
  }

  async getQueue() {
    try {
      const res = await fetch('/api/queue');
      return await res.json();
    } catch (err) {
      return { queue: [] };
    }
  }

  async addToQueue(uri, title, artist) {
    try {
      const res = await fetch('/api/queue/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uri, title, artist })
      });
      return await res.json();
    } catch (err) {
      return { success: false };
    }
  }

  async likeCurrentTrack() {
    const item = this.playback && this.playback.item;
    try {
      const res = await fetch('/api/like', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: item ? item.id : '', title: item ? item.name : '' })
      });
      return await res.json();
    } catch (err) {
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async saveConfig(cfg) {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg)
    });
    return await res.json();
  }

  async logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    await this.fetchStatus();
    await this.fetchPlayback();
  }

  async getAuthUrl() {
    const res = await fetch('/api/auth/url');
    return await res.json();
  }
}

window.spotify = new SpotifyService();
