function pct(v) { return `${Math.round((v || 0) * 100)}%`; }
function num(v, d = 1) { return Number(v || 0).toFixed(d); }

async function loadReports() {
  const res = await fetch('/api/reports');
  const data = await res.json();
  const m = data.metrics;
  document.getElementById('rAccuracy').textContent = pct(m.accuracy);
  document.getElementById('rPrecision').textContent = pct(m.precision);
  document.getElementById('rRecall').textContent = pct(m.recall);
  document.getElementById('rF1').textContent = pct(m.f1_score);
  document.getElementById('rMae').textContent = `${num(m.mae_mm)} mm`;
  document.getElementById('rFps').textContent = num(m.avg_fps);
  document.getElementById('tp').textContent = m.tp;
  document.getElementById('tn').textContent = m.tn;
  document.getElementById('fp').textContent = m.fp;
  document.getElementById('fn').textContent = m.fn;
  drawHeatmap(data.events || []);
}

function drawHeatmap(events) {
  const canvas = document.getElementById('heatmapCanvas');
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const pad = 32;
  const w = canvas.width - pad * 2;
  const h = canvas.height - pad * 2;
  const x = v => pad + Math.max(0, Math.min(44, v)) / 44 * w;
  const y = v => pad + h - Math.max(0, Math.min(20, v)) / 20 * h;

  ctx.fillStyle = '#3559a8';
  ctx.fillRect(pad, pad, w, h);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 3;
  ctx.strokeRect(pad, pad, w, h);
  [15, 22, 29].forEach(v => { ctx.beginPath(); ctx.moveTo(x(v), pad); ctx.lineTo(x(v), pad + h); ctx.stroke(); });
  ctx.beginPath(); ctx.moveTo(pad, y(10)); ctx.lineTo(x(15), y(10)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x(29), y(10)); ctx.lineTo(pad + w, y(10)); ctx.stroke();

  events.forEach(e => {
    ctx.beginPath();
    const radius = e.system_call === 'IN' ? 10 : 7;
    ctx.arc(x(e.bounce_x), y(e.bounce_y), radius, 0, Math.PI * 2);
    ctx.fillStyle = e.system_call === 'IN' ? 'rgba(18,183,106,.55)' : 'rgba(240,68,56,.65)';
    ctx.fill();
  });
}

loadReports();
