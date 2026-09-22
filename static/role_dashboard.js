function setupMatchRowClicks() {
  const rows = document.querySelectorAll('.selectable-match-row[data-href]');

  rows.forEach((row) => {
    row.addEventListener('click', (event) => {
      if (event.target.closest('a, button')) return;
      window.location.href = row.dataset.href;
    });
  });
}

function activateRoleTab(target) {
  const tabs = document.querySelectorAll('.role-tab');
  const contents = document.querySelectorAll('.role-tab-content');

  if (!target || !document.getElementById(target)) {
    target = 'matches';
  }

  tabs.forEach((item) => {
    item.classList.toggle('active', item.dataset.tab === target);
  });

  contents.forEach((content) => {
    content.classList.toggle('active', content.id === target);
  });

  if (target === 'trajectory') {
    setTimeout(drawRoleTrajectory, 80);
  }
}

function setupRoleTabs() {
  const tabs = document.querySelectorAll('.role-tab');
  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get('tab') || document.querySelector('.role-tab.active')?.dataset.tab || 'matches';

  activateRoleTab(initialTab);

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      activateRoleTab(target);

      const nextParams = new URLSearchParams(window.location.search);
      nextParams.set('tab', target);
      window.history.replaceState({}, '', `${window.location.pathname}?${nextParams.toString()}`);
    });
  });
}

function drawRoleTrajectory() {
  const canvas = document.getElementById('roleTrajectoryCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');

  let points = [];

  try {
    points = JSON.parse(canvas.dataset.trajectory || '[]');
  } catch (error) {
    points = [];
  }

  const courtLength = 44;
  const courtWidth = 20;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const margin = 28;
  const x = margin;
  const y = margin;
  const w = canvas.width - margin * 2;
  const h = canvas.height - margin * 2;

  function mapX(value) {
    return x + (Number(value || 0) / courtLength) * w;
  }

  function mapY(value) {
    return y + h - (Number(value || 0) / courtWidth) * h;
  }

  ctx.fillStyle = '#d5b985';
  ctx.fillRect(x - 14, y - 14, w + 28, h + 28);

  ctx.fillStyle = '#3559a8';
  ctx.fillRect(x, y, w, h);

  ctx.fillStyle = '#4b74d9';
  ctx.fillRect(mapX(15), y, mapX(29) - mapX(15), h);

  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 4;
  ctx.strokeRect(x, y, w, h);

  [15, 22, 29].forEach((lineX) => {
    ctx.beginPath();
    ctx.moveTo(mapX(lineX), y);
    ctx.lineTo(mapX(lineX), y + h);
    ctx.stroke();
  });

  ctx.beginPath();
  ctx.moveTo(x, mapY(10));
  ctx.lineTo(mapX(15), mapY(10));
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(mapX(29), mapY(10));
  ctx.lineTo(x + w, mapY(10));
  ctx.stroke();

  ctx.fillStyle = 'rgba(255,255,255,.85)';
  ctx.font = 'bold 13px Arial';
  ctx.fillText('TEAM A SIDE', mapX(2), mapY(19));
  ctx.fillText('TEAM B SIDE', mapX(35), mapY(19));

  if (!points.length) {
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 18px Arial';
    ctx.fillText('No trajectory data available for this view.', x + 24, y + 42);
    return;
  }

  const cleanPoints = points
    .filter((point) => point && Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y)))
    .map((point) => ({
      x: Math.max(0, Math.min(courtLength, Number(point.x))),
      y: Math.max(0, Math.min(courtWidth, Number(point.y))),
    }));

  if (!cleanPoints.length) return;

  ctx.strokeStyle = 'rgba(255, 228, 92, .9)';
  ctx.lineWidth = 4;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  ctx.beginPath();

  cleanPoints.forEach((point, index) => {
    const px = mapX(point.x);
    const py = mapY(point.y);

    if (index === 0) {
      ctx.moveTo(px, py);
    } else {
      ctx.lineTo(px, py);
    }
  });

  ctx.stroke();

  cleanPoints.forEach((point, index) => {
    const px = mapX(point.x);
    const py = mapY(point.y);

    ctx.beginPath();
    ctx.arc(px, py, index === cleanPoints.length - 1 ? 9 : 5, 0, Math.PI * 2);
    ctx.fillStyle = index === cleanPoints.length - 1 ? '#12b76a' : '#fff2a8';
    ctx.fill();

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupMatchRowClicks();
  setupRoleTabs();
  drawRoleTrajectory();
});
