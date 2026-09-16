// ── INDUSTRY × GEOGRAPHY RISK MATRIX ─────────────────────────

let _riskMatrixData = null;

function _rmCellColor(score) {
  if (score <= 25) return 'rgba(26,71,42,0.85)';
  if (score <= 50) return 'rgba(122,96,0,0.85)';
  if (score <= 75) return 'rgba(122,53,0,0.85)';
  return 'rgba(107,0,0,0.85)';
}

function _rmCellTextColor(score) {
  if (score <= 25) return '#4caf7d';
  if (score <= 50) return '#ffd740';
  if (score <= 75) return '#ff8c42';
  return '#ff5252';
}

async function loadRiskMatrix() {
  const days = document.getElementById('riskmatrix-days').value;
  const compareDays = document.getElementById('riskmatrix-compare-days').value;
  const body = document.getElementById('riskmatrix-body');
  const status = document.getElementById('riskmatrix-status');

  body.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);padding:32px 0;text-align:center"><div class="loading-spinner" style="display:inline-block;margin-right:8px"></div>Computing risk matrix…</div>';
  status.textContent = '';

  try {
    const r = await fetch(`/api/intelligence/risk-matrix?days=${days}&compare_days=${compareDays}`, { headers: _authHeader() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const res = await r.json();
    _riskMatrixData = res;
    status.textContent = `Generated ${res.generated_at} — ${res.matrix.length} cells across ${res.industries.length} industries × ${res.countries.length} countries`;
    renderRiskMatrix();
  } catch (e) {
    body.innerHTML = `<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--red);padding:24px 0">Error: ${escHtml(String(e))}</div>`;
  }
}

function renderRiskMatrix() {
  const body = document.getElementById('riskmatrix-body');
  if (!_riskMatrixData) return;

  const minScore = parseInt(document.getElementById('riskmatrix-min-score').value, 10) || 0;
  const { matrix, industries, countries } = _riskMatrixData;

  const filtered = matrix.filter(r => r.risk_score >= minScore);
  if (!filtered.length) {
    body.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);padding:32px 0;text-align:center">No cells meet the minimum risk score filter.</div>';
    return;
  }

  const visIndustries = industries.filter(ind => filtered.some(r => r.industry === ind));
  const visCountries  = countries.filter(cty => filtered.some(r => r.country === cty));

  const cellMap = {};
  for (const r of filtered) cellMap[`${r.industry}||${r.country}`] = r;

  const thStyle = 'font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim);padding:5px 8px;text-align:center;white-space:nowrap;border:1px solid var(--border);background:var(--surface2)';
  const tdLabelStyle = 'font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text);padding:4px 8px;white-space:nowrap;border:1px solid var(--border);background:var(--surface2);max-width:160px;overflow:hidden;text-overflow:ellipsis';

  let html = '<table style="border-collapse:collapse;font-size:10px">';
  html += '<thead><tr>';
  html += `<th style="${thStyle}">Industry \\ Country</th>`;
  for (const cty of visCountries) {
    html += `<th style="${thStyle}" title="${escHtml(cty)}">${escHtml(cty.length > 12 ? cty.slice(0,11)+'…' : cty)}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const ind of visIndustries) {
    html += '<tr>';
    html += `<td style="${tdLabelStyle}" title="${escHtml(ind)}">${escHtml(ind)}</td>`;
    for (const cty of visCountries) {
      const cell = cellMap[`${ind}||${cty}`];
      if (cell) {
        const bg = _rmCellColor(cell.risk_score);
        const fg = _rmCellTextColor(cell.risk_score);
        const actors = cell.top_actors.length ? cell.top_actors.join(', ') : '—';
        const tip = `${escHtml(ind)} × ${escHtml(cty)}\nRisk: ${cell.risk_score} ${cell.trend}\nNow: ${cell.current_count} articles | Prev: ${cell.previous_count}\nTop actors: ${escHtml(actors)}`;
        html += `<td title="${tip}" style="background:${bg};color:${fg};font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:700;text-align:center;padding:4px 7px;border:1px solid var(--border);cursor:default;min-width:48px">${cell.risk_score}${cell.trend}</td>`;
      } else {
        html += `<td style="background:var(--surface);border:1px solid var(--border);min-width:48px"></td>`;
      }
    }
    html += '</tr>';
  }

  html += '</tbody></table>';
  body.innerHTML = html;
}
