// ══════════════════════════════════════════════════════════════
// SCRAPER HEALTH
// ══════════════════════════════════════════════════════════════
let _healthDailyChart = null;

async function loadScraperHealth() {
  const days = document.getElementById('health-days')?.value || 7;
  try {
    const resp = await fetch(`/api/scraper/health?days=${days}`, { headers: _authHeader() });
    const d = await resp.json();

    document.getElementById('h-total').textContent    = d.total_processed.toLocaleString();
    document.getElementById('h-accepted').textContent = d.total_accepted.toLocaleString();
    document.getElementById('h-rejected').textContent = d.total_rejected.toLocaleString();
    document.getElementById('h-rate').textContent     = d.accept_rate + '%';

    // Daily chart
    if (_healthDailyChart) _healthDailyChart.destroy();
    const ctx = document.getElementById('chart-health-daily').getContext('2d');
    _healthDailyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: d.daily_accepted.map(r => r.date),
        datasets: [{
          label: 'Accepted',
          data: d.daily_accepted.map(r => r.count),
          backgroundColor: 'rgba(61,201,175,0.4)',
          borderColor: 'rgba(61,201,175,0.8)',
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
          y: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
        },
      },
    });

    // Per-script table
    const tbody = document.getElementById('health-script-tbody');
    tbody.innerHTML = '';
    const healthDays = document.getElementById('health-days')?.value || 7;
    d.per_script.forEach(s => {
      const rateColor = s.accept_rate >= 70 ? 'var(--green)' : s.accept_rate >= 40 ? 'var(--accent3)' : 'var(--red)';
      const lastRun = s.last_run ? s.last_run.slice(0, 10) : '—';
      const tr = document.createElement('tr');
      tr.style.cursor = 'pointer';
      tr.title = 'Click to view articles';
      tr.addEventListener('mouseenter', () => tr.style.background = 'rgba(47,129,247,0.06)');
      tr.addEventListener('mouseleave', () => tr.style.background = '');
      tr.addEventListener('click', () => openScraperArticlesModal(s.script, healthDays));
      tr.innerHTML = `
        <td style="padding:3px 6px;color:var(--text);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${s.script}">${s.script}</td>
        <td style="padding:3px 6px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px;">${s.total}</td>
        <td style="padding:3px 6px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:${rateColor}">${s.accept_rate}%</td>
        <td style="padding:3px 6px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${lastRun}</td>`;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error('Scraper health error:', e);
  }
}

// ══════════════════════════════════════════════════════════════
// MITRE ATT&CK HEATMAP
// ══════════════════════════════════════════════════════════════
const _MITRE_COLORS = [
  'transparent',
  'rgba(47,129,247,0.08)','rgba(47,129,247,0.16)','rgba(47,129,247,0.26)',
  'rgba(47,129,247,0.38)','rgba(47,129,247,0.50)','rgba(47,129,247,0.62)',
  'rgba(47,129,247,0.74)','rgba(47,129,247,0.86)','rgba(47,129,247,1.0)',
];

function _heatColor(val, max) {
  if (!val || !max) return 'transparent';
  const idx = Math.max(1, Math.ceil((val / max) * 8));
  return _MITRE_COLORS[idx] || _MITRE_COLORS[8];
}

function _heatTextColor(val, max) {
  if (!val || !max) return 'transparent';
  return (val / max) > 0.5 ? '#0D1117' : 'var(--accent)';
}

async function loadMitreHeatmap() {
  const view = document.getElementById('mitre-view').value;
  const days = document.getElementById('mitre-days').value;
  const loading = document.getElementById('mitre-loading');
  const empty = document.getElementById('mitre-empty');
  const table = document.getElementById('mitre-heatmap-table');

  loading.style.display = 'block';
  empty.style.display = 'none';
  table.innerHTML = '';

  try {
    const resp = await fetch(`/api/mitre/heatmap?view=${view}&days=${days}`, { headers: _authHeader() });
    const d = await resp.json();
    loading.style.display = 'none';

    if (!d.rows?.length || !d.ttps?.length) {
      empty.style.display = 'block';
      return;
    }

    const max = d.max_val || 1;
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    const cornerTh = document.createElement('th');
    cornerTh.textContent = view === 'ta' ? 'Threat Actor' : 'Industry';
    headerRow.appendChild(cornerTh);
    d.ttps.forEach(t => {
      const th = document.createElement('th');
      th.className = 'ttp-col';
      th.title = `${t.id} — ${t.name}`;
      th.textContent = t.id;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    d.rows.forEach((row, ri) => {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.className = 'row-label';
      td.title = row;
      td.textContent = row;
      tr.appendChild(td);
      d.matrix[ri].forEach((val, ci) => {
        const cell = document.createElement('td');
        cell.className = 'heatmap-cell';
        cell.dataset.v = val;
        cell.style.background = _heatColor(val, max);
        cell.style.color = _heatTextColor(val, max);
        cell.title = `${row} × ${d.ttps[ci].id}: ${val} articles`;
        cell.textContent = val || '';
        if (val > 0) {
          cell.style.cursor = 'pointer';
          const ttpId = d.ttps[ci].id, ttpName = d.ttps[ci].name, rowName = row;
          cell.onclick = () => openTtpDrill(ttpId, ttpName, rowName, view, parseInt(days));
        }
        tr.appendChild(cell);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
  } catch (e) {
    loading.style.display = 'none';
    console.error('MITRE heatmap error:', e);
  }
}

async function downloadNavigatorLayer() {
  const view = document.getElementById('mitre-view').value;
  const days = document.getElementById('mitre-days').value;
  const resp = await fetch(`/api/mitre/navigator-export?view=${view}&days=${days}`, { headers: _authHeader() });
  if (!resp.ok) return;
  const blob = await resp.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `cti_navigator_${view}_${days}d.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

function openNavigator() {
  const view = document.getElementById('mitre-view').value;
  const days = document.getElementById('mitre-days').value;
  const layerUrl = encodeURIComponent(
    `${window.location.origin}/api/mitre/navigator-layer?view=${view}&days=${days}`
  );
  window.open(
    `https://mitre-attack.github.io/attack-navigator/#layerURL=${layerUrl}`,
    '_blank'
  );
}

