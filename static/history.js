function badge(call) { return `<span class="badge ${String(call).toLowerCase()}">${call || '--'}</span>`; }
function pct(v) { return `${Math.round((v || 0) * 100)}%`; }
async function loadHistory() {
  const res = await fetch('/api/events?limit=200');
  const events = await res.json();
  const tbody = document.getElementById('historyTable');
  tbody.innerHTML = events.slice().reverse().map(e => `
    <tr>
      <td>${e.id}</td>
      <td>${String(e.timestamp).replace('T', ' ')}</td>
      <td>${badge(e.system_call)}</td>
      <td>${e.court_zone}</td>
      <td>${pct(e.confidence)}</td>
      <td>${Number(e.fps).toFixed(1)}</td>
      <td>${Number(e.latency_ms).toFixed(1)} ms</td>
    </tr>
  `).join('');
}
loadHistory();
setInterval(loadHistory, 3000);
