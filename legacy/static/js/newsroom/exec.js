// ══════════════════════════════════════════════════════════════
// EXECUTIVE DASHBOARD
// ══════════════════════════════════════════════════════════════

const _PALETTE = [
  'rgba(47,129,247,.7)','rgba(88,166,255,.7)','rgba(61,201,175,.7)',
  'rgba(218,54,51,.7)','rgba(227,179,65,.7)','rgba(138,43,226,.7)',
  'rgba(0,191,255,.7)','rgba(255,215,0,.7)',
];

function _execTrend(current, prev) {
  if (!prev) return '';
  const delta = current - prev;
  const pct   = Math.abs(Math.round((delta / prev) * 100));
  // for security metrics: up = more incidents/actors = bad (red), down = good (green)
  const color = delta > 0 ? 'var(--red)' : delta < 0 ? 'var(--green)' : 'var(--text-dim)';
  const arrow = delta > 0 ? '↑' : delta < 0 ? '↓' : '→';
  return `<span style="color:${color}">${arrow}${pct}% vs prev period</span>`;
}

function drillToNewsroomTA(taName) {
  const tabBtn = document.querySelector('.tab[onclick*="\'newsroom\'"]');
  if (tabBtn) switchTab('newsroom', tabBtn);
  const sel = document.getElementById('filter-actor');
  const opt = sel ? Array.from(sel.options).find(o => o.value.toLowerCase() === taName.toLowerCase()) : null;
  if (opt) sel.value = opt.value;
  loadAllPanels();
}


// ══════════════════════════════════════════════════════════════
// EXEC DASHBOARD V2
// ══════════════════════════════════════════════════════════════
let _execSectorChartV2 = null, _execCountryChartV2 = null, _execTypeChartV2 = null;
let _execNewstypeTrendChart = null, _execVictimCountryChart = null;
let _execSrSpreadChart = null;
let _execDataV2 = null;
let _execRolePreview = localStorage.getItem('exec_role_preview') || null;

function execSwitchRolePreview(role) {
  _execRolePreview = role || null;
  if (_execRolePreview) {
    localStorage.setItem('exec_role_preview', _execRolePreview);
  } else {
    localStorage.removeItem('exec_role_preview');
  }
  loadExecDashboard();
}

function _execApplyViewConfig(vc) {
  if (!vc || !vc.sections) return;
  const sections = vc.sections;
  document.querySelectorAll('[data-section]').forEach(el => {
    const key = el.dataset.section;
    if (key in sections) {
      el.style.display = sections[key] ? '' : 'none';
    }
  });
  const badge = document.getElementById('exec-role-badge');
  if (badge) {
    badge.textContent = `View: ${(vc.role || 'analyst').toUpperCase()}`;
    badge.style.display = '';
  }
}

