const courtLength = 44;
const courtWidth = 20;

function fmtPct(v) {
  return `${Math.round((v || 0) * 100)}%`;
}

function fmtNum(v, digits = 1) {
  return Number(v || 0).toFixed(digits);
}

function badge(call) {
  return `<span class="badge ${String(call).toLowerCase()}">${call || '--'}</span>`;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

let matchSaved = false;
let autoSaveTriggered = false;

function showToast(message) {
  const toast = document.getElementById('dashboardToast');
  if (!toast) {
    alert(message);
    return;
  }

  toast.textContent = message;
  toast.hidden = false;

  setTimeout(() => {
    toast.hidden = true;
  }, 2500);
}

async function saveCurrentMatch(redirectTarget = 'reports') {
  const res = await fetch('/api/match/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  const result = await res.json();

  if (!result.ok) {
    alert(result.message || 'Failed to save match.');
    return;
  }

  matchSaved = true;
  showToast(result.message || 'Match saved successfully.');

  const gameId = result.game_id;

  if (redirectTarget === 'reports') {
    setTimeout(() => {
      window.location.href = gameId
        ? `/player-dashboard?match_id=${gameId}&tab=reports`
        : '/player-dashboard?tab=reports';
    }, 900);
  }

  if (redirectTarget === 'setup') {
    setTimeout(() => {
      window.location.href = '/setup';
    }, 900);
  }
}

function renderScore(score) {
  if (!score) return;

  const isSingles = score.match_type === 'singles';
  const defaultScoreCall = isSingles ? '0-0' : '0-0-0';

  setText('scoreModeLabel', isSingles ? 'Singles Scoring' : 'Doubles Scoring');
  setText('scoreCall', score.score_call || defaultScoreCall);

  setText('teamALabel', isSingles ? 'Player' : 'Team A');
  setText('teamBLabel', isSingles ? 'Opponent' : 'Team B');

  setText('teamAScore', score.team_a_score ?? 0);
  setText('teamBScore', score.team_b_score ?? 0);

  setText('teamAName', score.team_a_name || (isSingles ? 'Player' : 'Team A'));
  setText('teamBName', score.team_b_name || (isSingles ? 'Opponent' : 'Team B'));

  setText('servingCardLabel', isSingles ? 'Server' : 'Serving Team');
  setText('receivingCardLabel', isSingles ? 'Receiver' : 'Receiving Team');

  setText('servingTeam', score.serving_team_name || '--');
  setText('receivingTeam', score.receiving_team_name || '--');

  setText('serverNumber', isSingles ? 'Singles' : `Server ${score.server_number ?? 0}`);
  setText('currentServer', score.current_server_name || 'Not assigned yet');

  setText('servingSide', score.started ? (score.serving_side_label || '--') : '--');

  setText(
    'serviceBox',
    score.started
      ? `${score.current_server_name || 'Server'} serving`
      : 'Press Start Game'
  );

  setText(
    'receivingSide',
    score.started
      ? (score.receiving_side_label || 'Diagonal return court')
      : 'Waiting'
  );

  setText('lastRallyWinner', score.last_rally_winner_name || 'No rally');
  setText('lastScorer', score.last_point_player || score.last_point_team_name || 'No point');
  setText('scoreMessage', score.last_action || 'Ready to start.');

  const startBtn = document.getElementById('startScore');
  if (startBtn) {
    startBtn.textContent = score.started ? 'Game Started' : 'Start Game';
    startBtn.disabled = Boolean(score.started && !score.game_over);
  }

  const servingBtn = document.getElementById('servingWon');
  const receivingBtn = document.getElementById('receivingWon');

  if (servingBtn) {
    servingBtn.textContent = isSingles ? 'Server Won Rally' : 'Serving Team Won Rally';
    servingBtn.disabled = Boolean(score.game_over);
  }

  if (receivingBtn) {
    receivingBtn.textContent = isSingles ? 'Receiver Won Rally' : 'Receiving Team Won Rally';
    receivingBtn.disabled = Boolean(score.game_over);
  }
  const saveMatchBtn = document.getElementById('saveMatch');

if (saveMatchBtn) {
  if (matchSaved) {
    saveMatchBtn.textContent = 'Match Saved';
    saveMatchBtn.disabled = true;
  } else {
    saveMatchBtn.textContent = 'Save & End Game';
    saveMatchBtn.disabled = false;
  }
}

const autoSaveBox = document.getElementById('autoSaveSession');

if (
  autoSaveBox &&
  autoSaveBox.checked &&
  score.game_over &&
  !matchSaved &&
  !autoSaveTriggered
) {
  autoSaveTriggered = true;
  saveCurrentMatch('none');
}
}




async function fetchLiveData() {
  const res = await fetch('/api/live-data');
  return await res.json();
}

async function startScore() {
  await fetch('/api/score/start', { method: 'POST' });
  await loadDashboard();
}

async function resetScore() {
  await fetch('/api/score/reset', { method: 'POST' });
  await loadDashboard();
}

async function submitRally(winner) {
  await fetch('/api/score/rally', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ winner }),
  });

  await loadDashboard();
}

