// ── CAMPAIGN CLUSTERS ──────────────────────────────────────────

let _campaignData = [];
let _campaignExpanded = {};
let _campaignSort = 'size';

function _ensureVelocityCss() {
  if (document.getElementById('velocity-css')) return;
  const s = document.createElement('style');
  s.id = 'velocity-css';
  s.textContent = `
    .vel-dot{display:inline-block;width:7px;height:7px;border-radius:50%;flex-shrink:0;vertical-align:middle}
    .vel-surging{background:#ff4444;animation:vel-pulse 1s ease-in-out infinite}
    .vel-active{background:#ffaa00}
    .vel-moderate{background:#cccc00}
    .vel-slow{background:#555}
    @keyframes vel-pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.4)}}
    .trend-growing{color:#ff4444}
    .trend-stable{color:#cccc00}
    .trend-declining{color:#34a853}
    .trend-dormant{color:#555}
    .campaign-alert-row td{background:rgba(255,68,68,0.05)!important}
    .sev-critical{background:rgba(218,54,51,0.18);border:1px solid rgba(218,54,51,0.5);color:#ff6b6b}
    .sev-high{background:rgba(255,140,0,0.15);border:1px solid rgba(255,140,0,0.45);color:#ffaa00}
    .sev-medium{background:rgba(204,204,0,0.12);border:1px solid rgba(204,204,0,0.4);color:#cccc00}
    .sev-low{background:rgba(100,100,100,0.15);border:1px solid rgba(100,100,100,0.35);color:#888}
    .kc-full_chain{background:rgba(218,54,51,0.15);border:1px solid rgba(218,54,51,0.4);color:#ff6b6b}
    .kc-partial_chain{background:rgba(255,140,0,0.12);border:1px solid rgba(255,140,0,0.35);color:#ffaa00}
    .kc-limited{background:rgba(100,100,100,0.12);border:1px solid rgba(100,100,100,0.3);color:#888}
    .ltype-same_actor{background:rgba(218,54,51,0.12);border:1px solid rgba(218,54,51,0.4);color:#ff6b6b}
    .ltype-shared_infra{background:rgba(255,140,0,0.12);border:1px solid rgba(255,140,0,0.35);color:#ffaa00}
    .ltype-similar_ttp{background:rgba(83,52,131,0.15);border:1px solid rgba(83,52,131,0.35);color:#a78bdb}
    .ltype-related{background:rgba(100,100,100,0.12);border:1px solid rgba(100,100,100,0.3);color:#888}
  `;
  document.head.appendChild(s);
}

function _severityBadge(c) {
  const label = c.severity_label || 'low';
  const score = c.severity_score != null ? c.severity_score : '';
  const title = c.severity_breakdown ? _severityBreakdownTitle(c.severity_breakdown) : '';
  return `<span class="sev-${label}" title="${escHtml(title)}" style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;font-weight:700;margin-left:4px;cursor:default">${label.toUpperCase()} ${score}</span>`;
}

function _severityBreakdownTitle(bd) {
  if (!bd) return '';
  return [
    `TA Sophistication: ${bd.ta_sophistication}`,
    `IOC Confidence: ${bd.ioc_confidence}`,
    `CVE Criticality: ${bd.cve_criticality}`,
    `Velocity: ${bd.campaign_velocity}`,
    `Source Quality: ${bd.source_quality}`,
  ].join(' | ');
}

function _velocityBadge(c) {
  const label = c.velocity_label || 'slow';
  const apd = (c.velocity_articles_per_day || 0).toFixed(1);
  if (label === 'surging') {
    return `<span style="display:inline-flex;align-items:center;gap:3px;margin-left:4px"><span class="vel-dot vel-surging"></span><span style="font-size:9px;color:#ff4444;font-weight:700;letter-spacing:.05em">SURGING</span></span>`;
  }
  if (label === 'active') {
    return `<span style="display:inline-flex;align-items:center;gap:3px;margin-left:4px"><span class="vel-dot vel-active"></span><span style="font-size:9px;color:#ffaa00;font-weight:700;letter-spacing:.05em">ACTIVE</span></span>`;
  }
  return `<span style="margin-left:4px;display:inline-flex;align-items:center" title="${label} — ${apd}/day"><span class="vel-dot vel-${label}"></span></span>`;
}

const _TREND_ARROWS = { growing: '↑', stable: '→', declining: '↓', dormant: '↓' };
const _TREND_DIAG   = { growing: '↗', declining: '↘' };

function _trendArrow(trend) {
  if (!trend || !trend.trend_direction) return '';
  const dir = trend.trend_direction;
  const arrow = _TREND_DIAG[dir] || _TREND_ARROWS[dir] || '→';
  const gr = trend.growth_rate != null ? ` ${trend.growth_rate > 0 ? '+' : ''}${trend.growth_rate}%` : '';
  return `<span class="trend-${dir}" title="Trend: ${dir}${gr}" style="font-size:12px;margin-left:4px;cursor:default">${arrow}</span>`;
}

