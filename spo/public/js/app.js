/**
 * Main Tablet Stream Deck Application Controller
 */

document.addEventListener('DOMContentLoaded', async () => {
  // DOM Elements
  const albumArtEl = document.getElementById('albumArt');
  const trackTitleEl = document.getElementById('trackTitle');
  const trackArtistEl = document.getElementById('trackArtist');
  const progressFillEl = document.getElementById('progressFill');
  const progressBgEl = document.getElementById('progressBarBg');
  const progressThumbEl = document.getElementById('progressThumb');
  const timeElapsedEl = document.getElementById('timeElapsed');
  const timeTotalEl = document.getElementById('timeTotal');

  const playPauseBtn = document.getElementById('playPauseBtn');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const shuffleBtn = document.getElementById('shuffleBtn');
  const repeatBtn = document.getElementById('repeatBtn');

  // Volume
  const volumeSliderFill = document.getElementById('volumeSliderFill');
  const volumeSliderThumb = document.getElementById('volumeSliderThumb');
  const volumeSliderContainer = document.getElementById('volumeSliderContainer');
  const volumePercentLabel = document.getElementById('volumePercentLabel');
  const shuffleSwitch = document.getElementById('shuffleSwitch');

  // Lyrics
  const lyricsContainer = document.getElementById('lyricsContainer');
  const fsLyricsContainer = document.getElementById('fsLyricsContainer');
  const lyricsExpandBtn = document.getElementById('lyricsExpandBtn');
  const fsLyricsModal = document.getElementById('fsLyricsModal');
  const closeFsLyricsBtn = document.getElementById('closeFsLyricsBtn');

  // Modals & Drawers
  const settingsModal = document.getElementById('settingsModal');
  const openSettingsBtn = document.getElementById('openSettingsBtn');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  const connectSpotifyBtn = document.getElementById('connectSpotifyBtn');
  const toggleDemoModeBtn = document.getElementById('toggleDemoModeBtn');
  const clientIdInput = document.getElementById('clientIdInput');
  const clientSecretInput = document.getElementById('clientSecretInput');
  const redirectUriInput = document.getElementById('redirectUriInput');
  const tabletUrlDisplay = document.getElementById('tabletUrlDisplay');

  // Header status
  const connectionStatusDot = document.getElementById('connectionStatusDot');
  const connectionStatusText = document.getElementById('connectionStatusText');
  const fullscreenToggleBtn = document.getElementById('fullscreenToggleBtn');
  const wakeLockToggleBtn = document.getElementById('wakeLockToggleBtn');
  const themeToggleBtn = document.getElementById('themeToggleBtn');

  // State
  let isSeeking = false;
  let isAdjustingVolume = false;
  let wakeLockSentinel = null;
  let lastLyricsTrackKey = '';

  // Initialize Lyrics Manager
  const lyricsManager = new LyricsManager(
    lyricsContainer,
    fsLyricsContainer,
    async (seekMs) => reportAction(await window.spotify.seek(seekMs), 'Could not seek in Spotify.')
  );

  // Time format utility (ms -> mm:ss)
  function formatTime(ms) {
    if (!ms || isNaN(ms)) return '0:00';
    const totalSecs = Math.floor(ms / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  }

  // Toast helper
  function showToast(msg) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  // Update playback UI
  function updatePlaybackUI(data) {
    const { playback, progressMs, status } = data;

    // Status pill
    if (status) {
      if (status.demo_mode) {
        connectionStatusDot.className = 'status-dot demo';
        connectionStatusText.textContent = 'Demo Mode (Simulation)';
      } else if (status.connected) {
        connectionStatusDot.className = 'status-dot';
        connectionStatusText.textContent = status.premium ? 'Spotify Premium' : 'Spotify Free · local control';
      } else if (status.native_control) {
        connectionStatusDot.className = status.player_available ? 'status-dot' : 'status-dot demo';
        connectionStatusText.textContent = status.player_available
          ? 'Spotify Free · local control'
          : 'Spotify closed · open the app on your PC';
      } else {
        connectionStatusDot.className = 'status-dot demo';
        connectionStatusText.textContent = 'Not connected';
      }
    }

    if (!playback || !playback.item) {
      // Idle state
      trackTitleEl.textContent = 'Ready to Play';
      trackArtistEl.textContent = 'Open Spotify on your PC or tap Demo';
      playPauseBtn.innerHTML = getPlaySvg();
      timeElapsedEl.textContent = '0:00';
      timeTotalEl.textContent = '0:00';
      progressFillEl.style.width = '0%';
      return;
    }

    const item = playback.item;
    const duration = item.duration_ms || 1;

    // Title & Artist
    trackTitleEl.textContent = item.name || 'Unknown Track';
    const artistNames = item.artists ? item.artists.map(a => a.name).join(', ') : (item.artist || 'Unknown Artist');
    trackArtistEl.textContent = artistNames;

    // Album Art
    let imgUrl = '/assets/cover-placeholder.svg';
    if (item.album && item.album.images && item.album.images.length > 0) {
      imgUrl = item.album.images[0].url;
    } else if (item.cover_url) {
      imgUrl = item.cover_url;
    }
    if (albumArtEl.src !== imgUrl && !albumArtEl.src.endsWith(imgUrl)) {
      albumArtEl.src = imgUrl;
    }

    // Play/Pause button
    if (playback.is_playing) {
      playPauseBtn.innerHTML = getPauseSvg();
    } else {
      playPauseBtn.innerHTML = getPlaySvg();
    }

    // Progress
    if (!isSeeking) {
      const currentMs = Math.min(progressMs, duration);
      const pct = Math.max(0, Math.min(100, (currentMs / duration) * 100));
      progressFillEl.style.width = `${pct}%`;
      progressThumbEl.style.left = `${pct}%`;
      timeElapsedEl.textContent = formatTime(currentMs);
      timeTotalEl.textContent = formatTime(duration);

      // Sync Lyrics
      lyricsManager.updateSync(currentMs);
    }

    // Shuffle & Repeat states
    if (playback.shuffle_state) {
      shuffleBtn.classList.add('active');
      shuffleSwitch.checked = true;
    } else {
      shuffleBtn.classList.remove('active');
      shuffleSwitch.checked = false;
    }

    if (playback.repeat_state && playback.repeat_state !== 'off') {
      repeatBtn.classList.add('active');
    } else {
      repeatBtn.classList.remove('active');
    }

    // Shuffle/repeat only exist in the Web API (Premium) or on Linux (MPRIS)
    const canShuffle = !status || status.premium || status.backend === 'mpris';
    shuffleBtn.classList.toggle('unavailable', !canShuffle);
    repeatBtn.classList.toggle('unavailable', !canShuffle);
    shuffleBtn.title = canShuffle ? 'Shuffle' : 'Shuffle needs Premium (or Linux)';
    repeatBtn.title = canShuffle ? 'Repeat' : 'Repeat needs Premium (or Linux)';

    // Volume
    if (!isAdjustingVolume && playback.device && playback.device.volume_percent !== undefined) {
      const vol = playback.device.volume_percent;
      volumePercentLabel.textContent = `${vol}%`;
      volumeSliderFill.style.width = `${vol}%`;
      volumeSliderThumb.style.left = `${vol}%`;
    }
  }

  // Fetch lyrics when track changes
  async function loadLyricsForCurrentTrack(item) {
    if (!item) {
      lastLyricsTrackKey = '';
      lyricsManager.loadLyrics('', '');
      return;
    }
    const artist = item.artists ? item.artists.map(a => a.name).join(' ') : (item.artist || '');
    const title = item.name || '';
    const key = `${item.id}|${title}|${artist}|${item.duration_ms}`;
    if (key === lastLyricsTrackKey) return;
    lastLyricsTrackKey = key;
    lyricsManager.loadLyrics('', 'Loading lyrics...');
    const lyricsData = await window.spotify.getLyrics(title, artist, item.duration_ms);
    if (lastLyricsTrackKey !== key) return;
    lyricsManager.loadLyrics(lyricsData.syncedLyrics, lyricsData.plainLyrics);
    lyricsManager.updateSync(window.spotify.localProgressMs);
  }

  window.addEventListener('trackchange', (e) => {
    loadLyricsForCurrentTrack(e.detail);
  });

  // Playback Controls Listeners
  const reportAction = (result, fallback) => {
    if (result && result.success === false) {
      showToast(result.error || fallback);
    } else if (result && result.message) {
      showToast(result.message);
    }
  };

  playPauseBtn.addEventListener('click', async () => {
    reportAction(await window.spotify.togglePlay(), 'Could not play or pause Spotify.');
  });
  prevBtn.addEventListener('click', async () => {
    reportAction(await window.spotify.previous(), 'Could not skip back.');
  });
  nextBtn.addEventListener('click', async () => {
    reportAction(await window.spotify.next(), 'Could not skip forward.');
  });

  shuffleBtn.addEventListener('click', async () => {
    const isShuffle = shuffleBtn.classList.contains('active');
    reportAction(await window.spotify.setShuffle(!isShuffle), 'Could not change shuffle.');
  });

  shuffleSwitch.addEventListener('change', async () => {
    const wanted = shuffleSwitch.checked;
    const result = await window.spotify.setShuffle(wanted);
    if (result && result.success === false) {
      shuffleSwitch.checked = !wanted;
      showToast(result.error || 'Could not change shuffle.');
    }
  });

  repeatBtn.addEventListener('click', async () => {
    const cur = window.spotify.playback ? window.spotify.playback.repeat_state : 'off';
    const nextState = cur === 'off' ? 'context' : (cur === 'context' ? 'track' : 'off');
    reportAction(await window.spotify.setRepeat(nextState), 'Could not change repeat.');
  });

  // Progress Bar Scrubbing
  progressBgEl.addEventListener('pointerdown', (e) => {
    isSeeking = true;
    let seekMs = 0;
    const duration = window.spotify.playback?.item?.duration_ms || 0;
    const updateTarget = (clientX) => {
      const rect = progressBgEl.getBoundingClientRect();
      const pos = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      seekMs = Math.floor(pos * duration);
      progressFillEl.style.width = `${pos * 100}%`;
    };
    updateTarget(e.clientX);
    const onPointerMove = (ev) => updateTarget(ev.clientX);
    const cleanup = () => {
      isSeeking = false;
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', cleanup);
    };
    const onPointerUp = async (ev) => {
      updateTarget(ev.clientX);
      cleanup();
      if (duration > 0) reportAction(await window.spotify.seek(seekMs), 'Could not seek in Spotify.');
    };
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', cleanup);
  });

  // Volume Slider Scrubbing (Zero-lag, buttery smooth touch & mouse)
  let volThrottleTimer = null;
  let lastVolSent = -1;

  function setVolumeFromClientX(clientX, isFinal = false) {
    const rect = volumeSliderContainer.getBoundingClientRect();
    const pos = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const vol = Math.round(pos * 100);

    // Instant 0ms visual update on tablet
    volumePercentLabel.textContent = `${vol}%`;
    volumeSliderFill.style.width = `${vol}%`;
    volumeSliderThumb.style.left = `${vol}%`;

    if (isFinal) {
      clearTimeout(volThrottleTimer);
      volThrottleTimer = null;
      if (vol !== lastVolSent) {
        lastVolSent = vol;
        window.spotify.setVolume(vol);
      }
    } else {
      if (!volThrottleTimer) {
        volThrottleTimer = setTimeout(() => {
          volThrottleTimer = null;
          if (vol !== lastVolSent) {
            lastVolSent = vol;
            window.spotify.setVolume(vol);
          }
        }, 40);
      }
    }
  }

  volumeSliderContainer.addEventListener('pointerdown', (e) => {
    isAdjustingVolume = true;
    setVolumeFromClientX(e.clientX, false);
    const onPointerMove = (ev) => {
      setVolumeFromClientX(ev.clientX, false);
    };
    const onPointerUp = (ev) => {
      isAdjustingVolume = false;
      setVolumeFromClientX(ev.clientX, true);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  });

  // Fullscreen Lyrics
  lyricsExpandBtn.addEventListener('click', () => {
    fsLyricsModal.classList.add('active');
    lyricsManager.updateSync(window.spotify.localProgressMs, true);
  });

  closeFsLyricsBtn.addEventListener('click', () => {
    fsLyricsModal.classList.remove('active');
  });

  // Settings Modal & Spotify Connect Setup
  openSettingsBtn.addEventListener('click', async () => {
    const st = await window.spotify.fetchStatus();
    if (st) {
      clientIdInput.value = st.client_id || '';
      redirectUriInput.value = st.redirect_uri || `http://${st.local_ip}:${st.port}/callback`;
      tabletUrlDisplay.textContent = `http://${st.local_ip}:${st.port}`;
    }
    settingsModal.classList.add('active');
  });

  closeSettingsBtn.addEventListener('click', () => {
    settingsModal.classList.remove('active');
  });

  saveSettingsBtn.addEventListener('click', async () => {
    const res = await window.spotify.saveConfig({
      client_id: clientIdInput.value.trim(),
      client_secret: clientSecretInput.value.trim(),
      redirect_uri: redirectUriInput.value.trim()
    });
    if (res.success) {
      showToast('Settings saved successfully!');
    }
  });

  connectSpotifyBtn.addEventListener('click', async () => {
    // Save first
    await window.spotify.saveConfig({
      client_id: clientIdInput.value.trim(),
      client_secret: clientSecretInput.value.trim(),
      redirect_uri: redirectUriInput.value.trim()
    });

    const authRes = await window.spotify.getAuthUrl();
    if (authRes.url) {
      window.location.href = authRes.url;
    } else {
      alert(authRes.error || 'Please enter your Spotify Client ID and Client Secret.');
    }
  });

  toggleDemoModeBtn.addEventListener('click', async () => {
    const st = window.spotify.status;
    const newDemoState = !st.demo_mode;
    await window.spotify.saveConfig({ demo_mode: newDemoState });
    window.location.reload();
  });

  // Tablet Fullscreen Toggle
  fullscreenToggleBtn.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => {
        console.warn('Fullscreen request failed:', err);
      });
      fullscreenToggleBtn.title = 'Exit Fullscreen';
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
      fullscreenToggleBtn.title = 'Enter Fullscreen';
    }
  });

  // Screen Wake Lock API (keeps tablet awake while music is playing)
  wakeLockToggleBtn.addEventListener('click', async () => {
    if (!wakeLockSentinel && 'wakeLock' in navigator) {
      try {
        wakeLockSentinel = await navigator.wakeLock.request('screen');
        wakeLockToggleBtn.style.color = 'var(--spotify-green)';
        showToast('Screen Wake Lock: Active (Tablet won\'t sleep)');
        wakeLockSentinel.addEventListener('release', () => {
          wakeLockSentinel = null;
          wakeLockToggleBtn.style.color = '';
        });
      } catch (err) {
        showToast('Wake Lock error: ' + err.message);
      }
    } else if (wakeLockSentinel) {
      wakeLockSentinel.release();
      wakeLockSentinel = null;
      wakeLockToggleBtn.style.color = '';
      showToast('Screen Wake Lock: Released');
    } else {
      showToast('Wake Lock not supported on this browser');
    }
  });

  // Theme Toggle (Light / Dark)
  themeToggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    }
  });

  if (localStorage.getItem('theme') === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  // SVG Helper Icons
  function getPlaySvg() {
    return `<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>`;
  }

  function getPauseSvg() {
    return `<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1.5"></rect><rect x="14" y="4" width="4" height="16" rx="1.5"></rect></svg>`;
  }

  // Check URL params for auth success/error
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('auth') === 'success') {
    showToast('🎉 Connected to Spotify successfully!');
    history.replaceState(null, '', window.location.pathname);
  } else if (urlParams.get('auth') === 'error') {
    showToast('Spotify auth error: ' + (urlParams.get('msg') || ''));
  }

  // Initialize service
  window.spotify.onUpdate(updatePlaybackUI);
  await window.spotify.init();

  // Load initial track lyrics
  if (window.spotify.playback && window.spotify.playback.item) {
    loadLyricsForCurrentTrack(window.spotify.playback.item);
  }
});
