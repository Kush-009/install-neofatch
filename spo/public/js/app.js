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
  const addToPlaylistBtn = document.getElementById('addToPlaylistBtn');
  const openQueueBtn = document.getElementById('openQueueBtn');

  // Search & Playlists
  const searchInput = document.getElementById('searchInput');
  const searchClearBtn = document.getElementById('searchClearBtn');
  const filterPills = document.querySelectorAll('.filter-pills .pill-btn');
  const playlistsListEl = document.getElementById('playlistsList');

  // Lyrics
  const lyricsContainer = document.getElementById('lyricsContainer');
  const fsLyricsContainer = document.getElementById('fsLyricsContainer');
  const lyricsExpandBtn = document.getElementById('lyricsExpandBtn');
  const fsLyricsModal = document.getElementById('fsLyricsModal');
  const closeFsLyricsBtn = document.getElementById('closeFsLyricsBtn');

  // Modals & Drawers
  const queueModal = document.getElementById('queueModal');
  const closeQueueBtn = document.getElementById('closeQueueBtn');
  const queueListEl = document.getElementById('queueList');

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
  let currentActiveTab = 'playlists';
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

  const openInSpotify = async (uri) => {
    try {
      const res = await fetch('/api/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uri }),
      });
      return await res.json();
    } catch (err) {
      return { success: false, error: 'Could not reach the deck server.' };
    }
  };

  addToPlaylistBtn.addEventListener('click', async () => {
    const track = window.spotify.playback && window.spotify.playback.item;
    if (!track || !/^[A-Za-z0-9]{22}$/.test(track.id || '')) {
      showToast('This local media session has no Spotify track ID to add.');
      return;
    }
    await openPlaylistPicker(track);
  });

  const playlistPickerModal = document.getElementById('playlistPickerModal');
  const playlistPickerList = document.getElementById('playlistPickerList');
  const playlistPickerTitle = document.getElementById('playlistPickerTitle');
  let pickerRequest = 0;

  const pickerMessage = (text) => {
    const note = document.createElement('div');
    note.className = 'search-empty';
    note.textContent = text;
    playlistPickerList.replaceChildren(note);
  };

  const setPickerButton = (button, contains) => {
    button.dataset.contains = contains ? '1' : '0';
    button.textContent = contains ? 'Remove' : 'Add';
    button.classList.toggle('is-added', contains);
  };

  const renderPickerRow = (trackId, playlist) => {
    const row = document.createElement('div');
    row.className = 'playlist-item picker-item';
    const left = document.createElement('div');
    left.className = 'playlist-item-left';
    const thumb = document.createElement('img');
    thumb.className = 'playlist-thumb';
    thumb.alt = '';
    thumb.src = playlist.cover_url || '/assets/cover-placeholder.svg';
    const meta = document.createElement('div');
    meta.className = 'playlist-meta';
    const name = document.createElement('span');
    name.className = 'playlist-name';
    name.textContent = playlist.name;
    const status = document.createElement('span');
    status.className = 'playlist-count';
    const describe = (contains) => {
      status.textContent = contains === null ? 'Could not check this playlist' : contains ? 'Already in this playlist' : 'Not in this playlist';
    };
    describe(playlist.contains);
    meta.append(name, status);
    left.append(thumb, meta);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'picker-toggle-btn';
    setPickerButton(button, playlist.contains === true);
    button.addEventListener('click', async () => {
      const removing = button.dataset.contains === '1';
      button.disabled = true;
      const result = await postApi(removing ? '/api/playlists/remove' : '/api/playlists/add',
        { id: trackId, playlist_id: playlist.id });
      button.disabled = false;
      if (!result.success) {
        showToast(result.error || (removing ? 'Could not remove track.' : 'Could not add track.'));
        return;
      }
      setPickerButton(button, !removing);
      describe(!removing);
      showToast(removing ? `Removed from ${playlist.name}` : `Added to ${playlist.name}`);
    });
    row.append(left, button);
    return row;
  };

  async function openPlaylistPicker(track) {
    const request = ++pickerRequest;
    const artist = (track.artists || []).map(a => a.name).join(', ');
    playlistPickerTitle.textContent = track.name ? `Add "${track.name}" to playlist` : 'Add to playlist';
    pickerMessage('Loading your playlists…');
    playlistPickerModal.classList.add('active');
    const data = await postApi('/api/playlists/options', { id: track.id || '', title: track.name || '', artist });
    if (request !== pickerRequest) return;
    if (!data.success) {
      pickerMessage(data.error || 'Could not load your playlists.');
      return;
    }
    if (!data.playlists.length) {
      pickerMessage('You have no playlists you can edit yet. Create one first.');
      return;
    }
    playlistPickerList.replaceChildren(...data.playlists.map(p => renderPickerRow(data.track_id, p)));
  }

  const closePlaylistPicker = () => {
    pickerRequest++;
    playlistPickerModal.classList.remove('active');
  };
  document.getElementById('closePlaylistPickerBtn').addEventListener('click', closePlaylistPicker);
  playlistPickerModal.addEventListener('click', (ev) => {
    if (ev.target === playlistPickerModal) closePlaylistPicker();
  });

  document.getElementById('navCreatePlaylist').addEventListener('click', async () => {
    const name = window.prompt('Name your new private playlist:');
    if (!name || !name.trim()) return;
    const result = await postApi('/api/playlists/create', { name: name.trim() });
    showToast(result.success ? `Created ${name.trim()}` : result.error || 'Could not create playlist.');
    if (result.success) await loadPlaylists();
  });

  document.getElementById('navRecent').addEventListener('click', () => loadLibrary('recent'));

  async function postApi(path, body) {
    try {
      const response = await fetch(path, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      });
      return await response.json();
    } catch {
      return { success: false, error: 'Could not reach the deck server.' };
    }
  }

  async function loadLibrary(kind) {
    playlistsListEl.innerHTML = '<div class="search-empty">Loading...</div>';
    try {
      const response = await fetch(`/api/library?kind=${kind}`);
      const data = await response.json();
      if (!response.ok) {
        playlistsListEl.innerHTML = `<div class="search-empty">${escapeHtml(data.error || 'Library unavailable.')}</div>`;
        return;
      }
      const items = data.items || [];
      playlistsListEl.replaceChildren();
      if (!items.length) playlistsListEl.textContent = 'No tracks found.';
      for (const track of items) {
        const row = document.createElement('button');
        row.className = 'playlist-item';
        row.textContent = `${track.name} — ${(track.artists || []).map(artist => artist.name).join(', ')}`;
        row.addEventListener('click', async () => {
          const result = await window.spotify.play({ uris: [track.uri] });
          if (!result.success) showToast(result.error || 'Could not play track.');
        });
        playlistsListEl.appendChild(row);
      }
    } catch {
      playlistsListEl.innerHTML = '<div class="search-empty">Could not reach the deck server.</div>';
    }
  }

  openQueueBtn.addEventListener('click', async () => {
    queueModal.classList.add('active');
    queueListEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">Loading Queue...</div>';
    const data = await window.spotify.getQueue();
    const queue = data.queue || [];
    if (queue.length === 0) {
      const note = `Queue — ${data.api_error || 'nothing is up next.'}`;
      queueListEl.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted)">${escapeHtml(note)}</div>`;
    } else {
      queueListEl.innerHTML = queue.map((t, i) => `
        <div class="playlist-item">
          <div class="playlist-item-left">
            <span style="font-weight:700;color:var(--text-muted);width:20px;">${i + 1}</span>
            <img class="playlist-thumb" src="${t.cover_url || (t.album && t.album.images && t.album.images[0] ? t.album.images[0].url : '/assets/cover-placeholder.svg')}" onerror="this.src='/assets/cover-placeholder.svg'" />
            <div class="playlist-meta">
              <span class="playlist-name">${escapeHtml(t.title || t.name)}</span>
              <span class="playlist-sub">${escapeHtml(t.artist || (t.artists ? t.artists.map(a => a.name).join(', ') : ''))}</span>
            </div>
          </div>
        </div>
      `).join('');
    }
  });

  closeQueueBtn.addEventListener('click', () => {
    queueModal.classList.remove('active');
  });

  // Fullscreen Lyrics
  lyricsExpandBtn.addEventListener('click', () => {
    fsLyricsModal.classList.add('active');
    lyricsManager.updateSync(window.spotify.localProgressMs, true);
  });

  closeFsLyricsBtn.addEventListener('click', () => {
    fsLyricsModal.classList.remove('active');
  });

  // Playlists and Search Rendering
  async function loadPlaylists() {
    playlistsListEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">Loading playlists...</div>';
    const data = await window.spotify.getPlaylists();
    if (data.api_error) {
      playlistsListEl.textContent = data.api_error;
      return;
    }
    const items = data.items || [];
    renderPlaylists(items);
  }

  function renderPlaylists(items) {
    if (items.length === 0) {
      const hint = window.spotify.status.api_error
        ? `${window.spotify.status.api_error} The deck still controls the Spotify app on your PC.`
        : (window.spotify.status.connected
          ? 'No playlists found'
          : 'No playlists yet — tap Connect Spotify in Settings');
      playlistsListEl.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted)">${hint}</div>`;
      return;
    }

    playlistsListEl.innerHTML = items.map(p => {
      const isLiked = p.id === 'liked' || p.type === 'liked';
      const thumb = isLiked
        ? `<div class="playlist-thumb gradient-purple"><svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg></div>`
        : `<img class="playlist-thumb" src="${p.cover_url || '/assets/cover-placeholder.svg'}" onerror="this.src='/assets/cover-placeholder.svg'" />`;

      const trackCountText = p.track_count ? `${p.track_count} songs` : 'Playlist';

      return `
        <div class="playlist-item" data-id="${p.id}" data-uri="${p.uri || ''}">
          <div class="playlist-item-left">
            ${thumb}
            <div class="playlist-meta">
              <span class="playlist-name">${escapeHtml(p.name)}</span>
              <span class="playlist-sub">${trackCountText}</span>
            </div>
          </div>
          <button class="playlist-more-btn" title="Options">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
          </button>
        </div>
      `;
    }).join('');

    // Attach click to play playlist
    playlistsListEl.querySelectorAll('.playlist-item').forEach(el => {
      el.addEventListener('click', async (e) => {
        if (e.target.closest('.playlist-more-btn')) {
          e.stopPropagation();
          showToast('Playing playlist...');
        }
        const plId = el.getAttribute('data-id');
        const uri = el.getAttribute('data-uri');

        if (uri) {
          const result = await window.spotify.play({ context_uri: uri });
          if (result && result.success === false) {
            showToast(result.error || 'Could not start that playlist.');
          } else {
            showToast(`Playing ${el.querySelector('.playlist-name').textContent}`);
          }
        } else {
          // Fetch tracks and play
          const tData = await window.spotify.getPlaylistTracks(plId);
          if (tData.items && tData.items.length > 0) {
            const result = await window.spotify.play({ context_uri: tData.items[0].uri || uri });
            if (result && result.success === false) {
              showToast(result.error || 'Could not start that playlist.');
            } else {
              showToast(`Playing ${el.querySelector('.playlist-name').textContent}`);
            }
          } else {
            showToast('That playlist has no playable tracks.');
          }
        }
      });
    });
  }

  // Filter Pills
  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentActiveTab = pill.getAttribute('data-tab');

      if (searchInput.value.trim()) {
        executeSearch(searchInput.value.trim());
      } else {
        loadPlaylists();
      }
    });
  });

  // Search Input with debounce
  let searchTimeout = null;
  searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim();
    if (q) {
      searchClearBtn.style.display = 'block';
    } else {
      searchClearBtn.style.display = 'none';
    }

    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      if (q) {
        executeSearch(q);
      } else {
        loadPlaylists();
      }
    }, 350);
  });

  searchClearBtn.addEventListener('click', () => {
    searchInput.value = '';
    searchClearBtn.style.display = 'none';
    loadPlaylists();
  });

  async function executeSearch(query) {
    playlistsListEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">Searching...</div>';
    const data = await window.spotify.search(query);

    if (data.api_error) {
      // No catalog access, so hand the query to Spotify's own search instead.
      const opened = await openInSpotify(`spotify:search:${encodeURIComponent(query)}`);
      const note = opened.success
        ? 'Spotify search opened on your PC — the Web API has no free tier for this app.'
        : `Search needs Spotify Premium. ${opened.error || ''}`.trim();
      playlistsListEl.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted)">${escapeHtml(note)}</div>`;
      return;
    }

    let items = [];
    if (currentActiveTab === 'playlists') {
      items = (data.playlists && data.playlists.items) || [];
      renderPlaylists(items.map(p => ({
        id: p.id,
        name: p.name,
        type: 'playlist',
        uri: p.uri,
        track_count: p.tracks ? p.tracks.total : '',
        cover_url: p.images && p.images[0] ? p.images[0].url : ''
      })));
    } else {
      // Songs / Artists / Albums
      items = (data.tracks && data.tracks.items) || [];
      if (items.length === 0) {
        playlistsListEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">No songs found</div>';
        return;
      }
      playlistsListEl.innerHTML = items.map(t => `
        <div class="playlist-item" data-uri="${t.uri || ''}" data-id="${t.id}">
          <div class="playlist-item-left">
            <img class="playlist-thumb" src="${t.cover_url || (t.album && t.album.images && t.album.images[0] ? t.album.images[0].url : '/assets/cover-placeholder.svg')}" onerror="this.src='/assets/cover-placeholder.svg'" />
            <div class="playlist-meta">
              <span class="playlist-name">${escapeHtml(t.name || t.title)}</span>
              <span class="playlist-sub">${escapeHtml(t.artists ? t.artists.map(a => a.name).join(', ') : (t.artist || ''))}</span>
            </div>
          </div>
          <button class="playlist-more-btn" title="Queue">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      `).join('');

      playlistsListEl.querySelectorAll('.playlist-item').forEach(el => {
        el.addEventListener('click', async (e) => {
          const uri = el.getAttribute('data-uri');
          const title = el.querySelector('.playlist-name').textContent;
          const artist = el.querySelector('.playlist-sub').textContent;

          if (e.target.closest('.playlist-more-btn')) {
            e.stopPropagation();
            const result = await window.spotify.addToQueue(uri, title, artist);
            if (result && result.success === false) {
              showToast(result.error || 'Could not add to the queue.');
            } else {
              showToast(`Added "${title}" to Queue!`);
            }
            return;
          }

          let result;
          if (uri) {
            result = await window.spotify.play({ uris: [uri] });
          } else {
            result = await window.spotify.play();
          }
          if (result && result.success === false) {
            showToast(result.error || 'Could not start playback.');
          } else {
            showToast(`Playing "${title}"`);
          }
        });
      });
    }
  }

  // Sidebar navigation actions
  document.getElementById('navSearch').addEventListener('click', () => {
    searchInput.focus();
    searchInput.select();
  });

  document.getElementById('navLibrary').addEventListener('click', () => {
    searchInput.value = '';
    searchClearBtn.style.display = 'none';
    loadPlaylists();
  });

  document.getElementById('navLiked').addEventListener('click', () => loadLibrary('liked'));

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
  await loadPlaylists();

  // Load initial track lyrics
  if (window.spotify.playback && window.spotify.playback.item) {
    loadLyricsForCurrentTrack(window.spotify.playback.item);
  }
});