function _sparkline(timeline, width, height) {
  if (!timeline || timeline.length < 2) return '';
  const counts = timeline.map(p => p.count);
  const max = Math.max(...counts, 1);
  const min = Math.min(...counts);
  const range = max - min || 1;
  const step = width / (counts.length - 1);
  const pts = counts.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="display:block;overflow:visible">
    <polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" opacity="0.7"/>
  </svg>`;
}

let _campaignTrends = {};

async function _loadTrend(clusterId) {
  if (_campaignTrends[clusterId]) return _campaignTrends[clusterId];
  try {
    const res = await fetch(`/api/clusters/${encodeURIComponent(clusterId)}/trends`, { headers: _authAndClientHeaders() });
    if (!res.ok) return null;
    const data = await res.json();
    _campaignTrends[clusterId] = data;
    return data;
  } catch { return null; }
}

function _setCampaignSort(sort) {
  _campaignSort = sort;
  _renderCampaigns();
}

async function loadCampaigns() {
  const body    = document.getElementById('campaigns-body');
  const footer  = document.getElementById('campaigns-footer');
  const countEl = document.getElementById('intel-campaigns-count');
  const days    = document.getElementById('campaigns-days').value;
  const minSize = document.getElementById('campaigns-minsize').value;

  body.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Clustering campaigns…</div></div>';

  try {
    const res  = await fetch(`/api/clusters/recent?days=${days}&min_size=${minSize}`, { headers: _authAndClientHeaders() });
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();

    _campaignData    = data.campaigns || [];
    _campaignExpanded = {};
    countEl.textContent = _campaignData.length;
    footer.textContent  = `${_campaignData.length} campaign cluster${_campaignData.length !== 1 ? 's' : ''} found`;

    _renderCampaigns();
  } catch(e) {
    body.innerHTML = `<div class="intel-empty" style="color:var(--red)">Error: ${escHtml(e.message)}</div>`;
  }
}

function _renderCampaigns() {
  _ensureVelocityCss();
  const body = document.getElementById('campaigns-body');

  if (!_campaignData.length) {
    body.innerHTML = '<div class="intel-empty">No campaign clusters found for selected parameters</div>';
    return;
  }

  const sorted = _campaignSort === 'velocity'
    ? [..._campaignData].sort((a, b) => (b.velocity_articles_per_day || 0) - (a.velocity_articles_per_day || 0))
    : _campaignSort === 'severity'
    ? [..._campaignData].sort((a, b) => (b.severity_score || 0) - (a.severity_score || 0))
    : _campaignSort === 'first_seen'
    ? [..._campaignData].sort((a, b) => (a.first_seen || '').localeCompare(b.first_seen || ''))
    : _campaignSort === 'last_seen'
    ? [..._campaignData].sort((a, b) => (b.last_seen || '').localeCompare(a.last_seen || ''))
    : _campaignSort === 'size'
    ? [..._campaignData].sort((a, b) => (b.size || 0) - (a.size || 0))
    : _campaignData;

  const btnBase = 'font-family:\'IBM Plex Mono\',monospace;font-size:10px;padding:2px 8px;border-radius:3px;cursor:pointer;border:1px solid';
  const sortBar = `
    <div style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-bottom:1px solid var(--border);font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">
      Sort:
      <button onclick="_setCampaignSort('size')" style="${btnBase} ${_campaignSort==='size'?'background:rgba(47,129,247,0.15);border-color:rgba(47,129,247,0.5);color:var(--accent)':'background:transparent;border-color:var(--border);color:var(--text-dim)'}">Article Count</button>
      <button onclick="_setCampaignSort('velocity')" style="${btnBase} ${_campaignSort==='velocity'?'background:rgba(47,129,247,0.15);border-color:rgba(47,129,247,0.5);color:var(--accent)':'background:transparent;border-color:var(--border);color:var(--text-dim)'}">Velocity</button>
      <button onclick="_setCampaignSort('severity')" style="${btnBase} ${_campaignSort==='severity'?'background:rgba(47,129,247,0.15);border-color:rgba(47,129,247,0.5);color:var(--accent)':'background:transparent;border-color:var(--border);color:var(--text-dim)'}">Severity</button>
      <button onclick="_setCampaignSort('first_seen')" style="${btnBase} ${_campaignSort==='first_seen'?'background:rgba(47,129,247,0.15);border-color:rgba(47,129,247,0.5);color:var(--accent)':'background:transparent;border-color:var(--border);color:var(--text-dim)'}">First Seen</button>
      <button onclick="_setCampaignSort('last_seen')" style="${btnBase} ${_campaignSort==='last_seen'?'background:rgba(47,129,247,0.15);border-color:rgba(47,129,247,0.5);color:var(--accent)':'background:transparent;border-color:var(--border);color:var(--text-dim)'}">Last Seen</button>
    </div>`;

  const rows = sorted.map((c) => {
    const cid = c.cluster_id;
    const taChips = (c.dominant_tas || []).map(t =>
      `<span onclick="taViewProfile('${escHtml(t)}')" title="View TA profile"
        style="cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(255,165,0,0.1);border:1px solid rgba(255,165,0,0.3);color:#ffaa00">${escHtml(t)}</span>`
    ).join(' ');

    const indChips = (c.dominant_industries || []).map(i =>
      `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(47,129,247,0.08);border:1px solid rgba(47,129,247,0.25);color:var(--accent)">${escHtml(i)}</span>`
    ).join(' ');

    const ctrChips = (c.dominant_countries || []).map(ct =>
      `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(88,166,255,0.1);border:1px solid rgba(88,166,255,0.3);color:#58A6FF">${escHtml(ct)}</span>`
    ).join(' ');

    const kc = c.kill_chain || {};
    const kcLabel = kc.completeness_label || '';
    const kcScore = kc.completeness_score != null ? kc.completeness_score : '';
    const kcRisk  = kc.operational_risk || '';
    const kcBadge = kcLabel
      ? `<span class="kc-${kcLabel}" title="Kill chain: ${kcLabel.replace('_',' ')} | Risk: ${kcRisk}" style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;font-weight:700;cursor:default;margin-left:4px">${kcScore}%</span>`
      : '';
    const ttpChips = (c.attack_techniques || []).slice(0, 5).map(t =>
      `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(83,52,131,0.15);border:1px solid rgba(83,52,131,0.35);color:#a78bdb">${escHtml(t)}</span>`
    ).join(' ');

    const trend = _campaignTrends[cid] || null;
    const trendArrowHtml = _trendArrow(trend);

    const pirBadges = (c.matched_pirs || []).length > 0
      ? `<span title="${(c.matched_pirs).map(p => escHtml(p.title)).join('\n')}"
          style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(218,54,51,0.1);border:1px solid rgba(218,54,51,0.3);color:var(--red)">PIR</span>`
      : '';

    const newIocBadge = (c.new_iocs_24h > 0)
      ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(52,168,83,0.12);border:1px solid rgba(52,168,83,0.35);color:#34a853;margin-left:4px">NEW: ${c.new_iocs_24h} IOCs</span>`
      : '';

    const velBadge = _velocityBadge(c);
    const sevBadge = _severityBadge(c);
    const alertClass = c.velocity_alert ? ' class="campaign-alert-row"' : '';
    const expandedHtml = _campaignExpanded[cid] ? _renderCampaignExpanded(c, cid) : '';

    return `
      <tr${alertClass}>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright);cursor:pointer;max-width:260px"
            onclick="toggleCampaign('${escHtml(cid)}')">
          <span style="color:var(--text-dim);margin-right:4px">${_campaignExpanded[cid] ? '▼' : '▶'}</span>
          ${escHtml(c.summary_title || cid)}${trendArrowHtml}
          ${sevBadge}
          ${pirBadges ? `<span style="margin-left:4px;display:inline-block">${pirBadges}</span>` : ''}
        </td>
        <td style="text-align:center;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright);white-space:nowrap">
          ${c.size}${velBadge}${newIocBadge}
        </td>
        <td style="white-space:nowrap">${sevBadge}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${escHtml(c.first_seen)}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${escHtml(c.last_seen)}</td>
        <td style="max-width:160px">${taChips || '<span style="color:var(--text-dim);font-size:10px">—</span>'}</td>
        <td style="max-width:160px">${indChips || '<span style="color:var(--text-dim);font-size:10px">—</span>'}</td>
        <td style="max-width:120px">${ctrChips || '<span style="color:var(--text-dim);font-size:10px">—</span>'}</td>
        <td style="max-width:200px">${ttpChips || '<span style="color:var(--text-dim);font-size:10px">—</span>'}${kcBadge}</td>
        <td style="white-space:nowrap">
          <button onclick="campaignHuntPack('${escHtml(cid)}')"
            style="font-size:10px;padding:3px 8px;background:rgba(47,129,247,0.08);border:1px solid rgba(47,129,247,0.3);color:var(--accent);border-radius:3px;cursor:pointer">⬇ Hunt Pack</button>
        </td>
      </tr>
      ${expandedHtml ? `<tr><td colspan="10" style="padding:0">${expandedHtml}</td></tr>` : ''}`;
  }).join('');

  const table = `
    <table style="width:100%;border-collapse:collapse;font-family:'IBM Plex Mono',monospace;font-size:11px">
      <thead>
        <tr style="color:var(--text-dim);border-bottom:1px solid var(--border)">
          <th style="text-align:left;padding:6px 8px">Summary Title</th>
          <th style="text-align:center;padding:6px 8px;width:80px;cursor:pointer" onclick="_setCampaignSort('size')">Size / Velocity ↕</th>
          <th style="text-align:left;padding:6px 8px;width:80px;cursor:pointer" onclick="_setCampaignSort('severity')">Severity ↕</th>
          <th style="text-align:left;padding:6px 8px;width:90px;cursor:pointer" onclick="_setCampaignSort('first_seen')">First Seen ↕</th>
          <th style="text-align:left;padding:6px 8px;width:90px;cursor:pointer" onclick="_setCampaignSort('last_seen')">Last Seen ↕</th>
          <th style="text-align:left;padding:6px 8px">TAs</th>
          <th style="text-align:left;padding:6px 8px">Industries</th>
          <th style="text-align:left;padding:6px 8px">Countries</th>
          <th style="text-align:left;padding:6px 8px">ATT&CK</th>
          <th style="text-align:left;padding:6px 8px">Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;

  document.getElementById('campaigns-body').innerHTML = sortBar + table;
}

function _renderCampaignExpanded(c, clusterId) {
  const articleRows = (c.member_article_ids || []).map((aid, i) => {
    const title = escHtml((c.titles || [])[i] || aid);
    return `<div style="padding:6px 12px;border-bottom:1px solid var(--border)">
      <span style="cursor:pointer;color:var(--accent)" onclick="openArticleById('${escHtml(aid)}')">${title}</span>
    </div>`;
  }).join('');

  const iocChips = (c.iocs || []).slice(0, 20).map(ioc =>
    `<span style="cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;border-radius:2px;background:rgba(218,54,51,0.08);border:1px solid rgba(218,54,51,0.25);color:var(--red)"
      onclick="iocmgmtOpenDetail('${escHtml(ioc.type)}','${escHtml(ioc.value.replace(/'/g,"\\x27"))}')"
      title="${escHtml(ioc.type)}">${escHtml(ioc.value)}</span>`
  ).join(' ');

  const _cvePrioList = (c.prioritized_cves && c.prioritized_cves.length)
    ? c.prioritized_cves
    : (c.cve_ids || []).map(id => ({ cve_id: id, priority_label: null, patch_urgency: null, cvss_score: null, in_tech_stack: false }));

  const _cveBorderColor = lbl =>
    lbl === 'critical_patch' ? '#da3633' : lbl === 'high_priority' ? '#e8750a' : lbl === 'medium' ? '#cccc00' : 'rgba(52,168,83,0.4)';
  const _cveBg = lbl =>
    lbl === 'critical_patch' ? 'rgba(218,54,51,0.08)' : lbl === 'high_priority' ? 'rgba(232,117,10,0.08)' : lbl === 'medium' ? 'rgba(204,204,0,0.08)' : 'rgba(52,168,83,0.06)';

  const cveChips = _cvePrioList.slice(0, 20).map(pv => {
    const border = _cveBorderColor(pv.priority_label);
    const bg     = _cveBg(pv.priority_label);
    const star   = pv.in_tech_stack ? '<span title="In your tech stack" style="color:#ffcc00;margin-right:2px">★</span>' : '';
    const cvss   = pv.cvss_score != null ? `<span style="font-size:8px;opacity:0.75;margin-left:3px">${pv.cvss_score}</span>` : '';
    const urgency = pv.patch_urgency ? `<span style="font-size:8px;opacity:0.65;margin-left:3px">${pv.patch_urgency}</span>` : '';
    return `<span style="cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 6px;border-radius:2px;background:${bg};border:1px solid ${border};color:var(--text-bright);display:inline-flex;align-items:center"
      onclick="openCveDetail && openCveDetail('${escHtml(pv.cve_id)}')"
      title="${escHtml(pv.priority_label || '')}${pv.patch_urgency ? ' — patch: '+pv.patch_urgency : ''}"
      >${star}${escHtml(pv.cve_id)}${cvss}${urgency}</span>`;
  }).join(' ');

  const pirRows = (c.matched_pirs || []).map((p, pirIdx) =>
    `<div style="padding:6px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;cursor:pointer" onclick="openClusterPir('${escHtml(clusterId)}',${pirIdx})">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(218,54,51,0.1);border:1px solid rgba(218,54,51,0.3);color:var(--red);flex-shrink:0;pointer-events:none">PIR</span>
      <span style="color:var(--text-bright);font-size:11px;pointer-events:none">${escHtml(p.title)}</span>
    </div>`
  ).join('');

  const sevBreakdownHtml = (() => {
    const bd = c.severity_breakdown;
    if (!bd) return '';
    const raw = bd.raw || {};
    const rows = [
      ['TA Sophistication', bd.ta_sophistication, raw.ta_sophistication, '30%'],
      ['IOC Confidence',    bd.ioc_confidence,    raw.ioc_confidence,    '20%'],
      ['CVE Criticality',   bd.cve_criticality,   raw.cve_criticality,   '20%'],
      ['Campaign Velocity', bd.campaign_velocity, raw.campaign_velocity, '15%'],
      ['Source Quality',    bd.source_quality,    raw.source_quality,    '15%'],
    ].map(([name, contrib, rawScore, weight]) =>
      `<div style="display:flex;align-items:center;gap:8px;padding:3px 0;font-family:'IBM Plex Mono',monospace;font-size:10px">
        <span style="color:var(--text-dim);width:130px;flex-shrink:0">${name} (${weight})</span>
        <div style="flex:1;height:4px;background:rgba(255,255,255,0.08);border-radius:2px">
          <div style="width:${Math.round(rawScore)}%;height:100%;background:var(--accent);border-radius:2px"></div>
        </div>
        <span style="color:var(--text-bright);width:32px;text-align:right">${rawScore}</span>
        <span style="color:var(--text-dim);width:36px;text-align:right">+${contrib}</span>
      </div>`
    ).join('');
    const label = c.severity_label || 'low';
    return `<div style="margin-bottom:10px">
      <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">
        Severity Breakdown — <span class="sev-${label}" style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;font-weight:700">${label.toUpperCase()} ${c.severity_score}</span>
      </div>
      <div style="padding:8px 10px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px">${rows}</div>
    </div>`;
  })();

  const killChainHtml = (() => {
    const kc = c.kill_chain;
    if (!kc || !kc.chain_visualization) return '';
    const label = kc.completeness_label || 'limited';
    const score = kc.completeness_score != null ? kc.completeness_score : 0;
    const risk  = kc.operational_risk || 'low';
    const riskColor = risk === 'critical' ? '#ff6b6b' : risk === 'high' ? '#ffaa00' : risk === 'medium' ? '#cccc00' : '#888';
    const labelColor = label === 'full_chain' ? '#ff6b6b' : label === 'partial_chain' ? '#ffaa00' : '#888';

    const segments = kc.chain_visualization.map(phase => {
      const phaseName = phase.phase.replace(/_/g, ' ');
      const techs = (phase.techniques || []).map(t => escHtml(t)).join('&#10;');
      const bg = phase.covered ? labelColor : 'rgba(100,100,100,0.2)';
      const border = phase.covered ? labelColor : 'rgba(100,100,100,0.3)';
      return `<div title="${phaseName}${techs ? '&#10;' + techs : ''}"
        style="flex:1;height:12px;background:${bg};border:1px solid ${border};border-radius:2px;opacity:${phase.covered ? '0.85' : '0.3'};cursor:default"></div>`;
    }).join('');

    const phaseDetails = kc.chain_visualization
      .filter(p => p.covered && p.techniques.length)
      .map(p => {
        const chips = p.techniques.map(t =>
          `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 4px;border-radius:2px;background:rgba(83,52,131,0.15);border:1px solid rgba(83,52,131,0.3);color:#a78bdb">${escHtml(t)}</span>`
        ).join(' ');
        return `<div style="display:flex;align-items:flex-start;gap:6px;padding:3px 0">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);width:120px;flex-shrink:0;padding-top:1px">${p.phase.replace(/_/g,' ')}</span>
          <div style="display:flex;gap:3px;flex-wrap:wrap">${chips}</div>
        </div>`;
      }).join('');

    return `<div style="margin-bottom:10px">
      <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;display:flex;align-items:center;gap:8px">
        Kill Chain Coverage
        <span class="kc-${label}" style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;font-weight:700">${score}% — ${label.replace(/_/g,' ')}</span>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:${riskColor}">Risk: ${risk}</span>
      </div>
      <div style="display:flex;gap:2px;margin-bottom:6px;padding:0 2px">${segments}</div>
      <div style="display:flex;gap:2px;padding:0 2px;margin-bottom:8px">
        ${kc.chain_visualization.map(p =>
          `<div style="flex:1;font-family:'IBM Plex Mono',monospace;font-size:7px;color:var(--text-dim);text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${p.phase.replace(/_/g,' ')}">${p.phase.replace(/_/g,'_').split('_')[0]}</div>`
        ).join('')}
      </div>
      ${phaseDetails ? `<div style="padding:6px 8px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px">${phaseDetails}</div>` : ''}
    </div>`;
  })();

  const trendHtml = (() => {
    const trend = _campaignTrends[clusterId];
    if (!trend || !trend.timeline || trend.timeline.length < 2) return '';
    const dir = trend.trend_direction || 'stable';
    const dirColor = dir === 'growing' ? '#ff4444' : dir === 'declining' ? '#34a853' : dir === 'dormant' ? '#555' : '#cccc00';
    const gr = trend.growth_rate != null ? `${trend.growth_rate > 0 ? '+' : ''}${trend.growth_rate}%` : '—';
    const spark = _sparkline(trend.timeline, 200, 32);
    const peakNote = trend.predicted_peak ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-left:8px">est. peak ${trend.predicted_peak}</span>` : '';
    return `<div style="margin-bottom:10px">
      <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;display:flex;align-items:center;gap:8px">
        Campaign Trend
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(255,255,255,0.04);border:1px solid var(--border);color:${dirColor}">${dir}</span>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:${dirColor}">${gr} 7d</span>
        ${peakNote}
      </div>
      <div style="padding:6px 10px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px;display:flex;align-items:center;gap:10px">
        ${spark}
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">${trend.timeline[0]?.date || ''} → ${trend.timeline[trend.timeline.length-1]?.date || ''}</span>
      </div>
    </div>`;
  })();

  return `
    <div style="background:rgba(255,255,255,0.02);border-top:1px solid var(--border);padding:12px 16px">
      ${trendHtml}
      ${sevBreakdownHtml}
      ${killChainHtml}
      ${_renderDiamondModel(c)}
      ${pirRows ? `<div style="margin-bottom:10px">
        <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Matched PIRs (${(c.matched_pirs||[]).length})</div>
        <div style="border:1px solid var(--border);border-radius:4px;overflow:hidden">${pirRows}</div>
      </div>` : ''}
      <div style="margin-bottom:10px">
        <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Member Articles (${(c.member_article_ids||[]).length})</div>
        <div style="border:1px solid var(--border);border-radius:4px;overflow:hidden;max-height:180px;overflow-y:auto">${articleRows || '<div style="padding:8px;color:var(--text-dim);font-size:10px">None</div>'}</div>
      </div>
      ${iocChips ? `<div style="margin-bottom:10px">
        <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">IOCs (${(c.iocs||[]).length})</div>
        <div style="display:flex;gap:4px;flex-wrap:wrap">${iocChips}</div>
      </div>` : ''}
      ${cveChips ? `<div>
        <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">CVEs (${_cvePrioList.length})</div>
        <div style="display:flex;gap:4px;flex-wrap:wrap">${cveChips}</div>
      </div>` : ''}
      ${mmInlineWidget(`mm-cluster-${c.cluster_id}`, 'cluster', c.cluster_id, c.cluster_name || c.cluster_id)}
      ${_renderRelatedCampaigns(c)}
    </div>`;
}

