const roleCourtLength = 44;
const roleCourtWidth = 20;

function initTabs() {
  const buttons = Array.from(document.querySelectorAll('.tab-button'));
  const panels = Array.from(document.querySelectorAll('.role-tab-panel'));
  buttons.forEach(button => {
    button.addEventListener('click', () => {
      const target = button.dataset.tab;
      buttons.forEach(b => b.classList.toggle('active', b === button));
      panels.forEach(panel => panel.classList.toggle('active', panel.id === target));
      drawAllRoleTrajectories();
    });
  });
}

function getJsonData(id) {
  const el = document.getElementById(id);
  if (!el) return [];
  try { return JSON.parse(el.textContent || '[]'); }
  catch { return []; }
}

function cleanRolePoints(points, maxPoints = 80) {
  const valid = (points || [])
    .filter(p => p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y)))
    .map(p => ({
      x: Math.max(0, Math.min(roleCourtLength, Number(p.x))),
      y: Math.max(0, Math.min(roleCourtWidth, Number(p.y)))
    }));
  if (valid.length <= maxPoints) return valid;
  const step = Math.ceil(valid.length / maxPoints);
  const sampled = valid.filter((_, index) => index % step === 0);
  const last = valid[valid.length - 1];
  if (!sampled.length || sampled[sampled.length - 1].x !== last.x || sampled[sampled.length - 1].y !== last.y) {
    sampled.push(last);
  }
  return sampled;
}

function roleCourtMapper(canvas) {
  const ctx = canvas.getContext('2d');
  const margin = 26;
  const availableWidth = canvas.width - margin * 2;
  const availableHeight = canvas.height - margin * 2;
  const aspect = roleCourtLength / roleCourtWidth;
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
    ctx, x0, y0, w, h, cx, cy, cw, ch,
    x: x => cx + (x / roleCourtLength) * cw,
    y: y => cy + ch - (y / roleCourtWidth) * ch,
  };
}

function drawRoleCourtLines(m) {
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
}

function drawRoleLabel(ctx, text, x, y) {
  ctx.font = 'bold 13px Arial';
  const width = ctx.measureText(text).width + 12;
  ctx.fillStyle = 'rgba(255,255,255,.92)';
  ctx.fillRect(x, y - 18, width, 22);
  ctx.strokeStyle = 'rgba(15,35,62,.20)';
  ctx.strokeRect(x, y - 18, width, 22);
  ctx.fillStyle = '#0b1020';
  ctx.fillText(text, x + 6, y);
}

function drawRoleTrajectory(canvasId, points) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const m = roleCourtMapper(canvas);
  const ctx = m.ctx;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawRoleCourtLines(m);
  const clean = cleanRolePoints(points);

  if (!clean.length) {
    drawRoleLabel(ctx, 'NO TRAJECTORY DATA YET', m.cx + 20, m.cy + 35);
    return;
  }

  for (let i = 1; i < clean.length; i++) {
    const prev = clean[i - 1];
    const p = clean[i];
    const alpha = Math.max(0.25, i / clean.length);
    ctx.beginPath();
    ctx.moveTo(m.x(prev.x), m.y(prev.y));
    ctx.lineTo(m.x(p.x), m.y(p.y));
    ctx.strokeStyle = `rgba(255, 228, 92, ${alpha})`;
    ctx.lineWidth = 3;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
  }

  const start = clean[0];
  const latest = clean[clean.length - 1];
  ctx.beginPath();
  ctx.arc(m.x(start.x), m.y(start.y), 7, 0, Math.PI * 2);
  ctx.fillStyle = '#ffffff';
  ctx.fill();
  ctx.strokeStyle = '#0b1020';
  ctx.lineWidth = 2;
  ctx.stroke();
  drawRoleLabel(ctx, 'START', m.x(start.x) + 10, m.y(start.y) - 8);

  ctx.beginPath();
  ctx.arc(m.x(latest.x), m.y(latest.y), 11, 0, Math.PI * 2);
  ctx.fillStyle = '#12b76a';
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 3;
  ctx.stroke();
  drawRoleLabel(ctx, 'LATEST', m.x(latest.x) + 14, m.y(latest.y) + 5);
}

function drawAllRoleTrajectories() {
  drawRoleTrajectory('playerTrajectoryCanvas', getJsonData('playerTrajectoryData'));
  drawRoleTrajectory('coachTrajectoryCanvas', getJsonData('coachTrajectoryData'));
}

initTabs();
drawAllRoleTrajectories();
