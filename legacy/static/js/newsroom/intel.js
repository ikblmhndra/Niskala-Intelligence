// ── INTELLIGENCE TAB ──────────────────────────────────────────

let _intelLoaded = false;

function intelSwitchView(view) {
  ['clusters','scores','spikes','mitre','attackdb','pir','rfi','threatroom','iocmgmt','campaigns','riskmatrix'].forEach(v => {
    document.getElementById(`intel-view-${v}`).style.display   = v === view ? '' : 'none';
    document.getElementById(`intel-${v}-btn`).classList.toggle('active', v === view);
  });
}

async function loadIntelligence() {
  if (!_intelLoaded) {
    _intelLoaded = true;
    await Promise.all([loadSREntries(), loadSpikes()]);
  }
}

function intelSwitchViewAndLoad(view) {
  intelSwitchView(view);
  if (view === 'scores')     loadSREntries();
  if (view === 'spikes')     loadSpikes();
  // clusters: manual generate only — do not auto-load on tab switch
  if (view === 'attackdb')   loadAttackDB();
  if (view === 'pir')        loadPirs();
  if (view === 'rfi')        loadRfis();
  if (view === 'threatroom') loadTAGroups();
  if (view === 'iocmgmt')   { iocmgmtLoad(1); allowlistLoad(); fpAnalyticsLoad(); }
  if (view === 'campaigns')   loadCampaigns();
  if (view === 'riskmatrix')  loadRiskMatrix();
}

let _clusterData = [];
let _spikeEntities = [];

function _clusterSparkline(articles) {
  const dates = articles.map(a => a.posted_on ? new Date(a.posted_on).getTime() : null).filter(Boolean).sort((a,b)=>a-b);
  if (dates.length < 2) return '';
  const W = 64, H = 12, pad = 2;
  const min = dates[0], max = dates[dates.length - 1];
  const dots = dates.map(d => {
    const x = min === max ? W/2 : Math.round(pad + (d - min) / (max - min) * (W - pad*2));
    return `<circle cx="${x}" cy="${H/2}" r="1.5" fill="var(--accent)" opacity="0.7"/>`;
  }).join('');
  return `<svg class="cluster-sparkline" width="${W}" height="${H}" style="margin-right:6px"><line x1="${pad}" y1="${H/2}" x2="${W-pad}" y2="${H/2}" stroke="rgba(47,129,247,0.2)" stroke-width="1"/>${dots}</svg>`;
}

function _matchesSpike(c) {
  if (!_spikeEntities.length) return false;
  const hay = (c.cluster_name + ' ' + c.articles.map(a => a.title).join(' ')).toLowerCase();
  return _spikeEntities.some(e => hay.includes(e));
}

function renderClusterList() {
  const body       = document.getElementById('intel-clusters-body');
  const showSingle = document.getElementById('cluster-show-single')?.checked;
  const clusters   = _clusterData;

  if (!clusters.length) {
    body.innerHTML = '<div class="intel-empty">No multi-source clusters found for selected window</div>';
    return;
  }

  const html = clusters.map((c, idx) => {
    const isSingle  = c.source_count === 1;
    const confClass = `conf-${c.confidence}`;
    const srcList   = c.sources.map(s => `<span class="cluster-art-source">${escHtml(s)}</span>`).join(' ');
    const spark     = _clusterSparkline(c.articles);
    const timeline  = (c.first_date && c.last_date && c.first_date !== c.last_date)
      ? `<span class="cluster-art-date" style="margin-right:4px">${escHtml(c.first_date)} → ${escHtml(c.last_date)}</span>`
      : '';
    const arts = c.articles.map(a => `
      <a class="cluster-article-row" href="${escHtml(a.url)}" target="_blank" rel="noopener">
        <span class="cluster-art-title">${escHtml(a.title)}</span>
        <span class="cluster-art-source">${escHtml(a.source)}</span>
        <span class="cluster-art-date">${escHtml(a.posted_on)}</span>
      </a>`).join('');

    const spikeBadge    = _matchesSpike(c) ? `<span class="cluster-badge spike-alert">⚡ Active Spike</span>` : '';
    const reEmergedBadge = c.re_emerged    ? `<span class="cluster-badge re-emerged">↑ Re-emerging</span>` : '';

    const cardClass = isSingle && !showSingle ? 'cluster-card single-source' : 'cluster-card';
    if (isSingle && !showSingle) {
      // still render (for count) but dimmed — no expand interaction needed
    }

    return `
      <div class="${cardClass}">
        <div class="cluster-header" onclick="toggleCluster(${idx})">
          <span class="cluster-expand" id="cluster-exp-${idx}">▶</span>
          <div class="cluster-title">${escHtml(c.cluster_name)}</div>
          <div class="cluster-badges">
            ${spark}${timeline}
            ${srcList}
            <span class="cluster-badge ${confClass}">${c.source_count} source${c.source_count !== 1 ? 's' : ''}</span>
            <span class="cluster-badge">${c.article_count} articles</span>
            <span class="cluster-badge ${confClass}" style="text-transform:uppercase">${c.confidence}</span>
            ${spikeBadge}${reEmergedBadge}
          </div>
        </div>
        <div class="cluster-body" id="cluster-body-${idx}">${arts}</div>
      </div>`;
  }).join('');

  body.innerHTML = html;
}