function _renderDiamondModel(c) {
  const dm = c.diamond_model;
  if (!dm) return '';

  const adv = dm.adversary || {};
  const inf = dm.infrastructure || {};
  const cap = dm.capability || {};
  const vic = dm.victim || {};
  const meta = dm.meta || {};

  function chips(items, color, limit) {
    if (!items || !items.length) return '<span style="color:var(--text-dim);font-size:9px;opacity:0.6">—</span>';
    const shown = items.slice(0, limit || 5);
    const more = items.length > (limit || 5) ? items.length - (limit || 5) : 0;
    return shown.map(v =>
      `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 4px;border-radius:2px;background:${color}18;border:1px solid ${color}44;color:${color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:120px;display:inline-block" title="${escHtml(String(v))}">${escHtml(String(v))}</span>`
    ).join(' ') + (more ? `<span style="font-size:8px;color:var(--text-dim)">+${more}</span>` : '');
  }

  function quadrantItems(items, color) {
    if (!items || !items.length) return '<span style="color:var(--text-dim);font-size:9px;opacity:0.6">—</span>';
    return chips(items, color, 4);
  }

  const advItems = [
    ...((adv.threat_actors || []).slice(0, 3)),
    ...(adv.sponsoring_nations || []).map(n => `🌐 ${n}`),
    ...(adv.sophistication ? [`Soph: ${adv.sophistication}`] : []),
  ];

  const allInfra = [
    ...(inf.domains || []),
    ...(inf.ips || []),
    ...(inf.urls || []),
  ];

  const allTechs = Object.values(cap.attack_techniques || {}).flat();
  const capItems = [
    ...allTechs.slice(0, 3),
    ...(cap.malware || []).slice(0, 2).map(m => `🦠 ${m}`),
    ...(cap.tools || []).slice(0, 1).map(t => `🔧 ${t}`),
    ...(cap.cve_exploited || []).slice(0, 2),
  ];

  const vicItems = [
    ...(vic.industries || []),
    ...(vic.countries || []),
    ...(vic.organization_types || []).slice(0, 2),
  ];

  const confColor = meta.confidence === 'high' ? '#34a853' : meta.confidence === 'medium' ? '#cccc00' : '#888';
  const dirLabel = meta.direction || 'inbound';

  const expandId = `dm-expand-${c.cluster_id}`;

  return `<div style="margin-bottom:10px">
    <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;display:flex;align-items:center;gap:8px">
      Diamond Model
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:${confColor}18;border:1px solid ${confColor}44;color:${confColor}">conf: ${meta.confidence || 'low'}</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(255,255,255,0.04);border:1px solid var(--border);color:var(--text-dim)">${dirLabel}</span>
      <button onclick="_dmToggleExpand('${escHtml(c.cluster_id)}')"
        style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 6px;border-radius:2px;background:transparent;border:1px solid var(--border);color:var(--text-dim);cursor:pointer;margin-left:auto" id="dm-btn-${escHtml(c.cluster_id)}">expand</button>
    </div>
    <div style="position:relative;width:100%;padding:0 8px">
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;grid-template-rows:auto auto auto;gap:0;position:relative">
        <div></div>
        <div style="padding:8px;background:rgba(255,140,0,0.06);border:1px solid rgba(255,140,0,0.25);border-radius:4px 4px 0 0;min-height:64px">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#ffaa00;font-weight:700;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em">▲ Adversary</div>
          <div style="display:flex;gap:3px;flex-wrap:wrap">${quadrantItems(advItems, '#ffaa00')}</div>
        </div>
        <div></div>
        <div style="padding:8px;background:rgba(83,52,131,0.08);border:1px solid rgba(83,52,131,0.3);border-radius:4px 0 0 4px;min-height:72px;border-right:none">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#a78bdb;font-weight:700;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em">◀ Capability</div>
          <div style="display:flex;gap:3px;flex-wrap:wrap">${quadrantItems(capItems, '#a78bdb')}</div>
        </div>
        <div style="display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.03);border:1px solid var(--border);min-height:72px;padding:6px;text-align:center">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);line-height:1.4;word-break:break-word">${escHtml((c.cluster_name || '').slice(0, 40))}</span>
        </div>
        <div style="padding:8px;background:rgba(47,129,247,0.06);border:1px solid rgba(47,129,247,0.25);border-radius:0 4px 4px 0;min-height:72px;border-left:none">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--accent);font-weight:700;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em">▶ Infrastructure</div>
          <div style="display:flex;gap:3px;flex-wrap:wrap">${quadrantItems(allInfra, '#2f81f7')}</div>
        </div>
        <div></div>
        <div style="padding:8px;background:rgba(52,168,83,0.06);border:1px solid rgba(52,168,83,0.25);border-radius:0 0 4px 4px;min-height:64px;border-top:none">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#34a853;font-weight:700;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em">▼ Victim</div>
          <div style="display:flex;gap:3px;flex-wrap:wrap">${quadrantItems(vicItems, '#34a853')}</div>
        </div>
        <div></div>
      </div>
    </div>
    <div id="${expandId}" style="display:none;margin-top:8px;padding:8px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px">
      ${_dmFullDetails(adv, inf, cap, vic)}
    </div>
  </div>`;
}