async function loadExecDashboard() {
  const days          = document.getElementById('exec-days').value;
  const incidentOnly  = document.getElementById('exec-incident-only')?.checked ?? true;
  const confirmedOnly = document.getElementById('exec-confirmed-only')?.checked ?? false;
  let url = `/api/exec/dashboard-v2?days=${days}&incident_only=${incidentOnly}&confirmed_only=${confirmedOnly}`;
  if (_execRolePreview) url += `&role=${encodeURIComponent(_execRolePreview)}`;

  // Show admin role switcher if user is admin
  const roleSwitcher = document.getElementById('exec-role-switcher');
  const userRole = typeof _jwtRole === 'function' ? _jwtRole() : '';
  if (roleSwitcher && ['admin', 'superadmin'].includes(userRole)) {
    roleSwitcher.style.display = '';
    if (_execRolePreview) roleSwitcher.value = _execRolePreview;
  }

  try {
    const resp = await fetch(url, { headers: _authAndClientHeaders() });
    const d = await resp.json();
    _execDataV2 = d;

    _execApplyViewConfig(d.view_config);

    // ── KPIs ──
    document.getElementById('exec-kpi-total').textContent    = d.total_incidents.toLocaleString();
    document.getElementById('exec-kpi-sectors').textContent  = d.active_sectors ?? d.top_sectors.length;
    document.getElementById('exec-kpi-tas').textContent      = d.unique_ta_count ?? d.ta_leaderboard.length;
    const critCves = d.cve_exposure_v2.reduce((s, r) => s + r.critical, 0);
    document.getElementById('exec-kpi-cve-crit').textContent = critCves;

    document.getElementById('exec-kpi-total-trend').innerHTML   = _execTrend(d.total_incidents, d.prev_total);
    document.getElementById('exec-kpi-sectors-trend').innerHTML = _execTrend(d.active_sectors ?? d.top_sectors.length, d.prev_active_sectors);
    document.getElementById('exec-kpi-tas-trend').innerHTML     = _execTrend(d.unique_ta_count ?? d.ta_leaderboard.length, d.prev_unique_ta);

    // T1-1 + T3: Highest Risk Sector KPI + formula tooltip
    const topRisk = d.sector_risk_scores?.[0];
    document.getElementById('exec-kpi-top-risk').textContent       = topRisk ? toTitleCase(topRisk.sector) : '—';
    document.getElementById('exec-kpi-top-risk-score').textContent = topRisk ? `Risk Score: ${topRisk.risk_score}/100` : '';
    const riskKpiCard = document.getElementById('exec-kpi-top-risk').closest('.exec-kpi');
    if (riskKpiCard) riskKpiCard.title = 'Risk Score Formula:\n• Volume  (0-50): last_month / max_sector_last_month × 50\n• Trend   (0-20): 2nd-half avg / 1st-half avg increase × 20 (0 if declining)\n• Spike   (0-30): z-score × 10, capped at 30\n  z-score = (last_month − avg_prev_months) / stdev_prev_months';

    // T1-2: Spike count KPI
    const spikeCount = (d.industry_spikes || []).length;
    document.getElementById('exec-kpi-spike-count').textContent = spikeCount;

    // T3-15: Confirmed Incident Rate KPI
    const confRate = d.confirmed_incident_rate;
    document.getElementById('exec-kpi-confirmed-rate').textContent = (confRate !== null && confRate !== undefined) ? `${confRate}%` : 'N/A';
    document.getElementById('exec-kpi-confirmed-rate-sub').textContent = (confRate !== null && confRate !== undefined) ? 'verified by GPT-4o' : 'field not yet populated';

    // T1-2: Spike Alert Banner
    const bannerEl = document.getElementById('exec-spike-banner');
    if (spikeCount > 0) {
      const spikesHtml = (d.industry_spikes || []).map(sp => `
        <div style="display:flex;align-items:center;gap:10px;padding:7px 12px;background:rgba(88,166,255,0.07);border:1px solid rgba(88,166,255,0.25);border-radius:3px;flex-shrink:0;">
          <span style="color:var(--accent3);font-size:16px;line-height:1">⚡</span>
          <div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent3);text-transform:uppercase;">${toTitleCase(sp.entity)}</div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);">z=${sp.z_score} · ${sp.count} incidents · ${sp.date}</div>
          </div>
          <span style="font-size:9px;padding:1px 6px;border-radius:2px;background:${sp.severity==='high'?'rgba(218,54,51,0.2)':'rgba(88,166,255,0.2)'};color:${sp.severity==='high'?'var(--red)':'var(--accent3)'};">${sp.severity.toUpperCase()}</span>
        </div>`).join('');
      bannerEl.style.display = 'block';
      bannerEl.innerHTML = `
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;">⚡ Anomaly Alerts — Sectors with statistically significant activity spikes</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">${spikesHtml}</div>`;
    } else {
      bannerEl.style.display = 'none';
    }

    // T1-1 + T3-14: Sector Risk Matrix with peer benchmark
    const matrixEl = document.getElementById('exec-sector-risk-matrix');
    matrixEl.innerHTML = '';
    // Compute sector totals for peer benchmark
    const sectorTotalsMap = {};
    (d.sector_trend || []).forEach(s => { sectorTotalsMap[s.sector] = s.data.reduce((a, b) => a + b, 0); });
    const allSectorTotals = Object.values(sectorTotalsMap);
    const grandTotal = allSectorTotals.reduce((a, b) => a + b, 0) || 1;
    const avgSectorPct = allSectorTotals.length > 0 ? (100 / allSectorTotals.length) : 0;
    const riskFormulaTitle = 'Risk Score = Volume(0-50) + Trend(0-20) + Spike(0-30)\n• Volume: (last_month / max_sector) × 50\n• Trend: increase first→second half, max 20\n• Spike: z-score × 10, capped at 30';
    (d.sector_risk_scores || []).forEach(sr => {
      const score = sr.risk_score;
      const color = score >= 70 ? 'var(--red)' : score >= 40 ? 'var(--accent3)' : 'var(--green)';
      const label = score >= 70 ? 'HIGH' : score >= 40 ? 'MED' : 'LOW';
      // T3-14: peer benchmark
      const sectorTotal = sectorTotalsMap[sr.sector] || 0;
      const sectorPct   = (sectorTotal / grandTotal) * 100;
      const diffVsAvg   = sectorPct - avgSectorPct;
      const benchColor  = diffVsAvg > 5 ? 'var(--red)' : diffVsAvg > 0 ? 'var(--accent3)' : 'var(--text-dim)';
      const benchText   = `${diffVsAvg >= 0 ? '+' : ''}${diffVsAvg.toFixed(1)}% vs avg`;
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:10px;';
      row.title = riskFormulaTitle;
      row.innerHTML = `
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text);min-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${toTitleCase(sr.sector)}</div>
        <div style="flex:1;height:6px;background:var(--surface2);border-radius:3px;overflow:hidden;">
          <div style="height:100%;width:${score}%;background:${color};border-radius:3px;transition:width .4s;"></div>
        </div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${color};min-width:28px;text-align:right;">${score}</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:${color}22;color:${color};min-width:32px;text-align:center;">${label}</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:${benchColor};min-width:64px;text-align:right;" title="Peer Benchmark: share of total incidents vs avg sector share">${benchText}</div>`;
      matrixEl.appendChild(row);
    });

    // T1-3 + T3-15: TA Leaderboard with NEW badge + confidence indicator
    const prevTaSet = new Set((d.prev_ta_names || []).map(n => n.toLowerCase()));
    const taConf = d.ta_confidence || {};
    const lbEl = document.getElementById('exec-ta-leaderboard');
    lbEl.innerHTML = '';
    const maxTa = d.ta_leaderboard[0]?.count || 1;
    d.ta_leaderboard.forEach(ta => {
      const isNew = !prevTaSet.has(ta.name.toLowerCase());
      const conf = taConf[ta.name] ?? taConf[ta.name.toLowerCase()] ?? null;
      const confColor = conf === null ? 'var(--text-dim)' : conf >= 80 ? 'var(--green)' : conf >= 50 ? 'var(--accent3)' : 'var(--red)';
      const confLabel = conf === null ? '?' : `${conf}%`;
      const row = document.createElement('div');
      row.className = 'ta-leader-row';
      row.style.cursor = 'pointer';
      row.title = `${toTitleCase(ta.name)} — Click to view in News Room\nSignal Quality: ${conf !== null ? conf + '% of mentions are incident-type articles' : 'unknown'}`;
      row.onclick = () => drillToNewsroomTA(ta.name);
      const pct = Math.round((ta.count / maxTa) * 100);
      const newBadge = isNew
        ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:rgba(61,201,175,0.2);color:var(--green);margin-left:4px;white-space:nowrap;">NEW</span>`
        : `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:rgba(139,148,158,0.2);color:var(--text-dim);margin-left:4px;white-space:nowrap;">REC</span>`;
      const confBadge = `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:${confColor}22;color:${confColor};margin-left:auto;flex-shrink:0;" title="Signal quality: % of articles classified as incident type">${confLabel}</span>`;
      row.innerHTML = `
        <span class="ta-leader-name" title="${ta.name}" style="display:flex;align-items:center;flex:1;min-width:0;">${toTitleCase(ta.name)}${newBadge}</span>
        <div class="ta-leader-bar" style="flex:1;margin:0 8px;"><div class="ta-leader-fill" style="width:${pct}%"></div></div>
        <span class="ta-leader-count">${ta.count}</span>
        ${confBadge}`;
      lbEl.appendChild(row);
    });

    // ── Sector trend chart ──
    if (_execSectorChartV2) _execSectorChartV2.destroy();
    const sCtx = document.getElementById('exec-chart-sector').getContext('2d');
    _execSectorChartV2 = new Chart(sCtx, {
      type: 'line',
      data: {
        labels: d.months,
        datasets: d.sector_trend.map((s, i) => ({
          label: toTitleCase(s.sector),
          data: s.data,
          borderColor: _PALETTE[i % _PALETTE.length],
          backgroundColor: _PALETTE[i % _PALETTE.length].replace('.7)', '.1)'),
          tension: 0.3, fill: false, pointRadius: 3,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#8B949E', font: { size: 10 } } } },
        scales: {
          x: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
          y: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
        },
      },
    });

    // ── Country trend chart ──
    if (_execCountryChartV2) _execCountryChartV2.destroy();
    const cCtx = document.getElementById('exec-chart-country').getContext('2d');
    _execCountryChartV2 = new Chart(cCtx, {
      type: 'line',
      data: {
        labels: d.months,
        datasets: d.country_trend.map((c, i) => ({
          label: toTitleCase(c.country),
          data: c.data,
          borderColor: _PALETTE[i % _PALETTE.length],
          backgroundColor: _PALETTE[i % _PALETTE.length].replace('.7)', '.1)'),
          tension: 0.3, fill: false, pointRadius: 3,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#8B949E', font: { size: 10 } } } },
        scales: {
          x: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
          y: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
        },
      },
    });

    // T1-4: Enhanced CVE table (CVSS + PoC)
    const tbody = document.querySelector('#exec-cve-table tbody');
    tbody.innerHTML = '';
    if (!d.cve_exposure_v2.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:10px;padding:10px;">No CVE data</td></tr>';
    }
    d.cve_exposure_v2.forEach(r => {
      const tr = document.createElement('tr');
      const cvssColor = r.max_cvss >= 9 ? 'var(--red)' : r.max_cvss >= 7 ? 'var(--orange)' : r.max_cvss >= 4 ? 'var(--accent3)' : 'var(--text-dim)';
      const pocCell = r.poc_count > 0
        ? `<span style="color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:10px;" title="${r.poc_count} CVE(s) with public PoC">⚠ ${r.poc_count}</span>`
        : `<span style="color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:10px;">—</span>`;
      tr.innerHTML = `
        <td>${r.tech}</td>
        <td>${r.total}</td>
        <td style="color:var(--red)">${r.critical || 0}</td>
        <td style="color:var(--orange)">${r.high || 0}</td>
        <td style="color:var(--accent3)">${r.medium || 0}</td>
        <td style="color:${cvssColor};font-family:'IBM Plex Mono',monospace;">${r.max_cvss > 0 ? r.max_cvss.toFixed(1) : '—'}</td>
        <td>${pocCell}</td>`;
      tbody.appendChild(tr);
    });

    // ── Incident type donut ──
    if (_execTypeChartV2) _execTypeChartV2.destroy();
    if (d.news_type_breakdown?.length) {
      const ntCtx = document.getElementById('exec-chart-newstype').getContext('2d');
      _execTypeChartV2 = new Chart(ntCtx, {
        type: 'doughnut',
        data: {
          labels: d.news_type_breakdown.map(x => x.name),
          datasets: [{ data: d.news_type_breakdown.map(x => x.count), backgroundColor: _PALETTE.slice(0, d.news_type_breakdown.length), borderWidth: 0 }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { position: 'right', labels: { color: '#8B949E', font: { size: 10 }, boxWidth: 12 } },
          },
          cutout: '60%',
        },
      });
    }

    // ── Sector heatmap + T3-12 drill-down on click ──
    const hmTable = document.getElementById('exec-sector-heatmap');
    hmTable.innerHTML = '';
    if (d.sector_heatmap?.length) {
      const hmax = d.heatmap_max || 1;
      const hdr = document.createElement('tr');
      hdr.innerHTML = '<th></th>' + d.months.map(m => `<th>${m.slice(5)}</th>`).join('');
      hmTable.appendChild(hdr);
      d.sector_heatmap.forEach(row => {
        const tr = document.createElement('tr');
        const cells = row.months.map(cell => {
          const intensity = hmax > 0 ? cell.count / hmax : 0;
          const bg = `rgba(47,129,247,${(intensity * 0.7 + 0.05).toFixed(2)})`;
          const color = intensity > 0.5 ? '#000' : 'var(--text)';
          const cursor = cell.count > 0 ? 'cursor:pointer;' : '';
          const td = `<td class="heatmap-cell" style="background:${bg};color:${color};${cursor}" title="${toTitleCase(row.sector)} · ${cell.month}: ${cell.count}${cell.count > 0 ? ' — click to view articles' : ''}" data-sector="${row.sector}" data-month="${cell.month}">${cell.count || ''}</td>`;
          return td;
        }).join('');
        tr.innerHTML = `<td class="heatmap-label">${toTitleCase(row.sector)}</td>${cells}`;
        // Attach click handlers after innerHTML is set
        tr.querySelectorAll('td[data-sector]').forEach(td => {
          if (parseInt(td.textContent) > 0) {
            td.addEventListener('click', () => openExecDrill(td.dataset.sector, td.dataset.month));
          }
        });
        hmTable.appendChild(tr);
      });
    }

    // ════════════════════════════════════════════════════
    // TIER 2 RENDERS
    // ════════════════════════════════════════════════════

    // T2-10: Incident type stacked bar (monthly trend)
    if (_execNewstypeTrendChart) _execNewstypeTrendChart.destroy();
    if (d.newstype_trend?.series?.length) {
      const ntCtx2 = document.getElementById('exec-chart-newstype-trend').getContext('2d');
      _execNewstypeTrendChart = new Chart(ntCtx2, {
        type: 'bar',
        data: {
          labels: d.newstype_trend.months,
          datasets: d.newstype_trend.series.map((s, i) => ({
            label: toTitleCase(s.type),
            data: s.data,
            backgroundColor: _PALETTE[i % _PALETTE.length].replace('.7)', '.6)'),
            borderWidth: 0,
          })),
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { labels: { color: '#8B949E', font: { size: 10 } } } },
          scales: {
            x: { stacked: true, ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
            y: { stacked: true, ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
          },
        },
      });
    }

    // T2-7: Top TTPs
    const ttpEl = document.getElementById('exec-ttp-list');
    ttpEl.innerHTML = '';
    if (d.top_ttps?.length) {
      const maxTtp = d.top_ttps[0]?.count || 1;
      d.top_ttps.forEach(t => {
        const pct = Math.round((t.count / maxTtp) * 100);
        const el = document.createElement('div');
        el.style.cssText = 'display:flex;align-items:center;gap:8px;';
        el.innerHTML = `
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--accent);min-width:70px;white-space:nowrap;" title="${t.id}">${t.id}</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${t.name}">${t.name}</div>
          <div style="width:80px;height:5px;background:var(--surface2);border-radius:2px;flex-shrink:0;">
            <div style="height:100%;width:${pct}%;background:rgba(47,129,247,0.5);border-radius:2px;"></div>
          </div>
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);min-width:24px;text-align:right;">${t.count}</span>`;
        ttpEl.appendChild(el);
      });
    } else {
      ttpEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim);padding:8px 0;">No TTP data for this period</div>';
    }

    // T2-8: TA Velocity
    const velEl = document.getElementById('exec-ta-velocity');
    velEl.innerHTML = '';
    if (d.ta_velocity?.length) {
      d.ta_velocity.forEach(ta => {
        const isRising = ta.velocity_pct > 0;
        const isNew    = ta.avg_prev === 0;
        const color = isNew ? 'var(--green)' : isRising ? 'var(--red)' : 'var(--text-dim)';
        const arrow = isNew ? '★' : isRising ? '▲' : '▼';
        const label = isNew ? 'NEW' : `${isRising ? '+' : ''}${ta.velocity_pct}%`;
        const el = document.createElement('div');
        el.style.cssText = 'display:flex;align-items:center;gap:10px;';
        el.innerHTML = `
          <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text);min-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${ta.actor}">${toTitleCase(ta.actor)}</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${color};min-width:48px;">${arrow} ${label}</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);">last: ${ta.last_month} · avg: ${ta.avg_prev}</div>`;
        velEl.appendChild(el);
      });
    } else {
      velEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim);padding:8px 0;">No TA data</div>';
    }

    // T2-6: Victim country trend
    if (_execVictimCountryChart) _execVictimCountryChart.destroy();
    if (d.victim_country_trend?.length) {
      const vcCtx = document.getElementById('exec-chart-victim-country').getContext('2d');
      _execVictimCountryChart = new Chart(vcCtx, {
        type: 'line',
        data: {
          labels: d.months,
          datasets: d.victim_country_trend.map((c, i) => ({
            label: toTitleCase(c.country),
            data: c.data,
            borderColor: _PALETTE[i % _PALETTE.length],
            backgroundColor: _PALETTE[i % _PALETTE.length].replace('.7)', '.1)'),
            tension: 0.3, fill: false, pointRadius: 3,
          })),
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { labels: { color: '#8B949E', font: { size: 10 } } } },
          scales: {
            x: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
            y: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' } },
          },
        },
      });
    } else {
      const vcCanvas = document.getElementById('exec-chart-victim-country');
      const vcCtx2 = vcCanvas.getContext('2d');
      vcCtx2.fillStyle = '#8B949E';
      vcCtx2.font = "11px 'IBM Plex Mono'";
      vcCtx2.fillText('No victim_countries data in this period', 20, 50);
    }

    // T2-11: Sector × Actor matrix
    const saTable = document.getElementById('exec-sector-actor-matrix');
    saTable.innerHTML = '';
    if (d.sector_actor_matrix?.sectors?.length) {
      const sam = d.sector_actor_matrix;
      const maxSam = sam.max_val || 1;
      const hdr = document.createElement('tr');
      hdr.innerHTML = '<th style="max-width:100px;"></th>' +
        sam.actors.map(a => `<th style="font-size:9px;max-width:60px;white-space:normal;word-break:break-word;" title="${a}">${toTitleCase(a).split(' ').slice(0,2).join(' ')}</th>`).join('');
      saTable.appendChild(hdr);
      sam.sectors.forEach((sector, si) => {
        const tr = document.createElement('tr');
        const cells = sam.matrix[si].map(count => {
          const intensity = count / maxSam;
          const bg = count > 0 ? `rgba(218,54,51,${(intensity * 0.7 + 0.05).toFixed(2)})` : 'transparent';
          const color = intensity > 0.5 ? '#fff' : 'var(--text)';
          return `<td class="heatmap-cell" style="background:${bg};color:${color};font-size:9px;" title="${toTitleCase(sector)} × ${toTitleCase(sam.actors[sam.matrix[si].indexOf(count)])}: ${count}">${count || ''}</td>`;
        }).join('');
        tr.innerHTML = `<td class="heatmap-label" style="font-size:9px;max-width:100px;white-space:normal;">${toTitleCase(sector)}</td>${cells}`;
        saTable.appendChild(tr);
      });
    }

    // T2-9: Sector co-occurrence (supply chain signal)
    const coEl = document.getElementById('exec-sector-cooccur');
    coEl.innerHTML = '';
    if (d.sector_cooccurrence?.length) {
      const maxCo = d.sector_cooccurrence[0]?.count || 1;
      d.sector_cooccurrence.forEach(co => {
        const pct = Math.round((co.count / maxCo) * 100);
        const el = document.createElement('div');
        el.style.cssText = 'display:flex;align-items:center;gap:8px;';
        el.innerHTML = `
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${toTitleCase(co.sector_a)} ↔ ${toTitleCase(co.sector_b)}">${toTitleCase(co.sector_a)} <span style="color:var(--accent3)">↔</span> ${toTitleCase(co.sector_b)}</div>
          <div style="width:60px;height:5px;background:var(--surface2);border-radius:2px;flex-shrink:0;">
            <div style="height:100%;width:${pct}%;background:rgba(88,166,255,0.5);border-radius:2px;"></div>
          </div>
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);min-width:20px;text-align:right;">${co.count}</span>`;
        coEl.appendChild(el);
      });
    } else {
      coEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim);">No co-targeting data</div>';
    }

    // Enable export button
    document.getElementById('exec-export-csv').disabled = false;

    // ── Role-specific sections ──

    // Source Reliability Spread
    if (d.source_reliability_spread && Object.keys(d.source_reliability_spread).length) {
      if (_execSrSpreadChart) _execSrSpreadChart.destroy();
      const srCtx = document.getElementById('exec-chart-sr-spread');
      if (srCtx) {
        const grades = Object.keys(d.source_reliability_spread).sort();
        const gradeColors = { A: 'rgba(61,201,175,.7)', B: 'rgba(47,129,247,.7)', C: 'rgba(88,166,255,.7)', D: 'rgba(227,179,65,.7)', E: 'rgba(218,54,51,.7)', F: 'rgba(138,43,226,.7)' };
        _execSrSpreadChart = new Chart(srCtx.getContext('2d'), {
          type: 'doughnut',
          data: {
            labels: grades.map(g => `${g} – ${d.source_reliability_spread[g]}`),
            datasets: [{ data: grades.map(g => d.source_reliability_spread[g]), backgroundColor: grades.map(g => gradeColors[g] || 'rgba(139,148,158,.7)'), borderWidth: 0 }],
          },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#8B949E', font: { size: 10 }, boxWidth: 12 } } }, cutout: '55%' },
        });
      }
    }

    // Cluster List
    const clusterEl = document.getElementById('exec-cluster-list');
    if (clusterEl) {
      if (!d.recent_clusters_summary?.length) {
        clusterEl.innerHTML = '<div style="color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:10px;padding:12px 0;">No data yet — feature pending.</div>';
      } else {
        clusterEl.innerHTML = `<table class="cve-exposure-table"><thead><tr><th>Summary</th><th>Size</th><th>Actors</th><th>Last Seen</th></tr></thead><tbody>${
          d.recent_clusters_summary.map(c => `<tr>
            <td style="color:var(--accent);cursor:pointer" onclick="switchTab('intelligence',null)">${esc(c.summary_title||'—')}</td>
            <td>${c.size||'—'}</td>
            <td style="color:var(--text-dim);font-size:9px">${esc((c.threat_actors||[]).slice(0,3).join(', '))||'—'}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:9px">${esc(c.last_seen||'—')}</td>
          </tr>`).join('')
        }</tbody></table>`;
      }
    }

    // FP Feedback Queue
    const fpEl = document.getElementById('exec-fp-queue');
    if (fpEl) {
      if (!d.pending_fp_queue?.length) {
        fpEl.innerHTML = '<div style="color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:10px;padding:12px 0;">No data yet — feature pending.</div>';
      } else {
        fpEl.innerHTML = `<table class="cve-exposure-table"><thead><tr><th>IOC</th><th>Type</th><th>Last Seen</th><th>Confidence</th><th></th></tr></thead><tbody>${
          d.pending_fp_queue.map(ioc => {
            const conf = ioc.confidence_score || 0;
            const confColor = conf >= 70 ? 'var(--accent3)' : conf >= 50 ? 'var(--text)' : 'var(--red)';
            return `<tr>
              <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">${esc(ioc.value||'—')}</td>
              <td><span class="ta-source-badge">${esc(ioc.type||'—')}</span></td>
              <td style="font-size:9px;color:var(--text-dim)">${esc(ioc.last_seen||'—')}</td>
              <td style="color:${confColor};font-family:'IBM Plex Mono',monospace;font-size:10px">${conf}%</td>
              <td style="white-space:nowrap">
                <button class="ta-watch-btn" style="font-size:9px;padding:2px 6px" onclick="execFpVote('${esc(ioc.type)}','${esc(ioc.value)}',true)" title="Mark as true positive">👍</button>
                <button class="ta-delete-btn" style="font-size:9px;padding:2px 6px;margin-left:4px" onclick="execFpVote('${esc(ioc.type)}','${esc(ioc.value)}',false)" title="Mark as false positive">👎</button>
              </td>
            </tr>`;
          }).join('')
        }</tbody></table>`;
      }
    }

    // Critical CVE Feed
    const critCveEl = document.getElementById('exec-critical-cve');
    if (critCveEl) {
      if (!d.critical_cves?.length) {
        critCveEl.innerHTML = '<div style="color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:10px;padding:12px 0;">No data yet — feature pending.</div>';
      } else {
        critCveEl.innerHTML = `<table class="cve-exposure-table"><thead><tr><th>CVE</th><th>Tech</th><th>EPSS%</th><th>CVSS</th><th>KEV</th><th>First Seen</th></tr></thead><tbody>${
          d.critical_cves.map(c => {
            const epss = c.epss_score != null ? `${(c.epss_score * 100).toFixed(1)}%` : '—';
            const cvss = c.cve_score != null ? c.cve_score.toFixed(1) : '—';
            const cvssColor = (c.cve_score || 0) >= 9 ? 'var(--red)' : (c.cve_score || 0) >= 7 ? 'var(--orange)' : 'var(--accent3)';
            const kev = c.cisa_kev ? '<span style="color:var(--red);font-size:9px">KEV</span>' : '—';
            return `<tr>
              <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent3);cursor:pointer" onclick="openCveModal && openCveModal('${esc(c.cve_id)}')">${esc(c.cve_id||'—')}</td>
              <td>${esc(c.tech||'—')}</td>
              <td style="color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:10px">${epss}</td>
              <td style="color:${cvssColor};font-family:'IBM Plex Mono',monospace;font-size:10px">${cvss}</td>
              <td>${kev}</td>
              <td style="font-size:9px;color:var(--text-dim)">${esc(c.first_seen||'—')}</td>
            </tr>`;
          }).join('')
        }</tbody></table>`;
      }
    }

  } catch (e) {
    console.error('Exec idea dashboard error:', e);
  }
}

async function execFpVote(iocType, iocValue, isTP) {
  try {
    await fetch('/api/iocs/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ..._authAndClientHeaders() },
      body: JSON.stringify({ ioc_type: iocType, value: iocValue, is_true_positive: isTP }),
    });
    loadExecDashboard();
  } catch (e) { console.error('FP vote error:', e); }
}

// ══════════════════════════════════════════════════════════════
// TIER 3 FUNCTIONS
// ══════════════════════════════════════════════════════════════

// T3-12: Heatmap drill-down
function _execMonthEnd(yyyymm) {
  const [y, m] = yyyymm.split('-').map(Number);
  return new Date(y, m, 0).toISOString().slice(0, 10);
}

async function openExecDrill(sector, month) {
  const overlay = document.getElementById('exec-drill-overlay');
  const body    = document.getElementById('exec-drill-body');
  const title   = document.getElementById('exec-drill-title');
  const subtitle = document.getElementById('exec-drill-subtitle');
  const countEl = document.getElementById('exec-drill-count');

  title.textContent    = toTitleCase(sector);
  subtitle.textContent = `${month} — loading…`;
  body.innerHTML       = '<div style="padding:20px;font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim);">Loading articles…</div>';
  countEl.textContent  = '';
  overlay.classList.add('open');

  try {
    const start = `${month}-01`;
    const end   = _execMonthEnd(month);
    const url   = `/api/articles?industry=${encodeURIComponent(sector)}&posted_on_start=${start}&posted_on_end=${end}&page_size=20`;
    const resp  = await fetch(url);
    const data  = await resp.json();
    const arts  = data.articles || [];
    const total = data.total || arts.length;

    subtitle.textContent = `${month} · ${total} article${total !== 1 ? 's' : ''}`;
    countEl.textContent  = `Showing ${arts.length} of ${total}`;

    if (!arts.length) {
      body.innerHTML = '<div style="padding:20px;font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim);">No articles found.</div>';
      return;
    }

    body.innerHTML = arts.map(a => `
      <div style="padding:12px 20px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:4px;">
        <a href="${a.url}" target="_blank" rel="noopener" style="font-family:'Rajdhani',sans-serif;font-size:13px;font-weight:600;color:var(--text-bright);text-decoration:none;line-height:1.3;">${a.title}</a>
        <div style="display:flex;gap:10px;flex-wrap:wrap;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);">
          <span>${a.posted_on || ''}</span>
          <span>${a.source || ''}</span>
          ${a.news_type ? `<span style="color:var(--accent)">${a.news_type}</span>` : ''}
          ${(a.threat_actors || []).length ? `<span style="color:var(--accent3)">${a.threat_actors.slice(0,3).map(t => toTitleCase(t)).join(', ')}</span>` : ''}
        </div>
      </div>`).join('');
  } catch (e) {
    body.innerHTML = `<div style="padding:20px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--red);">Error: ${e.message}</div>`;
  }
}

function closeExecDrill() {
  document.getElementById('exec-drill-overlay').classList.remove('open');
}

// T3-13: Watchlist (saved view) using localStorage
const _EXEC_WL_KEY = 'cti_exec_idea_watchlist_v1';

function saveExecWatchlist() {
  const prefs = {
    days: document.getElementById('exec-days').value,
    incidentOnly: document.getElementById('exec-incident-only')?.checked ?? true,
    confirmedOnly: document.getElementById('exec-confirmed-only')?.checked ?? false,
    savedAt: new Date().toISOString(),
  };
  localStorage.setItem(_EXEC_WL_KEY, JSON.stringify(prefs));
  _updateWatchlistButtons(true, prefs.savedAt);
}

function clearExecWatchlist() {
  localStorage.removeItem(_EXEC_WL_KEY);
  _updateWatchlistButtons(false);
}

function _updateWatchlistButtons(hasSaved, savedAt) {
  const saveBtn  = document.getElementById('exec-save-watchlist');
  const clearBtn = document.getElementById('exec-clear-watchlist');
  if (hasSaved) {
    const ts = savedAt ? new Date(savedAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
    saveBtn.textContent  = '✓ VIEW SAVED';
    saveBtn.style.color  = 'var(--green)';
    clearBtn.style.display = '';
    clearBtn.title = `Clear saved view (saved ${ts})`;
  } else {
    saveBtn.textContent  = '💾 SAVE VIEW';
    saveBtn.style.color  = 'var(--accent)';
    clearBtn.style.display = 'none';
  }
}

function restoreExecWatchlist() {
  const raw = localStorage.getItem(_EXEC_WL_KEY);
  if (!raw) { _updateWatchlistButtons(false); return; }
  try {
    const prefs = JSON.parse(raw);
    const daysEl = document.getElementById('exec-days');
    const inclEl = document.getElementById('exec-incident-only');
    const confEl = document.getElementById('exec-confirmed-only');
    if (daysEl && prefs.days) daysEl.value = prefs.days;
    if (inclEl && prefs.incidentOnly !== undefined) inclEl.checked = prefs.incidentOnly;
    if (confEl && prefs.confirmedOnly !== undefined) confEl.checked = prefs.confirmedOnly;
    _updateWatchlistButtons(true, prefs.savedAt);
  } catch (_) { localStorage.removeItem(_EXEC_WL_KEY); }
}

// T1-5: Export CSV
function exportExecCsv() {
  if (!_execDataV2) return;
  const d = _execDataV2;
  const rows = [
    ['=== SECTOR RISK MATRIX ==='],
    ['Sector', 'Risk Score'],
    ...(d.sector_risk_scores || []).map(r => [r.sector, r.risk_score]),
    [],
    ['=== TOP THREAT ACTORS ==='],
    ['Threat Actor', 'Incident Count', 'Status'],
    ...d.ta_leaderboard.map(ta => {
      const prevSet = new Set((d.prev_ta_names || []).map(n => n.toLowerCase()));
      return [ta.name, ta.count, prevSet.has(ta.name.toLowerCase()) ? 'RECURRING' : 'NEW'];
    }),
    [],
    ['=== CVE EXPOSURE ==='],
    ['Technology', 'Total', 'Critical', 'High', 'Medium', 'Max CVSS', 'PoC Count'],
    ...(d.cve_exposure_v2 || []).map(r => [r.tech, r.total, r.critical, r.high, r.medium, r.max_cvss, r.poc_count]),
    [],
    ['=== SPIKE ALERTS ==='],
    ['Sector/Industry', 'Date', 'Count', 'Z-Score', 'Severity'],
    ...(d.industry_spikes || []).map(sp => [sp.entity, sp.date, sp.count, sp.z_score, sp.severity]),
    [],
    ['=== KPI SUMMARY ==='],
    ['Metric', 'Value'],
    ['Total Incidents', d.total_incidents],
    ['Active Sectors', d.active_sectors ?? d.top_sectors.length],
    ['Unique Threat Actors', d.unique_ta_count ?? d.ta_leaderboard.length],
    ['Critical CVEs', (d.cve_exposure_v2 || []).reduce((s, r) => s + r.critical, 0)],
    ['Highest Risk Sector', d.sector_risk_scores?.[0]?.sector || ''],
    ['Highest Risk Score', d.sector_risk_scores?.[0]?.risk_score || 0],
    ['Active Spikes', (d.industry_spikes || []).length],
  ];
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `cti-exec-dashboard-${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// T1-6: Generate Executive Brief (AI narrative)
async function generateExecBrief() {
  const btn = document.getElementById('exec-generate-brief');
  const days = document.getElementById('exec-days').value || 90;
  const incidentOnly = document.getElementById('exec-incident-only').checked;
  const confirmedOnly = document.getElementById('exec-confirmed-only').checked;
  btn.disabled = true;
  btn.textContent = '⟳ GENERATING...';
  try {
    const params = new URLSearchParams({days, incident_only: incidentOnly, confirmed_only: confirmedOnly});
    const r = await fetch(`/api/exec/brief?${params}`, {method:'POST'});
    const d = await r.json();
    document.getElementById('exec-brief-content').textContent = d.brief;
    document.getElementById('exec-brief-meta').textContent = `Generated: ${new Date(d.generated_at).toLocaleString()} · Period: ${days} days`;
    document.getElementById('exec-brief-modal').style.display = 'block';
  } catch(e) {
    alert('Brief generation failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '✦ GENERATE BRIEF';
  }
}
function copyExecBrief() {
  const text = document.getElementById('exec-brief-content').textContent;
  navigator.clipboard.writeText(text).then(() => alert('Copied to clipboard'));
}

// ══════════════════════════════════════════════════════════════
// PRIORITY INTELLIGENCE REQUIREMENTS (PIR)
// ══════════════════════════════════════════════════════════════
// PIR multi-select state
const _MS_FIELDS = ['tas', 'industries', 'countries', 'news_types', 'ttps'];
const _pirSelected = {tas:[], industries:[], countries:[], news_types:[], ttps:[]};
let _pirOptions = null;
let _pirEditId  = null;

function _pirCloseAllDropdowns() {
  document.querySelectorAll('.pir-ms-dropdown.open').forEach(d => d.classList.remove('open'));
}
document.addEventListener('click', _pirCloseAllDropdowns);

function pirMsOpen(field, event) {
  event.stopPropagation();
  const dd = document.getElementById('pir-dd-' + field);
  const isOpen = dd.classList.contains('open');
  _pirCloseAllDropdowns();
  if (isOpen) return;
  if (!dd.dataset.populated) _pirPopulateDropdown(field);
  dd.classList.add('open');
}

function _pirPopulateDropdown(field) {
  const dd     = document.getElementById('pir-dd-' + field);
  const apiKey = field === 'tas' ? 'threat_actors' : field;
  const opts   = _pirOptions ? (_pirOptions[apiKey] || []) : [];

  let html = `<div style="padding:6px 8px;border-bottom:1px solid var(--border);">` +
    `<input class="pir-ms-search" placeholder="Search…" style="width:100%;border:none;outline:none;background:transparent;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:10px;" ` +
    `oninput="pirMsFilter('${field}',this.value)" onclick="event.stopPropagation()"></div>`;

  if (!opts.length) {
    html += `<div class="pir-ms-no-opt">No options available</div>`;
  } else if (field === 'ttps') {
    opts.forEach(t => {
      const lbl = t.id + ' — ' + t.name;
      const sel = _pirSelected[field].includes(t.id);
      const safeId  = t.id.replace(/'/g, "\\'");
      const safeLbl = lbl.replace(/"/g, '&quot;');
      html += `<div class="pir-ms-opt${sel?' selected':''}" data-val="${t.id}" data-lbl="${safeLbl}" ` +
        `onclick="pirMsToggle('${field}','${safeId}',event)">` +
        `<input type="checkbox" ${sel?'checked':''} onclick="event.stopPropagation();pirMsToggle('${field}','${safeId}',event)"> ${lbl}</div>`;
    });
  } else {
    opts.forEach(v => {
      const sel     = _pirSelected[field].includes(v);
      const safeVal = v.replace(/'/g, "\\'");
      const safeLbl = v.replace(/"/g, '&quot;');
      html += `<div class="pir-ms-opt${sel?' selected':''}" data-val="${v}" data-lbl="${safeLbl}" ` +
        `onclick="pirMsToggle('${field}','${safeVal}',event)">` +
        `<input type="checkbox" ${sel?'checked':''} onclick="event.stopPropagation();pirMsToggle('${field}','${safeVal}',event)"> ${v}</div>`;
    });
  }

  dd.innerHTML = html;
  dd.dataset.populated = '1';
}

function pirMsToggle(field, value, event) {
  if (event) event.stopPropagation();
  const idx = _pirSelected[field].indexOf(value);
  if (idx === -1) _pirSelected[field].push(value);
  else            _pirSelected[field].splice(idx, 1);
  pirMsRender(field);
  const dd = document.getElementById('pir-dd-' + field);
  dd.querySelectorAll('.pir-ms-opt').forEach(opt => {
    const sel = _pirSelected[field].includes(opt.dataset.val);
    opt.classList.toggle('selected', sel);
    const cb = opt.querySelector('input[type=checkbox]');
    if (cb) cb.checked = sel;
  });
}

function pirMsSet(field, values) {
  _pirSelected[field] = [...(values || [])];
  const dd = document.getElementById('pir-dd-' + field);
  if (dd) delete dd.dataset.populated;
  pirMsRender(field);
}

function pirMsRender(field) {
  const box = document.querySelector('#pir-ms-' + field + ' .pir-ms-box');
  if (!box) return;
  const sel = _pirSelected[field];
  const labels = (field === 'ttps' && _pirOptions?.ttps)
    ? sel.map(id => { const t = _pirOptions.ttps.find(x => x.id === id); return {val:id, lbl:t ? id+' — '+t.name : id}; })
    : sel.map(v => ({val:v, lbl:v}));
  box.innerHTML = labels.map(({val, lbl}) =>
    `<span class="pir-ms-tag">${lbl}<span class="pir-ms-tag-x" onclick="pirMsToggle('${field}','${val.replace(/'/g,"\\'")}',event)">&#215;</span></span>`
  ).join('') + `<span class="pir-ms-placeholder"${labels.length?' style="display:none"':''}>Select…</span>`;
}

function pirMsFilter(field, q) {
  const dd = document.getElementById('pir-dd-' + field);
  const lq = q.toLowerCase();
  dd.querySelectorAll('.pir-ms-opt').forEach(opt => {
    opt.style.display = (opt.dataset.lbl || '').toLowerCase().includes(lq) ? '' : 'none';
  });
}

async function _pirEnsureOptions() {
  if (_pirOptions) return;
  try {
    const resp = await fetch('/api/pir/options');
    _pirOptions = await resp.json();
  } catch(e) {
    _pirOptions = {tas:[], industries:[], countries:[], news_types:[], ttps:[]};
    console.error('PIR options load failed', e);
  }
}