async function loadDashboard() {
  try {
    const data = await fetchLiveData();

    const latest = data.latest || {};
    const m = data.metrics || {};

    const callCard = document.querySelector('.call-card');

    if (callCard) {
      callCard.classList.toggle('call-in', latest.system_call === 'IN');
      callCard.classList.toggle('call-out', latest.system_call === 'OUT');
    }

    setText('lastCall', latest.system_call || '--');
    setText('callConfidence', latest.confidence ? fmtPct(latest.confidence) : '');

    setText('bounceX', fmtNum(latest.bounce_x, 2));
    setText('bounceY', fmtNum(latest.bounce_y, 2));
    setText('latency', fmtNum(latest.latency_ms, 1));
    setText('fps', fmtNum(latest.fps, 1));
    setText('totalShots', m.total_shots ?? '--');
    setText('courtZone', latest.court_zone || 'Zone --');

    setText('avgConfidence', fmtPct(m.avg_confidence));
    setText('avgLatency', `${fmtNum(m.avg_latency_ms)} ms`);
    setText('maxLatency', `${fmtNum(m.max_latency_ms)} ms`);
    setText('cpuUsage', `${fmtNum(m.cpu_usage)}%`);
    setText('ramUsage', `${fmtNum(m.ram_usage)}%`);
    setText('accuracy', fmtPct(m.accuracy));

    setText('toggleSimulation', data.simulation ? 'Pause Simulation' : 'Resume Simulation');

    renderScore(data.score);

    drawCourt(
      data.rally_trajectory || latest.trajectory || [],
      latest.bounce_x,
      latest.bounce_y,
      latest.system_call,
      data.score
    );

    renderEventTable(data.events || []);
  } catch (error) {
    console.error('Dashboard load error:', error);
  }
}

function renderEventTable(events) {
  const tbody = document.getElementById('eventTable');
  if (!tbody) return;

  tbody.innerHTML = events.slice().reverse().map(e => `
    <tr>
      <td>${String(e.timestamp).replace('T', ' ')}</td>
      <td>${badge(e.system_call)}</td>
      <td>${badge(e.human_call)}</td>
      <td>${e.correct === null || e.correct === undefined ? '--' : (e.correct ? 'Yes' : 'No')}</td>
      <td>${fmtPct(e.confidence)}</td>
      <td>${fmtNum(e.bounce_x, 2)}, ${fmtNum(e.bounce_y, 2)}</td>
      <td>${fmtNum(e.latency_ms, 1)} ms</td>
    </tr>
  `).join('');
}

function courtMapper(canvas) {
  const ctx = canvas.getContext('2d');

  const margin = 26;
  const availableWidth = canvas.width - margin * 2;
  const availableHeight = canvas.height - margin * 2;
  const aspect = courtLength / courtWidth;

  let w = availableWidth;
  let h = w / aspect;

  if (h > availableHeight) {
    h = availableHeight;
    w = h * aspect;
  }

  const x0 = (canvas.width - w) / 2;
  const y0 = (canvas.height - h) / 2;

  const pad = 26;
  const cx = x0 + pad;
  const cy = y0 + pad;
  const cw = w - pad * 2;
  const ch = h - pad * 2;

  return {
    ctx,
    x0,
    y0,
    w,
    h,
    cx,
    cy,
    cw,
    ch,
    x: (x) => cx + (x / courtLength) * cw,
    y: (y) => cy + ch - (y / courtWidth) * ch,
  };
}