async function loadClusters() {
  const body    = document.getElementById('intel-clusters-body');
  const days    = document.getElementById('intel-cluster-days').value;
  const thr     = document.getElementById('intel-cluster-threshold').value;
  const exclLR  = document.getElementById('cluster-excl-lowrel')?.checked ? 'true' : 'false';
  body.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Clustering articles… (first load may take a few seconds)</div></div>';

  try {
    const [clusterRes, spikeRes] = await Promise.all([
      fetch(`/api/clusters?days=${days}&threshold=${thr}&exclude_low_reliability=${exclLR}`, { headers: _authHeader() }),
      fetch('/api/spikes?lookback_days=7&z_threshold=2.0', { headers: _authHeader() }).catch(() => null),
    ]);

    const data     = await clusterRes.json();
    _clusterData   = data.clusters || [];

    if (spikeRes?.ok) {
      const sd = await spikeRes.json();
      _spikeEntities = [
        ...(sd.threat_actors || []).map(s => s.entity?.toLowerCase()).filter(Boolean),
        ...(sd.countries     || []).map(s => s.entity?.toLowerCase()).filter(Boolean),
      ];
    }

    document.getElementById('intel-clusters-count').textContent = _clusterData.length;
    document.getElementById('intel-clusters-footer').textContent =
      `${_clusterData.length} news cluster${_clusterData.length !== 1 ? 's' : ''} found`;

    renderClusterList();
  } catch (e) {
    body.innerHTML = `<div class="intel-empty">Error loading clusters: ${e.message}</div>`;
  }
}

function toggleCluster(idx) {
  const body = document.getElementById(`cluster-body-${idx}`);
  const exp  = document.getElementById(`cluster-exp-${idx}`);
  body.classList.toggle('open');
  exp.classList.toggle('open');
}

async function loadSourceScores() {
  const tbody  = document.getElementById('intel-scores-body');
  const footer = document.getElementById('intel-scores-footer');
  tbody.innerHTML = '<tr><td colspan="5" class="ta-td"><div class="loading-state"><div class="loading-spinner"></div></div></td></tr>';

  try {
    const res   = await fetch('/api/source-scores', { headers: _authHeader() });
    const data  = await res.json();
    const items = data.sources || [];
    footer.textContent = `${items.length} source${items.length !== 1 ? 's' : ''} scored`;

    tbody.innerHTML = items.map((s, i) => `
      <tr>
        <td class="ta-td ta-num">${i + 1}</td>
        <td class="ta-td ta-name">${escHtml(s.source)}</td>
        <td class="ta-td"><span class="admiral-grade admiral-${s.reliability_grade}">${s.reliability_grade}</span></td>
        <td class="ta-td" style="font-size:12px;color:var(--text)">${escHtml(s.reliability_label)}</td>
        <td class="ta-td">
          ${s.known
            ? '<span class="ta-source-badge">KNOWN</span>'
            : '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:9px;color:var(--text-dim)">unrated</span>'}
        </td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="ta-td" style="color:var(--red)">Error: ${e.message}</td></tr>`;
  }
}

async function loadSpikes() {
  const body    = document.getElementById('intel-spikes-body');
  const days    = document.getElementById('intel-spike-days').value;
  const z       = document.getElementById('intel-spike-z').value;
  const countEl = document.getElementById('intel-spikes-count');
  body.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Analyzing signals…</div></div>';

  try {
    const res  = await fetch(`/api/spikes?lookback_days=${days}&z_threshold=${z}`, { headers: _authHeader() });
    const data = await res.json();

    const allSpikes = [
      ...(data.overall      || []).map(s => ({ ...s, category: 'Overall Volume' })),
      ...(data.threat_actors|| []).map(s => ({ ...s, category: 'Threat Actor' })),
      ...(data.countries    || []).map(s => ({ ...s, category: 'Country' })),
      ...(data.industries   || []).map(s => ({ ...s, category: 'Industry' })),
    ].sort((a, b) => b.z_score - a.z_score);

    countEl.textContent = allSpikes.length || '0';

    if (!allSpikes.length) {
      body.innerHTML = '<div class="intel-empty">No anomalies detected in the selected window — baseline activity appears normal</div>';
      return;
    }

    const sections = {};
    allSpikes.forEach(s => {
      if (!sections[s.category]) sections[s.category] = [];
      sections[s.category].push(s);
    });

    body.innerHTML = Object.entries(sections).map(([cat, spikes]) => `
      <div class="spike-section-label">${escHtml(cat)} Spikes</div>
      ${spikes.map(s => `
        <div class="spike-row">
          <div class="spike-entity">${escHtml(s.entity || 'Overall')}</div>
          <span class="spike-meta">date: ${escHtml(s.date)}</span>
          <span class="spike-meta">count: <strong style="color:var(--text-bright)">${s.count}</strong></span>
          <span class="spike-meta">baseline: ${s.baseline_mean}/day</span>
          <span class="spike-badge ${s.severity}">${s.severity.toUpperCase()}</span>
          <span class="spike-zscore ${s.severity}">z=${s.z_score}σ</span>
        </div>`).join('')}
    `).join('');
  } catch (e) {
    body.innerHTML = `<div class="intel-empty" style="color:var(--red)">Error: ${e.message}</div>`;
  }
}

function escHtml(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

