// Live Session camera panel: shows the MJPEG stream from /video_feed and
// polls /api/camera/status for state, fps and errors.
(() => {
  const img = document.getElementById('liveFeed');
  if (!img) return;

  const pill = document.getElementById('feedStatus');
  const toggleBtn = document.getElementById('toggleFeed');
  const placeholder = document.getElementById('feedPlaceholder');
  const meta = document.getElementById('feedMeta');

  const LABELS = {
    idle: 'Camera off',
    starting: 'Starting',
    loading_model: 'Loading model',
    opening_camera: 'Opening camera',
    running: 'Live',
    stopped: 'Camera off',
    error: 'Error',
  };
  const OFF_STATES = new Set(['idle', 'stopped', 'error']);
  let running = true;

  function connectFeed() {
    img.src = `/video_feed?t=${Date.now()}`; // cache-bust forces a fresh stream
  }

  function disconnectFeed() {
    img.removeAttribute('src'); // closes the streaming HTTP connection
  }

  async function refreshStatus() {
    try {
      const res = await fetch('/api/camera/status', { cache: 'no-store' });
      if (!res.ok) return;
      const s = await res.json();

      running = !OFF_STATES.has(s.state);
      pill.textContent = LABELS[s.state] || s.state;
      toggleBtn.textContent = running ? 'Stop camera' : 'Start camera';

      const live = s.state === 'running';
      placeholder.hidden = live;
      if (s.state === 'error') {
        placeholder.textContent = `Camera error: ${s.error}`;
      } else if (!live) {
        placeholder.textContent = running ? `${LABELS[s.state]}…` : 'Camera is off. Select Start camera.';
      }

      meta.textContent = live
        ? `${s.device} | ${s.resolution} | ${Number(s.fps).toFixed(1)} fps | inference ${Number(s.inference_ms).toFixed(1)} ms` +
          (s.calibrated ? '' : ' | court not calibrated')
        : `Source: ${s.source}`;
    } catch (err) {
      console.error('Camera status error:', err);
    }
  }

  toggleBtn.addEventListener('click', async () => {
    toggleBtn.disabled = true;
    try {
      if (running) {
        disconnectFeed();
        await fetch('/api/camera/stop', { method: 'POST' });
      } else {
        await fetch('/api/camera/start', { method: 'POST' });
        connectFeed();
      }
    } finally {
      toggleBtn.disabled = false;
      refreshStatus();
    }
  });

  img.addEventListener('error', () => { placeholder.hidden = false; });
  window.addEventListener('beforeunload', disconnectFeed);

  refreshStatus();
  setInterval(refreshStatus, 1000);
})();