function clampPoint(point) {
  return {
    x: Math.max(0, Math.min(courtLength, Number(point.x))),
    y: Math.max(0, Math.min(courtWidth, Number(point.y))),
  };
}

function simplifyTrajectory(points, maxPoints = 55) {
  const clean = (points || [])
    .filter(p => p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y)))
    .map(clampPoint);

  if (clean.length <= maxPoints) return clean;

  const step = Math.ceil(clean.length / maxPoints);
  const sampled = clean.filter((_, i) => i % step === 0);

  const last = clean[clean.length - 1];
  const tail = sampled[sampled.length - 1];

  if (!tail || tail.x !== last.x || tail.y !== last.y) {
    sampled.push(last);
  }

  return sampled;
}

function drawLabel(ctx, text, x, y) {
  ctx.font = 'bold 13px Arial';

  const padding = 6;
  const width = ctx.measureText(text).width + padding * 2;
  const height = 24;

  ctx.fillStyle = 'rgba(255,255,255,.92)';
  ctx.fillRect(x, y - height + 6, width, height);

  ctx.strokeStyle = 'rgba(15,35,62,.20)';
  ctx.strokeRect(x, y - height + 6, width, height);

  ctx.fillStyle = '#0b1020';
  ctx.fillText(text, x + padding, y);
}

function drawMarker(ctx, m, point, label, fill, radius = 11) {
  const px = m.x(point.x);
  const py = m.y(point.y);

  ctx.beginPath();
  ctx.arc(px, py, radius, 0, Math.PI * 2);
  ctx.fillStyle = fill;
  ctx.fill();

  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 3;
  ctx.stroke();

  drawLabel(ctx, label, px + radius + 5, py + 6);
}

function drawCourtLines(m) {
  const ctx = m.ctx;

  ctx.fillStyle = '#d5b985';
  ctx.fillRect(m.x0, m.y0, m.w, m.h);

  ctx.fillStyle = '#3559a8';
  ctx.fillRect(m.cx, m.cy, m.cw, m.ch);

  ctx.fillStyle = '#4b74d9';
  ctx.fillRect(m.x(15), m.cy, m.x(22) - m.x(15), m.ch);
  ctx.fillRect(m.x(22), m.cy, m.x(29) - m.x(22), m.ch);

  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 4;
  ctx.strokeRect(m.cx, m.cy, m.cw, m.ch);

  [15, 29].forEach(x => {
    ctx.beginPath();
    ctx.moveTo(m.x(x), m.cy);
    ctx.lineTo(m.x(x), m.cy + m.ch);
    ctx.stroke();
  });

  ctx.beginPath();
  ctx.moveTo(m.x(22), m.cy);
  ctx.lineTo(m.x(22), m.cy + m.ch);
  ctx.strokeStyle = '#0b1020';
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 3;

  ctx.beginPath();
  ctx.moveTo(m.cx, m.y(10));
  ctx.lineTo(m.x(15), m.y(10));
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(m.x(29), m.y(10));
  ctx.lineTo(m.cx + m.cw, m.y(10));
  ctx.stroke();

  ctx.fillStyle = 'rgba(255,255,255,.80)';
  ctx.font = 'bold 12px Arial';
  ctx.fillText('TEAM A SIDE', m.x(2), m.y(19));
  ctx.fillText('TEAM B SIDE', m.x(35), m.y(19));
}

function drawServiceOverlay(m, score) {
  if (!score || !score.started || !score.court_markers) return;

  const markers = score.court_markers;
  const server = markers.server;
  const receiver = markers.receiver;

  if (!server || !receiver) return;

  const ctx = m.ctx;

  ctx.setLineDash([10, 8]);

  ctx.beginPath();
  ctx.moveTo(m.x(server.x), m.y(server.y));
  ctx.lineTo(m.x(receiver.x), m.y(receiver.y));
  ctx.strokeStyle = 'rgba(255,255,255,.85)';
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.setLineDash([]);

  drawMarker(ctx, m, server, `SERVER: ${server.label || ''}`, '#0f5f7a', 12);
  drawMarker(ctx, m, receiver, 'RECEIVER', '#6941c6', 11);
}