function _dmFullDetails(adv, inf, cap, vic) {
  function section(title, color, items) {
    if (!items || !items.length) return '';
    const chipHtml = items.map(v =>
      `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:${color}18;border:1px solid ${color}44;color:${color}">${escHtml(String(v))}</span>`
    ).join(' ');
    return `<div style="margin-bottom:8px">
      <div style="font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">${title}</div>
      <div style="display:flex;gap:3px;flex-wrap:wrap">${chipHtml}</div>
    </div>`;
  }

  const tacticOrder = ['initial_access','execution','persistence','privilege_escalation',
    'defense_evasion','credential_access','discovery','lateral_movement',
    'collection','exfiltration','command_and_control','impact','other'];

  const techSections = tacticOrder.map(tactic => {
    const techs = (cap.attack_techniques || {})[tactic];
    if (!techs || !techs.length) return '';
    const label = tactic.replace(/_/g, ' ');
    return section(label, '#a78bdb', techs);
  }).join('');

  return `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div>
        <div style="font-size:10px;font-weight:700;color:#ffaa00;margin-bottom:6px">Adversary</div>
        ${section('Threat Actors', '#ffaa00', adv.threat_actors)}
        ${section('Actor Types', '#ffaa00', adv.actor_types)}
        ${section('Sponsoring Nations', '#ffaa00', adv.sponsoring_nations)}
        ${adv.sophistication ? `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">Sophistication: <span style="color:#ffaa00">${escHtml(adv.sophistication)}</span></div>` : ''}
      </div>
      <div>
        <div style="font-size:10px;font-weight:700;color:#2f81f7;margin-bottom:6px">Infrastructure</div>
        ${section('Domains', '#2f81f7', inf.domains)}
        ${section('IPs', '#2f81f7', inf.ips)}
        ${section('URLs', '#2f81f7', inf.urls)}
      </div>
      <div>
        <div style="font-size:10px;font-weight:700;color:#a78bdb;margin-bottom:6px">Capability</div>
        ${techSections || section('Techniques', '#a78bdb', Object.values(cap.attack_techniques || {}).flat())}
        ${section('Malware', '#a78bdb', cap.malware)}
        ${section('Tools', '#a78bdb', cap.tools)}
        ${section('CVEs Exploited', '#a78bdb', cap.cve_exploited)}
      </div>
      <div>
        <div style="font-size:10px;font-weight:700;color:#34a853;margin-bottom:6px">Victim</div>
        ${section('Industries', '#34a853', vic.industries)}
        ${section('Countries', '#34a853', vic.countries)}
        ${section('Org Types', '#34a853', vic.organization_types)}
      </div>
    </div>`;
}

const _dmExpandedState = {};

function _dmToggleExpand(clusterId) {
  _dmExpandedState[clusterId] = !_dmExpandedState[clusterId];
  const el = document.getElementById(`dm-expand-${clusterId}`);
  const btn = document.getElementById(`dm-btn-${clusterId}`);
  if (el) el.style.display = _dmExpandedState[clusterId] ? 'block' : 'none';
  if (btn) btn.textContent = _dmExpandedState[clusterId] ? 'collapse' : 'expand';
}

function _renderRelatedCampaigns(c) {
  const related = c.related_campaigns || [];
  if (!related.length) return '';

  const ltypeLabel = { same_actor: 'Same Actor', shared_infra: 'Shared Infra', similar_ttp: 'Similar TTP', related: 'Related' };

  const rows = related.map(rc => {
    const se = rc.shared_elements || {};
    const hints = [
      ...(se.tas  || []).slice(0,2).map(v => escHtml(v)),
      ...(se.ttps || []).slice(0,2).map(v => escHtml(v)),
      ...(se.iocs || []).slice(0,1).map(v => escHtml(v)),
    ].join(', ');
    const ltLabel = ltypeLabel[rc.link_type] || rc.link_type;
    return `<div style="padding:6px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;cursor:pointer"
        onclick="jumpToCampaign('${escHtml(rc.cluster_id)}')">
      <span class="ltype-${escHtml(rc.link_type)}"
        style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;flex-shrink:0;pointer-events:none">${escHtml(ltLabel)}</span>
      <span style="color:var(--text-bright);font-size:11px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;pointer-events:none">${escHtml(rc.cluster_name)}</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);flex-shrink:0;pointer-events:none">${rc.link_score}</span>
      ${hints ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);flex-shrink:0;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;pointer-events:none" title="${hints}">↳ ${hints}</span>` : ''}
    </div>`;
  }).join('');

  return `<div style="margin-top:10px">
    <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Related Campaigns (${related.length})</div>
    <div style="border:1px solid var(--border);border-radius:4px;overflow:hidden">${rows}</div>
  </div>`;
}

function jumpToCampaign(clusterId) {
  _campaignExpanded[clusterId] = true;
  _renderCampaigns();
  requestAnimationFrame(() => {
    const rows = document.querySelectorAll('#campaigns-body tr');
    for (const row of rows) {
      if (row.querySelector(`[onclick*="${CSS.escape(clusterId)}"]`) ||
          (row.getAttribute('onclick') || '').includes(clusterId)) {
        row.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
    }
    const allTds = document.querySelectorAll('#campaigns-body td');
    for (const td of allTds) {
      if ((td.getAttribute('onclick') || '').includes(clusterId)) {
        td.closest('tr')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
    }
  });
}

function openClusterPir(clusterId, pirIdx) {
  const c = _campaignData.find(x => x.cluster_id === clusterId);
  if (!c) return;
  const pir = (c.matched_pirs || [])[pirIdx];
  if (!pir) return;
  _showClusterPirModal(pir);
}

let _currentClusterPir = null;

function _clusterPirViewArticles() {
  if (!_currentClusterPir) return;
  document.getElementById('cluster-pir-modal')?.remove();
  viewPirArticles(_currentClusterPir.id, _currentClusterPir.title);
}

function _showClusterPirModal(pir) {
  _currentClusterPir = pir;
  const existing = document.getElementById('cluster-pir-modal');
  if (existing) existing.remove();

  const crit = pir.criteria || {};
  const chips = (arr) => (arr || []).map(v =>
    `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:1px 7px;border-radius:2px;background:rgba(47,129,247,0.08);border:1px solid rgba(47,129,247,0.25);color:var(--accent)">${escHtml(v)}</span>`
  ).join(' ') || '<span style="color:var(--text-dim);font-size:10px">—</span>';

  const priorityColor = pir.priority === 'P1' ? 'var(--red)' : pir.priority === 'P2' ? '#ffaa00' : 'var(--text-dim)';

  const html = `
    <div id="cluster-pir-modal" style="position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:9500;display:flex;align-items:center;justify-content:center;" onclick="if(event.target===this)this.remove()">
      <div style="background:var(--surface);border:1px solid var(--border-bright);border-radius:6px;padding:24px;width:560px;max-width:95vw;max-height:88vh;overflow-y:auto;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
          <div style="flex:1;min-width:0">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
              <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:1px 6px;border-radius:2px;background:rgba(218,54,51,0.1);border:1px solid rgba(218,54,51,0.3);color:var(--red)">PIR</span>
              <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${priorityColor};font-weight:700">${escHtml(pir.priority || '')}</span>
              <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${escHtml(pir.status || '')}</span>
            </div>
            <div style="font-size:15px;font-weight:700;color:var(--text-bright)">${escHtml(pir.title)}</div>
          </div>
          <button onclick="document.getElementById('cluster-pir-modal').remove()" style="background:none;border:none;color:var(--text-dim);font-size:18px;cursor:pointer;margin-left:12px;">✕</button>
        </div>
        ${pir.description ? `<div style="font-size:12px;color:var(--text);margin-bottom:16px;line-height:1.6;padding:10px;background:var(--surface2);border-radius:4px;border:1px solid var(--border)">${escHtml(pir.description)}</div>` : ''}
        <div style="display:grid;gap:10px;">
          ${(crit.threat_actors||[]).length ? `<div>
            <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Threat Actors</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">${chips(crit.threat_actors)}</div>
          </div>` : ''}
          ${(crit.industries||[]).length ? `<div>
            <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Industries</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">${chips(crit.industries)}</div>
          </div>` : ''}
          ${(crit.countries||[]).length ? `<div>
            <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Countries</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">${chips(crit.countries)}</div>
          </div>` : ''}
          ${(crit.keywords||[]).length ? `<div>
            <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Keywords</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">${chips(crit.keywords)}</div>
          </div>` : ''}
          ${(crit.ttps||[]).length ? `<div>
            <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">TTPs</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">${chips(crit.ttps)}</div>
          </div>` : ''}
        </div>
        <div style="margin-top:16px;display:flex;justify-content:flex-end;">
          <button onclick="_clusterPirViewArticles()"
            style="font-size:11px;padding:5px 14px;background:rgba(47,129,247,0.08);border:1px solid rgba(47,129,247,0.3);color:var(--accent);border-radius:3px;cursor:pointer">
            View Matching Articles →
          </button>
        </div>
      </div>
    </div>`;

  document.body.insertAdjacentHTML('beforeend', html);
}