function drawCourt(trajectory, bounceX, bounceY, call, score) {
  const canvas = document.getElementById('courtCanvas');
  if (!canvas) return;

  const m = courtMapper(canvas);
  const ctx = m.ctx;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  drawCourtLines(m);
  drawServiceOverlay(m, score);

  const cleanTrajectory = simplifyTrajectory(trajectory, 55);

  if (cleanTrajectory.length) {
    for (let i = 1; i < cleanTrajectory.length; i++) {
      const prev = cleanTrajectory[i - 1];
      const p = cleanTrajectory[i];

      const alpha = Math.max(0.25, i / cleanTrajectory.length);

      ctx.beginPath();
      ctx.moveTo(m.x(prev.x), m.y(prev.y));
      ctx.lineTo(m.x(p.x), m.y(p.y));
      ctx.strokeStyle = `rgba(255, 228, 92, ${alpha})`;
      ctx.lineWidth = 3;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.stroke();
    }

    const dotStep = Math.max(1, Math.ceil(cleanTrajectory.length / 12));

    cleanTrajectory.forEach((p, i) => {
      if (i !== 0 && i !== cleanTrajectory.length - 1 && i % dotStep !== 0) return;

      ctx.beginPath();
      ctx.arc(m.x(p.x), m.y(p.y), i === 0 ? 6 : 4, 0, Math.PI * 2);
      ctx.fillStyle = i === 0 ? '#ffffff' : '#fff2a8';
      ctx.fill();

      ctx.strokeStyle = 'rgba(15,35,62,.35)';
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    const start = cleanTrajectory[0];
    drawLabel(ctx, 'START', m.x(start.x) + 10, m.y(start.y) - 8);
  }

  const rawX = Number(bounceX || 0);
  const rawY = Number(bounceY || 0);

  const clampedX = Math.max(0, Math.min(courtLength, rawX));
  const clampedY = Math.max(0, Math.min(courtWidth, rawY));

  drawMarker(
    ctx,
    m,
    { x: clampedX, y: clampedY },
    'LATEST',
    call === 'IN' ? '#12b76a' : '#f04438',
    12
  );

  if (rawX < 0 || rawX > courtLength || rawY < 0 || rawY > courtWidth) {
    drawLabel(ctx, 'OUT OF BOUNDS', m.cx + 18, m.cy + 34);
  }
}

function setupButtonEvents() {
  const startScoreBtn = document.getElementById('startScore');
  if (startScoreBtn) {
    startScoreBtn.addEventListener('click', startScore);
  }

  const resetScoreBtn = document.getElementById('resetScore');
  if (resetScoreBtn) {
    resetScoreBtn.addEventListener('click', async () => {
      const scoreCall = document.getElementById('scoreCall')?.textContent || '0-0-0';

      if (!confirm(`Reset the pickleball score from ${scoreCall}?`)) return;

      await resetScore();
    });
  }

  const servingWonBtn = document.getElementById('servingWon');
  if (servingWonBtn) {
    servingWonBtn.addEventListener('click', () => submitRally('serving'));
  }

  const receivingWonBtn = document.getElementById('receivingWon');
  if (receivingWonBtn) {
    receivingWonBtn.addEventListener('click', () => submitRally('receiving'));
  }

  const toggleSimulationBtn = document.getElementById('toggleSimulation');
  if (toggleSimulationBtn) {
    toggleSimulationBtn.addEventListener('click', async () => {
      await fetch('/api/toggle-simulation', { method: 'POST' });
      loadDashboard();
    });
  }

  const resetSessionBtn = document.getElementById('resetSession');
  if (resetSessionBtn) {
    resetSessionBtn.addEventListener('click', async () => {
      if (!confirm('Start a new empty session?')) return;

      await fetch('/api/reset-session', { method: 'POST' });
      loadDashboard();
    });
  }

  /* =========================
     SAVE MATCH BUTTON EVENTS
  ========================= */

  const saveMatchBtn = document.getElementById('saveMatch');
  const saveMatchModal = document.getElementById('saveMatchModal');
  const cancelSaveMatchBtn = document.getElementById('cancelSaveMatch');
  const saveMatchReportsBtn = document.getElementById('saveMatchReports');
  const saveMatchSetupBtn = document.getElementById('saveMatchSetup');
  const autoSaveSessionBox = document.getElementById('autoSaveSession');

  if (autoSaveSessionBox) {
    autoSaveSessionBox.checked = localStorage.getItem('picklevisionAutoSave') === 'true';

    autoSaveSessionBox.addEventListener('change', () => {
      localStorage.setItem(
        'picklevisionAutoSave',
        autoSaveSessionBox.checked ? 'true' : 'false'
      );
    });
  }

  if (saveMatchBtn && saveMatchModal) {
    saveMatchBtn.addEventListener('click', () => {
      saveMatchModal.hidden = false;
    });
  }

  if (cancelSaveMatchBtn && saveMatchModal) {
    cancelSaveMatchBtn.addEventListener('click', () => {
      saveMatchModal.hidden = true;
    });
  }

  if (saveMatchReportsBtn && saveMatchModal) {
    saveMatchReportsBtn.addEventListener('click', async () => {
      saveMatchReportsBtn.disabled = true;
      saveMatchReportsBtn.textContent = 'Saving...';

      await saveCurrentMatch('reports');

      saveMatchModal.hidden = true;
    });
  }

  if (saveMatchSetupBtn && saveMatchModal) {
    saveMatchSetupBtn.addEventListener('click', async () => {
      saveMatchSetupBtn.disabled = true;
      saveMatchSetupBtn.textContent = 'Saving...';

      await saveCurrentMatch('setup');

      saveMatchModal.hidden = true;
    });
  }

  if (saveMatchModal) {
    saveMatchModal.addEventListener('click', (event) => {
      if (event.target === saveMatchModal) {
        saveMatchModal.hidden = true;
      }
    });
  }

  /* =========================
     CONVERT SINGLES TO DOUBLES
  ========================= */

  const openConvertDoublesBtn = document.getElementById('openConvertDoubles');
  const convertDoublesPanel = document.getElementById('convertDoublesPanel');
  const cancelConvertDoublesBtn = document.getElementById('cancelConvertDoubles');
  const confirmConvertDoublesBtn = document.getElementById('confirmConvertDoubles');

  if (openConvertDoublesBtn) {
    openConvertDoublesBtn.addEventListener('click', () => {
      if (!convertDoublesPanel) {
        alert('Convert panel is missing in dashboard.html');
        return;
      }

      convertDoublesPanel.style.display = 'block';
      openConvertDoublesBtn.style.display = 'none';
    });
  }

  if (cancelConvertDoublesBtn) {
    cancelConvertDoublesBtn.addEventListener('click', () => {
      if (convertDoublesPanel) {
        convertDoublesPanel.style.display = 'none';
      }

      if (openConvertDoublesBtn) {
        openConvertDoublesBtn.style.display = 'inline-flex';
      }
    });
  }

  if (confirmConvertDoublesBtn) {
    confirmConvertDoublesBtn.addEventListener('click', async () => {
      const teammateName = document.getElementById('convertTeammateName')?.value.trim();
      const opponent2 = document.getElementById('convertOpponent2')?.value.trim();

      if (!teammateName || !opponent2) {
        alert('Please enter both teammate name and opponent 2.');
        return;
      }

      const confirmChange = confirm(
        'Convert this 1v1 match into 2v2? The score will reset because the match format will change.'
      );

      if (!confirmChange) return;

      try {
        const res = await fetch('/api/match/convert-to-doubles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            teammate_name: teammateName,
            opponent_2: opponent2,
          }),
        });

        const result = await res.json();

        if (!result.ok) {
          alert(result.message || 'Failed to convert match.');
          return;
        }

        window.location.href = '/live-dashboard';
      } catch (error) {
        console.error('Convert to doubles error:', error);
        alert('Failed to convert match. Check the browser console.');
      }
    });
  }
}

function initDashboard() {
  console.log('PickleVision dashboard.js loaded');

  setupButtonEvents();
  loadDashboard();
  setInterval(loadDashboard, 2000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDashboard);
} else {
  initDashboard();
}