async function toggleCampaign(clusterId) {
  _campaignExpanded[clusterId] = !_campaignExpanded[clusterId];
  if (_campaignExpanded[clusterId] && !_campaignTrends[clusterId]) {
    await _loadTrend(clusterId);
  }
  _renderCampaigns();
}

function campaignHuntPack(clusterId) {
  const c = _campaignData.find(x => x.cluster_id === clusterId);
  if (!c) return;

  const pack = {
    cluster_id:        c.cluster_id,
    cluster_name:      c.summary_title || c.cluster_id,
    generated_at:      new Date().toISOString(),
    date_range:        { first_seen: c.first_seen, last_seen: c.last_seen },
    article_count:     c.size,
    dominant_tas:      c.dominant_tas      || [],
    dominant_industries: c.dominant_industries || [],
    dominant_countries:  c.dominant_countries  || [],
    attack_techniques: c.attack_techniques || [],
    cve_ids:           c.cve_ids           || [],
    iocs:              (c.iocs || []).map(ioc => ({ type: ioc.type, value: ioc.value })),
    matched_pirs:      c.matched_pirs      || [],
  };

  const blob = new Blob([JSON.stringify(pack, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `hunt-pack-${c.cluster_id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function openArticleById(articleId) {
  try {
    const res = await fetch(`/api/articles/${articleId}`, { headers: _authAndClientHeaders() });
    if (!res.ok) throw new Error(res.statusText);
    const a = await res.json();
    const key = storeArticle(a);
    openModal(key);
  } catch(e) {
    alert(`Could not load article: ${e.message}`);
  }
}

// ── GEOPOLITICAL OVERVIEW ─────────────────────────────────────────────────────

let _geopoliticalData = null;

async function loadGeopoliticalOverview() {
  const panel  = document.getElementById('geo-overview-body');
  const toggle = document.getElementById('geo-toggle-btn');
  if (!panel) return;

  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    if (toggle) toggle.textContent = '▾ Geopolitical Overview';
    if (_geopoliticalData) { _renderGeopolitical(_geopoliticalData); return; }
  }

  const days = document.getElementById('campaigns-days')?.value || 30;
  panel.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Loading geopolitical context…</div></div>';

  try {
    const res  = await fetch(`/api/intelligence/geopolitical?days=${days}`, { headers: _authAndClientHeaders() });
    if (!res.ok) throw new Error(res.statusText);
    _geopoliticalData = await res.json();
    _renderGeopolitical(_geopoliticalData);
  } catch(e) {
    panel.innerHTML = `<div class="intel-empty" style="color:var(--red)">Error: ${escHtml(e.message)}</div>`;
  }
}

function toggleGeopolitical() {
  const panel  = document.getElementById('geo-overview-body');
  const toggle = document.getElementById('geo-toggle-btn');
  if (!panel) return;
  if (panel.style.display === 'none') {
    loadGeopoliticalOverview();
  } else {
    panel.style.display = 'none';
    if (toggle) toggle.textContent = '▸ Geopolitical Overview';
  }
}

function _renderGeopolitical(data) {
  const panel = document.getElementById('geo-overview-body');
  if (!panel) return;

  const alerts = data.geopolitical_alerts || [];
  const nsa    = data.nation_state_activity || {};
  const stt    = data.sector_threat_trends  || {};
  const mob    = data.motivation_breakdown  || {};

  // Alerts
  let alertsHtml = '';
  if (alerts.length) {
    const cards = alerts.map(a => {
      const isInc  = a.includes('increased') || a.includes('converging') || a.includes('New threat');
      const color  = isInc ? 'rgba(218,54,51,0.12)' : 'rgba(255,140,0,0.1)';
      const border = isInc ? 'rgba(218,54,51,0.4)' : 'rgba(255,140,0,0.35)';
      const icon   = isInc ? '⚠' : 'ℹ';
      return `<div style="background:${color};border:1px solid ${border};border-radius:4px;padding:6px 10px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:var(--text)">${icon} ${escHtml(a)}</div>`;
    }).join('');
    alertsHtml = `<div style="margin-bottom:14px">
      <div style="font-size:10px;font-weight:700;color:var(--text-dim);letter-spacing:.08em;margin-bottom:6px">ALERTS</div>
      <div style="display:flex;flex-direction:column;gap:5px">${cards}</div>
    </div>`;
  }

  // Nation → sector heatmap
  const nations  = Object.keys(nsa).filter(n => n !== 'Unknown').sort();
  const sectors  = [...new Set(Object.values(nsa).flatMap(e => e.targeted_sectors || []))].sort();
  let heatmapHtml = '';
  if (nations.length && sectors.length) {
    const maxCount = Math.max(...nations.flatMap(n =>
      sectors.map(s => (nsa[n].targeted_sectors || []).filter(x => x === s).length)
    ), 1);

    const headerCols = sectors.map(s =>
      `<th style="font-size:9px;font-weight:600;color:var(--text-dim);padding:3px 6px;white-space:nowrap;text-align:center;max-width:80px;overflow:hidden;text-overflow:ellipsis" title="${escHtml(s)}">${escHtml(s.length > 12 ? s.slice(0,11)+'…' : s)}</th>`
    ).join('');

    const rows = nations.map(nation => {
      const entry = nsa[nation];
      const cells = sectors.map(sector => {
        const count = (entry.targeted_sectors || []).filter(s => s === sector).length;
        if (!count) return `<td style="padding:3px 6px;text-align:center;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04)"></td>`;
        const intensity = count / maxCount;
        const alpha = Math.round(intensity * 0.7 * 100) / 100 + 0.08;
        return `<td style="padding:3px 6px;text-align:center;background:rgba(218,54,51,${alpha});border:1px solid rgba(218,54,51,0.25);font-size:10px;font-family:'IBM Plex Mono',monospace;color:#fff;font-weight:700">${count}</td>`;
      }).join('');
      const motBadge = (entry.primary_motivations || []).slice(0,1).map(m =>
        `<span style="font-size:8px;background:rgba(83,52,131,0.2);border:1px solid rgba(83,52,131,0.4);color:#a78bdb;padding:1px 4px;border-radius:2px;margin-left:4px">${escHtml(m)}</span>`
      ).join('');
      return `<tr>
        <td style="padding:3px 8px;white-space:nowrap;font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--text);font-weight:600;border:1px solid rgba(255,255,255,0.05)">${escHtml(nation)}${motBadge}</td>
        ${cells}
      </tr>`;
    }).join('');

    heatmapHtml = `<div style="margin-bottom:14px">
      <div style="font-size:10px;font-weight:700;color:var(--text-dim);letter-spacing:.08em;margin-bottom:6px">NATION → SECTOR HEATMAP</div>
      <div style="overflow-x:auto">
        <table style="border-collapse:collapse;width:100%;font-size:10px">
          <thead><tr>
            <th style="padding:3px 8px;font-size:9px;font-weight:600;color:var(--text-dim);text-align:left;border:1px solid rgba(255,255,255,0.05)">Nation</th>
            ${headerCols}
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
  }

  // Motivation breakdown
  let motHtml = '';
  const motEntries = Object.entries(mob).sort((a,b) => b[1]-a[1]);
  if (motEntries.length) {
    const total = motEntries.reduce((s,[,v]) => s+v, 0) || 1;
    const bars = motEntries.map(([mot, cnt]) => {
      const pct = Math.round(cnt/total*100);
      const colors = { espionage:'#a78bdb', financial:'#ffaa00', ransomware:'#ff4444', hacktivism:'#34a853', sabotage:'#ff6b6b', unknown:'#555' };
      const col = colors[mot] || '#888';
      return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
        <span style="font-size:9px;font-family:'IBM Plex Mono',monospace;color:var(--text-dim);width:80px;flex-shrink:0">${escHtml(mot)}</span>
        <div style="flex:1;background:rgba(255,255,255,0.05);border-radius:2px;overflow:hidden;height:10px">
          <div style="width:${pct}%;background:${col};height:100%;border-radius:2px;opacity:0.8"></div>
        </div>
        <span style="font-size:9px;font-family:'IBM Plex Mono',monospace;color:var(--text-dim);width:30px;text-align:right">${cnt}</span>
      </div>`;
    }).join('');
    motHtml = `<div style="margin-bottom:14px">
      <div style="font-size:10px;font-weight:700;color:var(--text-dim);letter-spacing:.08em;margin-bottom:6px">MOTIVATION BREAKDOWN</div>
      ${bars}
    </div>`;
  }

  panel.innerHTML = `<div style="padding:12px 14px">
    ${alertsHtml}
    ${heatmapHtml}
    ${motHtml}
    <div style="font-size:9px;color:var(--text-dim);text-align:right;margin-top:4px">
      ${data.campaign_count || 0} campaigns · ${data.days || 30}d window
    </div>
  </div>`;
}
