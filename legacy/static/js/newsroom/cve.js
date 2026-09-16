// ── PANEL LOADERS ─────────────────────────────────────────
const PANEL_CONFIG = {
  apac:   { newsType: 'apac',       listId: 'apac-list',   renderFn: renderNewsItem, emptyMsg: 'No APAC news' },
  global: { newsType: ['global', 'Security Technology & Best Practices', 'Vendor Report Article', 'Data Breach Article', 'Tech Stack Article', 'OT Article'], listId: 'global-list', renderFn: renderNewsItem, emptyMsg: 'No global news' },
};

async function loadPanel(panelId) {
  const s   = state[panelId];
  const btn = document.getElementById(panelId + '-refresh');
  if (btn) btn.classList.add('spinning');

  if (panelId === 'indo') {
    const t = await loadLocalPanel(getClientCountries());
    if (btn) btn.classList.remove('spinning');
    return t;
  }

  const cfg = PANEL_CONFIG[panelId];
  const el  = document.getElementById(cfg.listId);
  el.innerHTML = loadingHTML();

  const data = await fetchArticles({ newsType: cfg.newsType, page: s.page });
  s.total = data.total;

  el.innerHTML = data.articles.length
    ? data.articles.map(cfg.renderFn).join('')
    : emptyHTML(cfg.emptyMsg);

  document.getElementById(panelId + '-count').textContent = `${data.total} items`;
  renderPager(panelId);
  if (btn) btn.classList.remove('spinning');
  return data.total;
}

async function loadLocalPanel(countries) {
  const s   = state.indo;
  const btn = document.getElementById('indo-refresh');
  const f   = getFilters();

  const params = new URLSearchParams({ page: s.page, page_size: PAGE_SIZE });
  if (countries && countries.length > 0) {
    countries.forEach(c => expandCountry(c).forEach(v => params.append('country', v)));
  }
  if (f.dateStart) params.set('posted_on_start', f.dateStart);
  if (f.dateEnd)   params.set('posted_on_end',   f.dateEnd);
  if (f.industry)  params.append('industry', f.industry);
  if (f.actor)     params.append('threat_actor', f.actor);
  if (f.search)    params.set('search', f.search);

  const title   = localPanelTitle(countries);
  const titleEl = document.getElementById('local-panel-title');
  if (titleEl) titleEl.textContent = title;
  const tipEl = document.getElementById('local-panel-countries-tip');
  if (tipEl) {
    if (countries && countries.length > 0) {
      tipEl.title = `Countries in this section: ${countries.join(', ')}`;
      tipEl.style.display = '';
    } else {
      tipEl.style.display = 'none';
    }
  }

  const el = document.getElementById('indo-list');
  el.innerHTML = loadingHTML(true);

  let data = { articles: [], total: 0 };
  try {
    const resp = await fetch(`/api/articles?${params}`);
    if (resp.ok) data = await resp.json();
  } catch (e) { console.error(e); }

  s.total = data.total;

  const emptyMsg = countries && countries.length > 0 ? `No ${title} news` : 'No news';
  el.innerHTML = data.articles.length
    ? data.articles.map(renderNewsItem).join('')
    : emptyHTML(emptyMsg, true);

  document.getElementById('indo-count').textContent = `${data.total} items`;
  renderPager('indo');
  if (btn) btn.classList.remove('spinning');
  return data.total;
}

function _renderAffected(affected) {
  if (!affected || !affected.length) return '<span style="color:var(--text-dim)">—</span>';
  const entries = affected.filter(e => Object.keys(e).length);
  if (!entries.length) return '<span style="color:var(--text-dim)">—</span>';

  // Table cell: product name + total range count only — no raw version strings
  const prodCount  = entries.length;
  const rangeCount = entries.reduce((n, e) => n + ((e[Object.keys(e)[0]] || []).length), 0);
  const prodNames  = entries.slice(0, 2).map(e => Object.keys(e)[0]).join(', ')
                   + (prodCount > 2 ? ` +${prodCount - 2}` : '');

  return `<div style="line-height:1.5">
    <span style="color:var(--text-dim);font-size:10px">${esc(prodNames)}</span>
    <div style="color:var(--orange);font-family:'IBM Plex Mono',monospace;font-size:10px;margin-top:1px">${rangeCount} range${rangeCount !== 1 ? 's' : ''}</div>
  </div>`;
}

// Modal: full affected version detail with clean formatting
function _renderAffectedFull(affected) {
  if (!affected || !affected.length) return '<span style="color:var(--text-dim)">—</span>';
  const entries = affected.filter(e => Object.keys(e).length);
  if (!entries.length) return '<span style="color:var(--text-dim)">—</span>';

  return entries.map(entry => {
    const prod = Object.keys(entry)[0];
    const vers = entry[prod] || [];
    if (!vers.length) return '';
    // Group consecutive pairs into range notation: >= X, <= Y → X – Y
    const formatted = [];
    let i = 0;
    while (i < vers.length) {
      const cur  = vers[i];
      const next = vers[i + 1];
      if (next && /^>=/.test(cur) && /^<=/.test(next)) {
        formatted.push(`${cur.replace(/^>=\s*/, '')} – ${next.replace(/^<=\s*/, '')}`);
        i += 2;
      } else {
        formatted.push(cur);
        i++;
      }
    }
    return `<div style="margin-bottom:6px">
      <span style="color:var(--text-dim);font-size:11px">${esc(prod)}:</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--orange);margin-left:6px">${formatted.map(v => esc(v)).join(', ')}</span>
    </div>`;
  }).filter(Boolean).join('');
}

const _SEV_TIER  = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 };
const _TIER_SEV  = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const _SEV_COLOR = { CRITICAL: 'var(--red)', HIGH: 'var(--orange)', MEDIUM: 'var(--accent3)', LOW: 'var(--accent)' };

function _effectiveSeverity(c) {
  const base = (c.cve_severity || '').toUpperCase();
  if (!c.poc_available) return { base, effective: base, escalated: false };
  const hasWeaponized = (c.pocs || []).some(p => p.type === 'exploit' || p.type === 'metasploit_module');
  if (!hasWeaponized) return { base, effective: base, escalated: false };
  const tier = _SEV_TIER[base] ?? -1;
  if (tier < 0 || tier >= 3) return { base, effective: base, escalated: false };
  return { base, effective: _TIER_SEV[tier + 1], escalated: true };
}

function _renderNewsMentionsBadge(c) {
  const n = c.news_mentions_count || 0;
  if (c.false_positive || n === 0) return `<span style="color:var(--text-dim);font-size:11px">—</span>`;
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;background:rgba(61,201,175,0.12);border:1px solid rgba(61,201,175,0.35);color:var(--green);padding:2px 7px;border-radius:3px;cursor:default" title="${n} article(s) mention this CVE">📰 ${n}</span>`;
}

function _renderNewsMentionsModal(c) {
  const mentions = c.news_mentions || [];
  if (!mentions.length) return '<span style="color:var(--text-dim);font-size:12px">No articles mention this CVE.</span>';
  return mentions.map(m =>
    `<div style="margin-bottom:6px">
      <a href="${esc(m.url)}" target="_blank" class="cve-ref-link">${esc(m.title)}</a>
    </div>`
  ).join('');
}

function _renderEpssBadge(c) {
  if (c.epss_score == null) return `<span style="color:var(--text-dim);font-size:11px">—</span>`;
  const pct  = (c.epss_score * 100).toFixed(2);
  const perc = c.epss_percentile != null ? Math.round(c.epss_percentile * 100) : null;
  const col  = c.epss_score >= 0.5 ? 'var(--red)'
             : c.epss_score >= 0.1 ? 'var(--orange)'
             : 'var(--accent)';
  const tip  = perc != null
    ? `EPSS: ${pct}% probability of exploitation · ${perc}th percentile`
    : `EPSS: ${pct}% probability of exploitation`;
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:${col};background:rgba(110,124,255,0.08);border:1px solid rgba(110,124,255,0.35);padding:2px 7px;border-radius:3px;cursor:default;white-space:nowrap" title="${esc(tip)}">${pct}%</span>`;
}

function renderCveRow(c) {
  const { base, effective, escalated } = _effectiveSeverity(c);
  const color     = _SEV_COLOR[effective] || 'var(--text-dim)';
  const baseColor = _SEV_COLOR[base]      || 'var(--text-dim)';
  const score     = c.cve_score ? Number(c.cve_score).toFixed(1) : 'N/A';
  const _hasAdj   = c.adjusted_risk_score != null && c.adjusted_risk_score !== c.cve_score
                    && ((c.tech_exposure && c.tech_exposure !== 'internal') || (c.epss_multiplier && c.epss_multiplier !== 1.0));
  const adjScore  = _hasAdj ? Number(c.adjusted_risk_score).toFixed(1) : null;
  const expMult   = { public: '1.5×', both: '1.25×', internal: '1×' };
  const expColor  = { public: 'var(--red)', both: 'var(--orange)', internal: color };
  const _adjColor = c.tech_exposure === 'public' ? 'var(--red)' : c.tech_exposure === 'both' ? 'var(--orange)' : 'var(--accent3)';
  const _epssLabel    = c.epss_multiplier >= 1.3 ? 'EPSS≥50% 1.3×' : c.epss_multiplier >= 1.15 ? 'EPSS≥10% 1.15×' : null;
  const _hostingLabel = c.hosting_multiplier != null && c.hosting_multiplier < 1.0 ? `${c.hosting_type||'saas'} 0.8×` : null;
  const _adjTooltip = adjScore
    ? `Raw CVSS: ${score} × ${expMult[c.tech_exposure]||'1×'} (${c.tech_exposure||'internal'})${_epssLabel ? ' × ' + _epssLabel : ''}${_hostingLabel ? ' × ' + _hostingLabel : ''} = ${adjScore}`
    : '';
  const summary   = c.summary && c.summary.length > 130 ? c.summary.slice(0, 130) + '…' : (c.summary || '—');
  const published = c.published ? c.published.split('T')[0] : '—';
  const hasSol    = c.solutions && c.solutions !== 'No solution yet' && c.solutions.trim().length > 0;
  const cisaBadge = c.cisa_kev
    ? `<span class="cve-poc-badge" style="background:rgba(218,54,51,.15);color:var(--red);border-color:rgba(218,54,51,.5)"
            title="CISA KEV: ${esc((c.cisa_kev_name||'').replace(/"/g,'&quot;'))} — Added ${esc(c.cisa_kev_date_added||'')}">🔴 KEV</span>`
    : '';
  const pocBadge  = c.poc_available
    ? `<span class="cve-poc-badge">⚡ POC</span>`
    : `<span style="color:var(--text-dim);font-size:11px">—</span>`;
  const fpBadge   = c.false_positive
    ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--red);border:1px solid rgba(218,54,51,0.5);border-radius:2px;padding:1px 4px;margin-left:4px">FP</span>`
    : '';
  const sevCell   = escalated
    ? `<span style="color:${baseColor};font-weight:600">${base}</span><span style="color:var(--text-dim);font-size:10px;margin:0 3px">→</span><span style="color:${color};font-weight:700">${effective}</span>`
    : `<span style="color:${color};font-weight:600">${esc(c.cve_severity || '—')}</span>`;
  const isAckedFP  = !!_cveAckMap[c.cve_id];
  const ackBadge   = isAckedFP
    ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--green);border:1px solid rgba(61,201,175,0.5);border-radius:2px;padding:1px 4px;margin-left:4px" title="Acknowledged by ${esc(_cveAckMap[c.cve_id])}">✓ ACK</span>`
    : '';
  const edbChecked = c.exploit_db_checked_at
    ? `<span title="Last checked: ${esc(c.exploit_db_checked_at.split('T')[0])}" style="font-size:9px;color:var(--text-dim)">✓</span>`
    : '';
  const edbBtn = c.false_positive ? '' :
    `<button class="pir-btn" onclick="event.stopPropagation();runSingleExploitLookup(this,'${esc(c.cve_id)}')"
             title="Lookup on Exploit-DB" style="font-size:9px;border-color:rgba(227,179,65,.4);color:#E3B341">
       ⚡${edbChecked}
     </button>`;
  const actionBtn = c.false_positive
    ? `<button class="pir-btn" onclick="event.stopPropagation();unmarkCveFP('${esc(c.cve_id)}')" style="font-size:9px;color:var(--text-dim);border-color:var(--border)">Unmark FP</button>`
    : isAckedFP
      ? `<button class="pir-btn" onclick="event.stopPropagation();markCveFP('${esc(c.cve_id)}')" style="font-size:9px">Mark FP</button>`
      : `<button class="pir-btn" disabled title="Acknowledge this CVE first before marking as False Positive" style="font-size:9px;opacity:.4;cursor:not-allowed">Mark FP</button>`;
  const cbChecked  = _cveSelected.has(c.cve_id) ? 'checked' : '';
  const cbDisabled = c.false_positive
    ? 'disabled title="False Positive CVEs cannot be selected"'
    : '';
  const rowStyle  = c.false_positive ? 'opacity:0.45;cursor:pointer' : 'cursor:pointer';
  return `<tr style="${rowStyle}" data-cve-id="${esc(c.cve_id)}" onclick="openCveModal('${esc(c.cve_id)}')">
    <td style="text-align:center;width:32px" onclick="event.stopPropagation()">
      <input type="checkbox" class="cve-select-cb" data-cve-id="${esc(c.cve_id)}" ${cbChecked} ${cbDisabled} onchange="toggleCveSelect(this)">
    </td>
    <td style="font-family:'IBM Plex Mono',monospace;font-size:11px;white-space:nowrap" onclick="event.stopPropagation()">
      <a href="${esc(c.link)}" target="_blank" style="color:var(--accent);text-decoration:none">${esc(c.cve_id)}</a>${fpBadge}${ackBadge}
    </td>
    <td style="font-size:11px;text-transform:uppercase;white-space:nowrap">${esc(c.tech)}</td>
    <td style="font-family:'Share Tech Mono',monospace;color:${color};white-space:nowrap" title="${_adjTooltip}">
      ${adjScore
        ? `<span style="color:var(--text-dim);font-size:10px;text-decoration:line-through">${score}</span> <span style="color:${_adjColor};font-weight:700">${adjScore}</span>`
        : score}
    </td>
    <td style="font-size:11px;white-space:nowrap">${sevCell}</td>
    <td style="max-width:280px;font-size:12px;color:var(--text-bright);line-height:1.4">${esc(summary)}</td>
    <td style="font-size:11px;max-width:180px">${_renderAffected(c.affected)}</td>
    <td style="font-size:11px;color:var(--text-dim);white-space:nowrap">${published}</td>
    <td style="font-size:11px;white-space:nowrap;color:${hasSol ? 'var(--accent)' : 'var(--text-dim)'}">${hasSol ? 'Available' : 'Pending'}</td>
    <td style="white-space:nowrap">${cisaBadge}${pocBadge}</td>
    <td style="white-space:nowrap">${_renderNewsMentionsBadge(c)}</td>
    <td style="white-space:nowrap">${_renderEpssBadge(c)}</td>
    <td style="white-space:nowrap" onclick="event.stopPropagation()">${actionBtn}</td>
  </tr>`;
}


const _cveDataMap = {};   // cve_id → full CVE object for modal
let _cveAckMap    = {};   // cve_id → acknowledged_by (populated on loadCvePanel)
const _cveSelected = new Set();  // cve_ids currently selected for email

function _patchCveRowAck(cveId, analyst) {
  const row = document.querySelector(`tr[data-cve-id="${CSS.escape(cveId)}"]`);
  if (!row) return;

  const ackBadge = `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--green);border:1px solid rgba(61,201,175,0.5);border-radius:2px;padding:1px 4px;margin-left:4px" title="Acknowledged by ${esc(analyst)}">✓ ACK</span>`;

  // Cell 1 (checkbox): enable + update title
  const cb = row.querySelector('input.cve-select-cb');
  if (cb) { cb.disabled = false; cb.title = ''; }

  // Cell 2 (CVE ID link): inject ack badge after existing badges
  const linkTd = row.cells[1];
  if (linkTd && !linkTd.querySelector('[title^="Acknowledged"]')) {
    linkTd.insertAdjacentHTML('beforeend', ackBadge);
  }

  // Last cell (action): swap disabled "Mark FP" → enabled
  const actionTd = row.cells[row.cells.length - 1];
  if (actionTd) {
    actionTd.innerHTML = `<button class="pir-btn" onclick="event.stopPropagation();markCveFP('${esc(cveId)}')" style="font-size:9px">Mark FP</button>`;
  }
}
let _cveSelectedTech = null;     // tech of first selected CVE — all others must match
let _cveTechLoaded = false;
let _cveSortBy  = 'published';
let _cveSortDir = 'desc';
let _cvePage    = 1;
let _cveTotal   = 0;

function cveSortBy(col) {
  if (_cveSortBy === col) {
    _cveSortDir = _cveSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    _cveSortBy  = col;
    _cveSortDir = (col === 'published' || col === 'epss') ? 'desc' : 'asc';
  }
  _updateCveSortUI();
  loadCvePanel();
}

function _updateCveSortUI() {
  ['tech','severity','published','epss'].forEach(col => {
    const th = document.getElementById('cve-th-' + col);
    const si = document.getElementById('cve-si-' + col);
    if (!th || !si) return;
    const active = _cveSortBy === col;
    th.classList.toggle('sort-active', active);
    si.textContent = active ? (_cveSortDir === 'asc' ? '↑' : '↓') : '↕';
  });
}

function toggleCveSelect(cb) {
  const id = cb.dataset.cveId;
  if (cb.checked) {
    _cveSelected.add(id);
  } else {
    _cveSelected.delete(id);
  }
  _updateCveBulkButtons();
}

function toggleAllCveSelect(masterCb) {
  if (masterCb.checked) {
    document.querySelectorAll('.cve-select-cb:not([disabled])').forEach(cb => {
      cb.checked = true;
      _cveSelected.add(cb.dataset.cveId);
    });
  } else {
    document.querySelectorAll('.cve-select-cb:not([disabled])').forEach(cb => {
      cb.checked = false;
      _cveSelected.delete(cb.dataset.cveId);
    });
  }
  _updateCveBulkButtons();
}

function _updateCveBulkButtons() {
  const n        = _cveSelected.size;
  const countEl  = document.getElementById('cve-select-count');
  const emailBtn = document.getElementById('cve-draft-email-btn');
  const fpBtn    = document.getElementById('cve-bulk-fp-btn');
  const ackBtn   = document.getElementById('cve-bulk-ack-btn');
  const nEl      = document.getElementById('cve-select-n');
  if (!countEl) return;
  if (n > 0) {
    nEl.textContent       = n;
    countEl.style.display = '';
    const allAcked   = [..._cveSelected].every(id => !!_cveAckMap[id]);
    const anyUnacked = [..._cveSelected].some(id => !_cveAckMap[id]);
    if (ackBtn) ackBtn.style.display = anyUnacked ? '' : 'none';
    // Bulk FP only when all selected CVEs are acknowledged
    fpBtn.style.display = allAcked ? '' : 'none';
    // Draft Email only enabled when all selected are same tech
    const techs = new Set([..._cveSelected].map(id => (_cveDataMap[id]?.tech || '').toLowerCase()));
    emailBtn.style.display = '';
    emailBtn.disabled      = techs.size > 1;
    emailBtn.title         = techs.size > 1 ? 'Draft Email requires all selected CVEs to share the same tech stack' : '';
  } else {
    countEl.style.display  = 'none';
    if (ackBtn) ackBtn.style.display = 'none';
    fpBtn.style.display    = 'none';
    emailBtn.style.display = 'none';
    emailBtn.disabled      = false;
    emailBtn.title         = '';
  }
}

// keep old name as alias so existing callers don't break
const _updateCveEmailBtn = _updateCveBulkButtons;

function draftCveEmail() {
  const cve_ids = [..._cveSelected];
  if (!cve_ids.length) return;

  requireTAAuth(async ({ pass }) => {
    closeAuthModal();
    const btn = document.getElementById('cve-draft-email-btn');
    const origText = btn ? btn.textContent : '✉ Draft Email';
    if (btn) { btn.textContent = '⏳ Generating…'; btn.disabled = true; }

    try {
      const resp = await fetch('/api/cve/draft-email', {
        method: 'POST',
        headers: _authAndClientHeaders({
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + pass,
        }),
        body: JSON.stringify({ cve_ids }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        _cveToast(`Email failed: ${err.detail}`, false);
        return;
      }

      const data = await resp.json();
      const label = data.method === 'smtp' ? '✉ Sent via SMTP' : '✉ Draft created (Outlook)';
      _cveToast(`${label} — ${data.cve_count} CVE(s) · ${data.subject}`, true);
      _cveSelected.clear();
      _updateCveBulkButtons();
      document.querySelectorAll('.cve-select-cb').forEach(cb => { cb.checked = false; });
      const masterCb = document.getElementById('cve-select-all');
      if (masterCb) masterCb.checked = false;
    } catch(e) {
      _cveToast(`Network error: ${e.message}`, false);
    } finally {
      if (btn) { btn.textContent = origText; btn.disabled = false; }
    }
  }, { bypassCache: true });
}

async function _loadCveTechOptions() {
  if (_cveTechLoaded) return;
  try {
    // Prefer techstack collection; fall back to distinct values in cve_tracker
    const resp = await fetch('/api/techstack?page_size=500', { headers: _authAndClientHeaders() });
    if (!resp.ok) throw new Error();
    const d = await resp.json();
    const sel = document.getElementById('cve-tech');
    d.items.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.name; opt.textContent = t.name;
      sel.appendChild(opt);
    });
    _cveTechLoaded = true;
  } catch(_) {}
}

function cveResetFilters() {
  document.getElementById('cve-search').value     = '';
  document.getElementById('cve-severity').value   = '';
  document.getElementById('cve-tech').value       = '';
  document.getElementById('cve-date-start').value = '';
  document.getElementById('cve-date-end').value   = '';
  document.getElementById('cve-show-fp').checked  = false;
  const ackCb = document.getElementById('cve-unacked-filter');
  if (ackCb) ackCb.checked = false;
  loadCvePanel();
}

// ── CVE BULK ACKNOWLEDGE ─────────────────────────────────
function bulkAcknowledgeCve() {
  const cve_ids = [..._cveSelected].filter(id => !_cveAckMap[id]);
  if (!cve_ids.length) return;

  showConfirmModal({
    title:   'Bulk Acknowledge CVEs',
    okLabel: '✓ Acknowledge',
    okColor: 'var(--green)',
    body: `<p style="font-size:13px;color:var(--text);line-height:1.7">
      Acknowledge <strong style="color:var(--accent)">${cve_ids.length} CVE${cve_ids.length > 1 ? 's' : ''}</strong>?<br>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${cve_ids.slice(0, 10).map(id => esc(id)).join(', ')}${cve_ids.length > 10 ? ` … +${cve_ids.length - 10} more` : ''}</span>
    </p>`,
    onConfirm: () => requireTAAuth(async ({ pass, analyst }) => {
      try {
        const resp = await fetch('/api/cve/bulk-acknowledge', {
          method: 'POST',
          headers: _authAndClientHeaders({ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pass }),
          body: JSON.stringify({ cve_ids, analyst_name: analyst }),
        });
        if (resp.status === 401) { _authFailed(); return; }
        if (!resp.ok) throw new Error(await resp.text());
        const d = await resp.json();
        _cveToast(`${d.acknowledged} CVE${d.acknowledged !== 1 ? 's' : ''} acknowledged.`, true);
        cve_ids.forEach(id => {
          _cveAckMap[id] = analyst;
          _patchCveRowAck(id, analyst);
        });
        _cveSelected.clear();
        _updateCveBulkButtons();
        document.querySelectorAll('.cve-select-cb').forEach(cb => { cb.checked = false; });
        const masterCb = document.getElementById('cve-select-all');
        if (masterCb) masterCb.checked = false;
      } catch (e) {
        _cveToast(`Bulk acknowledge failed: ${e.message}`, false);
      }
    }, { analystName: true, subtitle: `Bulk acknowledge ${cve_ids.length} CVE(s)`, bypassCache: true }),
  });
}

// ── CVE FALSE POSITIVE ───────────────────────────────────
function bulkMarkCveFP() {
  const cve_ids = [..._cveSelected];
  if (!cve_ids.length) return;

  showConfirmModal({
    title:   'Bulk Mark as False Positive',
    okLabel: '⚑ Mark FP',
    okColor: 'var(--red)',
    body: `<p style="font-size:13px;color:var(--text);line-height:1.7">
      Mark <strong style="color:var(--red)">${cve_ids.length} CVE${cve_ids.length > 1 ? 's' : ''}</strong> as False Positive?<br>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${cve_ids.slice(0, 10).map(id => esc(id)).join(', ')}${cve_ids.length > 10 ? ` … +${cve_ids.length - 10} more` : ''}</span>
    </p>`,
    onConfirm: () => requireTAAuth(async (pass) => {
      try {
        const resp = await fetch('/api/cve/bulk-false-positive', {
          method: 'POST',
          headers: _authAndClientHeaders({ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pass }),
          body: JSON.stringify({ cve_ids }),
        });
        if (resp.status === 401) { _authFailed(); return; }
        if (!resp.ok) throw new Error(await resp.text());
        _cveToast(`${cve_ids.length} CVE${cve_ids.length > 1 ? 's' : ''} marked as False Positive.`, true);
        _cveSelected.clear();
        _updateCveBulkButtons();
        loadCvePanel();
      } catch (e) {
        _cveToast(`Bulk FP failed: ${e.message}`, false);
      }
    }),
  });
}

function markCveFP(cveId) {
  requireTAAuth(async ({ pass }) => {
    let r;
    try {
      r = await fetch(`/api/cve/${encodeURIComponent(cveId)}/false-positive`, {
        method: 'POST',
        headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + pass }),
      });
    } catch(e) { _cveToast(`Network error: ${e.message}`, false); return; }
    if (r.ok) { closeAuthModal(); _cveToast(`${cveId} marked as False Positive.`, true); loadCvePanel(); }
    else if (r.status === 401) { _authFailed(); }
    else { _cveToast(`Server error ${r.status}`, false); }
  }, { subtitle: `Mark ${cveId} as False Positive` });
}

function unmarkCveFP(cveId) {
  requireTAAuth(async ({ pass }) => {
    let r;
    try {
      r = await fetch(`/api/cve/${encodeURIComponent(cveId)}/false-positive`, {
        method: 'DELETE',
        headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + pass }),
      });
    } catch(e) { _cveToast(`Network error: ${e.message}`, false); return; }
    if (r.ok) { closeAuthModal(); _cveToast(`${cveId} FP flag removed.`, true); loadCvePanel(); }
    else if (r.status === 401) { _authFailed(); }
    else { _cveToast(`Server error ${r.status}`, false); }
  }, { subtitle: `Remove False Positive flag from ${cveId}` });
}

// ── EXPLOIT-DB LOOKUP ────────────────────────────────────
async function runExploitDbLookup(btn) {
  requireTAAuth(async (pass) => {
    btn.disabled  = true;
    btn.textContent = '⏳ Checking…';
    try {
      const resp = await fetch('/api/cve/exploit-lookup', {
        method: 'POST',
        headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + pass }),
      });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) throw new Error(await resp.text());
      const d = await resp.json();
      _cveToast(
        `Exploit-DB: checked ${d.checked} CVEs · ${d.with_exploits} with exploits · ${d.total_found} entries saved`,
        true,
      );
      loadCvePanel();
    } catch (e) {
      _cveToast(`Exploit-DB lookup failed: ${e.message}`, false);
    } finally {
      btn.disabled  = false;
      btn.textContent = '⚡ Exploit-DB Lookup';
    }
  });
}

async function runCisaLookup(btn) {
  requireTAAuth(async (pass) => {
    btn.disabled    = true;
    btn.textContent = '⏳ Checking…';
    try {
      const resp = await fetch('/api/cve/cisa-lookup', {
        method: 'POST',
        headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + pass }),
      });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) throw new Error(await resp.text());
      const d = await resp.json();
      _cveToast(
        `CISA KEV: checked ${d.checked} CVEs against ${d.catalog_size} catalog entries · ${d.matched} match${d.matched !== 1 ? 'es' : ''} tagged "Exploited in the Wild"`,
        d.matched > 0,
      );
      loadCvePanel();
    } catch (e) {
      _cveToast(`CISA KEV lookup failed: ${e.message}`, false);
    } finally {
      btn.disabled    = false;
      btn.textContent = '🔴 CISA KEV Lookup';
    }
  });
}

async function runEpssLookup(btn) {
  requireTAAuth(async (pass) => {
    btn.disabled    = true;
    btn.textContent = '⏳ Fetching…';
    try {
      const resp = await fetch('/api/cve/epss-lookup', {
        method: 'POST',
        headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + pass }),
      });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) throw new Error(await resp.text());
      const d = await resp.json();
      _cveToast(
        `EPSS: fetched scores for ${d.scored} of ${d.checked} CVEs · ${d.no_data} had no EPSS data`,
        d.scored > 0,
      );
      loadCvePanel();
    } catch (e) {
      _cveToast(`EPSS lookup failed: ${e.message}`, false);
    } finally {
      btn.disabled    = false;
      btn.textContent = '📊 EPSS Lookup';
    }
  });
}

async function exportCveExcel(btn) {
  requireTAAuth(async (pass) => {
    btn.disabled    = true;
    btn.textContent = '⏳ Exporting…';
    try {
      const dateStart = document.getElementById('cve-date-start')?.value  || '';
      const dateEnd   = document.getElementById('cve-date-end')?.value    || '';
      const search    = document.getElementById('cve-search')?.value.trim() || '';
      const severity  = document.getElementById('cve-severity')?.value    || '';
      const tech      = document.getElementById('cve-tech')?.value        || '';
      const includeFp = document.getElementById('cve-show-fp')?.checked || false;
      const unackedOnly = document.getElementById('cve-unacked-filter')?.checked || false;
      const params    = new URLSearchParams();
      if (dateStart)   params.set('date_start', dateStart);
      if (dateEnd)     params.set('date_end',   dateEnd);
      if (search)      params.set('search',     search);
      if (severity)    params.set('severity',   severity);
      if (tech)        params.set('tech',       tech);
      if (includeFp)   params.set('include_fp', 'true');
      if (unackedOnly) params.set('ack_filter', 'unacked');
      const url  = '/api/cve/export' + (params.toString() ? '?' + params.toString() : '');
      const resp = await fetch(url, { headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + pass }) });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) throw new Error(await resp.text());
      const blob     = await resp.blob();
      const anchor   = document.createElement('a');
      anchor.href    = URL.createObjectURL(blob);
      const cd       = resp.headers.get('Content-Disposition') || '';
      const match    = cd.match(/filename="([^"]+)"/);
      anchor.download = match ? match[1] : 'CVE_Tracker_Export.xlsx';
      anchor.click();
      URL.revokeObjectURL(anchor.href);
    } catch (e) {
      _cveToast(`Export failed: ${e.message}`, false);
    } finally {
      btn.disabled    = false;
      btn.textContent = '⬇ Export Excel';
    }
  });
}

async function runSingleExploitLookup(btn, cveId) {
  requireTAAuth(async (pass) => {
    btn.disabled = true;
    const orig   = btn.innerHTML;
    btn.innerHTML = '⏳';
    try {
      const resp = await fetch(`/api/cve/${encodeURIComponent(cveId)}/exploit-lookup`, {
        method: 'POST',
        headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + pass }),
      });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) throw new Error(await resp.text());
      const d = await resp.json();
      _cveToast(
        d.found > 0
          ? `${cveId}: ${d.found} exploit(s) found on Exploit-DB`
          : `${cveId}: no exploits found on Exploit-DB`,
        d.found > 0,
      );
      loadCvePanel();
    } catch (e) {
      _cveToast(`Exploit-DB lookup failed: ${e.message}`, false);
      btn.innerHTML = orig;
      btn.disabled  = false;
    }
  });
}

// ── CVSS VECTOR EXPANDER ──────────────────────────────────
function expandCvssVector(vector) {
  if (!vector) return '';
  const METRIC_NAMES = {
    'AV':'Attack Vector','AC':'Attack Complexity','PR':'Privileges Required',
    'UI':'User Interaction','S':'Scope','C':'Confidentiality Impact',
    'I':'Integrity Impact','A':'Availability Impact',
    'AT':'Attack Requirements','VC':'Vuln. Confidentiality','VI':'Vuln. Integrity',
    'VA':'Vuln. Availability','SC':'Sub. Confidentiality','SI':'Sub. Integrity',
    'SA':'Sub. Availability','Au':'Authentication',
  };
  const METRIC_VALUES = {
    'AV':{'N':'Network','A':'Adjacent Network','L':'Local','P':'Physical'},
    'AC':{'L':'Low','M':'Medium','H':'High'},
    'PR':{'N':'None','L':'Low','H':'High'},
    'UI':{'N':'None','R':'Required'},
    'S': {'U':'Unchanged','C':'Changed'},
    'C': {'N':'None','L':'Low','H':'High','P':'Partial','C':'Complete'},
    'I': {'N':'None','L':'Low','H':'High','P':'Partial','C':'Complete'},
    'A': {'N':'None','L':'Low','H':'High','P':'Partial','C':'Complete'},
    'Au':{'N':'None','S':'Single','M':'Multiple'},
    'AT':{'N':'None','P':'Present'},
    'VC':{'N':'None','L':'Low','H':'High'},'VI':{'N':'None','L':'Low','H':'High'},
    'VA':{'N':'None','L':'Low','H':'High'},'SC':{'N':'None','L':'Low','H':'High'},
    'SI':{'N':'None','L':'Low','H':'High','S':'Safety'},
    'SA':{'N':'None','L':'Low','H':'High','S':'Safety'},
  };
  const VAL_COLOR = {
    'None':'var(--text-dim)','Low':'var(--accent3)','Medium':'var(--accent3)',
    'High':'var(--orange)','Complete':'var(--red)','Partial':'var(--accent3)',
    'Network':'var(--red)','Adjacent Network':'var(--accent3)',
    'Local':'var(--accent)','Physical':'var(--accent)',
    'Changed':'var(--red)','Unchanged':'var(--text-dim)',
    'Required':'var(--accent3)','Single':'var(--accent3)','Multiple':'var(--orange)',
    'Present':'var(--orange)',
  };
  const clean = vector.replace(/^CVSS:[0-9.]+\//, '');
  const rows = clean.split('/').map(pair => {
    const ci = pair.indexOf(':');
    if (ci === -1) return '';
    const key = pair.slice(0, ci), val = pair.slice(ci + 1);
    const name  = METRIC_NAMES[key]  || key;
    const label = (METRIC_VALUES[key] || {})[val] || val;
    const color = VAL_COLOR[label] || 'var(--text-bright)';
    return `<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);padding:2px 14px 2px 0;white-space:nowrap">${esc(name)}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${color};padding:2px 0;font-weight:600">${esc(label)}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);padding:2px 0 2px 10px;opacity:0.55">(${esc(key)}:${esc(val)})</td>
    </tr>`;
  }).filter(Boolean).join('');
  return `<div style="margin-bottom:6px"><span class="cve-cvss">${esc(vector)}</span></div>`
       + `<table style="border-collapse:collapse;margin-top:4px">${rows}</table>`;
}

// ── CVE DETAIL MODAL ─────────────────────────────────────
function openCveModal(cveId) {
  const c = _cveDataMap[cveId];
  if (!c) return;
  const SEV_COLOR = { CRITICAL: 'var(--red)', HIGH: 'var(--orange)', MEDIUM: 'var(--accent3)', LOW: 'var(--accent)' };
  const color  = SEV_COLOR[c.cve_severity] || 'var(--text-dim)';
  const score  = c.cve_score ? Number(c.cve_score).toFixed(1) : 'N/A';
  const published = c.published ? c.published.split('T')[0] : '—';
  const hasSol = c.solutions && c.solutions !== 'No solution yet' && c.solutions.trim().length > 0;
  const _expMult  = { public: '1.5×', both: '1.25×', internal: '1×' };
  const _expColor = { public: 'var(--red)', both: 'var(--orange)', internal: color };
  const _mHasAdj  = c.adjusted_risk_score != null && c.adjusted_risk_score !== c.cve_score
                    && ((c.tech_exposure && c.tech_exposure !== 'internal') || (c.epss_multiplier && c.epss_multiplier !== 1.0));
  const modalAdj  = _mHasAdj ? Number(c.adjusted_risk_score).toFixed(1) : null;
  const _mAdjColor = c.tech_exposure === 'public' ? 'var(--red)' : c.tech_exposure === 'both' ? 'var(--orange)' : 'var(--accent3)';
  const _mEpssLabel    = c.epss_multiplier >= 1.3 ? 'EPSS≥50% ×1.3' : c.epss_multiplier >= 1.15 ? 'EPSS≥10% ×1.15' : null;
  const _mHostingLabel = c.hosting_multiplier != null && c.hosting_multiplier < 1.0 ? `${c.hosting_type||'saas'} ×0.8` : null;
  const _mAdjTip  = modalAdj
    ? `${score} × ${_expMult[c.tech_exposure]||'1×'} (${c.tech_exposure||'internal'})${_mEpssLabel ? ' × ' + _mEpssLabel : ''}${_mHostingLabel ? ' × ' + _mHostingLabel : ''} = ${modalAdj}`
    : '';
  const modalScoreHtml = modalAdj
    ? `<span style="color:var(--text-dim);font-family:'Share Tech Mono',monospace;font-size:11px;text-decoration:line-through">${score}</span>
       <span style="color:${_mAdjColor};font-family:'Share Tech Mono',monospace;font-weight:700;font-size:13px" title="${_mAdjTip}">${modalAdj} ▲</span>`
    : `<span style="color:${color};font-family:'Share Tech Mono',monospace;font-weight:700;font-size:13px">${score}</span>`;

  // Dot color
  const dot = document.getElementById('cve-modal-dot');
  dot.style.background  = color;
  dot.style.boxShadow   = `0 0 6px ${color}`;

  // Title
  document.getElementById('cve-modal-title').textContent = c.cve_id;
  document.getElementById('cve-modal-nvd-link').href = c.link || '#';

  // Meta bar
  document.getElementById('cve-modal-meta').innerHTML = `
    ${modalScoreHtml}
    <span class="modal-meta-item" style="color:${color};font-size:11px;font-weight:600">${esc(c.cve_severity || '—')}</span>
    <span class="modal-meta-item" style="color:var(--text-dim);font-size:11px">·</span>
    <span class="modal-meta-item" style="font-size:11px;text-transform:uppercase">${esc(c.tech)}</span>
    ${c.tech_exposure && c.tech_exposure !== 'internal' ? `<span class="modal-meta-item"><span style="font-size:10px;padding:2px 6px;border-radius:3px;background:${_expColor[c.tech_exposure]}1a;border:1px solid ${_expColor[c.tech_exposure]}66;color:${_expColor[c.tech_exposure]}">${c.tech_exposure.toUpperCase()}</span></span>` : ''}
    <span class="modal-meta-item" style="color:var(--text-dim);font-size:11px">·</span>
    <span class="modal-meta-item" style="color:var(--text-dim);font-size:11px">${published}</span>
    ${c.poc_available ? '<span class="modal-meta-item"><span class="cve-poc-badge">⚡ POC AVAILABLE</span></span>' : ''}
    ${c.cisa_kev ? `<span class="modal-meta-item"><span class="cve-poc-badge" style="background:rgba(218,54,51,.15);color:var(--red);border-color:rgba(218,54,51,.5)">🔴 EXPLOITED IN THE WILD (CISA KEV)</span></span>` : ''}
    ${c.epss_score != null ? `<span class="modal-meta-item"><span class="cve-poc-badge" style="background:rgba(110,124,255,0.12);color:#6E7CFF;border-color:rgba(110,124,255,0.4)">📊 EPSS ${(c.epss_score * 100).toFixed(2)}%</span></span>` : ''}
  `;

  // Body
  const affectedHTML = _renderAffectedFull(c.affected);

  const refsHTML = c.reference && c.reference.length
    ? c.reference.map(r =>
        `<div style="margin-bottom:6px">
          <a href="${esc(r.url)}" target="_blank" class="cve-ref-link">${esc(r.url)}</a>
          ${(r.tags||[]).map(t => `<span class="cve-ref-tag">${esc(t)}</span>`).join('')}
        </div>`
      ).join('')
    : '<span style="color:var(--text-dim)">No references listed.</span>';

  const pocsHTML = c.poc_available && c.pocs && c.pocs.length
    ? c.pocs.map(p =>
        `<div style="margin-bottom:8px;display:flex;align-items:center;gap:10px">
          <a href="${esc(p.url)}" target="_blank" class="cve-ref-link" style="margin-bottom:0;flex:1">${esc(p.url)}</a>
          <span class="cve-ref-tag">${esc(p.source || '')}</span>
          <span class="cve-ref-tag" style="color:var(--red);border-color:rgba(218,54,51,0.4)">${esc(p.type || 'poc')}</span>
        </div>`
      ).join('')
    : '<span style="color:var(--text-dim);font-size:12px">No public POC available at this time.</span>';

  document.getElementById('cve-modal-body').innerHTML = `
    <div class="cve-detail-section">
      <div class="cve-detail-label">Summary</div>
      <div class="cve-detail-value">${esc(c.summary || '—')}</div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">Affected Versions</div>
      <div class="cve-detail-value">${affectedHTML}</div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">CVSS Vector</div>
      <div class="cve-detail-value">
        ${c.cvss_vector ? expandCvssVector(c.cvss_vector) : '<span style="color:var(--text-dim)">—</span>'}
      </div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">Solution</div>
      <div class="cve-detail-value" style="color:${hasSol ? 'var(--text-bright)' : 'var(--text-dim)'}">
        ${esc(hasSol ? c.solutions : 'No solution available yet.')}
      </div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">POC / Exploit</div>
      <div class="cve-detail-value">${pocsHTML}</div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">News Mentions</div>
      <div class="cve-detail-value">${_renderNewsMentionsModal(c)}</div>
    </div>
    ${c.cisa_kev ? `<div class="cve-detail-section">
      <div class="cve-detail-label" style="color:var(--red)">🔴 CISA Known Exploited Vulnerability</div>
      <div class="cve-detail-value">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;margin-bottom:10px">
          <div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">VENDOR</span>
            <div style="font-size:12px;color:var(--text-bright)">${esc(c.cisa_kev_vendor||'—')}</div></div>
          <div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">PRODUCT</span>
            <div style="font-size:12px;color:var(--text-bright)">${esc(c.cisa_kev_product||'—')}</div></div>
          <div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">DATE ADDED</span>
            <div style="font-size:12px;color:var(--red)">${esc(c.cisa_kev_date_added||'—')}</div></div>
          <div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">DUE DATE</span>
            <div style="font-size:12px;color:var(--accent3)">${esc(c.cisa_kev_due_date||'—')}</div></div>
        </div>
        ${c.cisa_kev_name ? `<div style="margin-bottom:8px"><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">VULNERABILITY NAME</span>
          <div style="font-size:12px;color:var(--text-bright);margin-top:3px">${esc(c.cisa_kev_name)}</div></div>` : ''}
        ${c.cisa_kev_description ? `<div style="margin-bottom:8px"><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">DESCRIPTION</span>
          <div style="font-size:12px;line-height:1.6;margin-top:3px">${esc(c.cisa_kev_description)}</div></div>` : ''}
        ${c.cisa_kev_action ? `<div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">REQUIRED ACTION</span>
          <div style="font-size:12px;line-height:1.6;margin-top:3px;color:var(--accent3)">${esc(c.cisa_kev_action)}</div></div>` : ''}
      </div>
    </div>` : ''}
    ${c.epss_score != null ? (() => {
        const pct  = (c.epss_score * 100).toFixed(2);
        const perc = c.epss_percentile != null ? Math.round(c.epss_percentile * 100) : null;
        const col  = c.epss_score >= 0.5 ? 'var(--red)' : c.epss_score >= 0.1 ? 'var(--orange)' : 'var(--accent)';
        return `<div class="cve-detail-section">
          <div class="cve-detail-label" style="color:#6E7CFF">📊 EPSS Score (FIRST.org)</div>
          <div class="cve-detail-value">
            <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
              <div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">PROBABILITY</span>
                <div style="font-family:'Share Tech Mono',monospace;font-size:14px;color:${col};margin-top:2px">${pct}%</div></div>
              ${perc != null ? `<div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">PERCENTILE</span>
                <div style="font-family:'Share Tech Mono',monospace;font-size:14px;color:var(--text-bright);margin-top:2px">${perc}th</div></div>` : ''}
              ${c.epss_date ? `<div><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">SCORE DATE</span>
                <div style="font-size:12px;color:var(--text-dim);margin-top:2px">${esc(c.epss_date)}</div></div>` : ''}
            </div>
            <div style="margin-top:6px;font-size:10px;color:var(--text-dim)">
              Probability of exploitation within 30 days.
            </div>
          </div>
        </div>`;
    })() : ''}
    <div class="cve-detail-section" style="border-bottom:none">
      <div class="cve-detail-label">References</div>
      <div class="cve-detail-value">${refsHTML}</div>
    </div>
  `;

  // Reset to details tab, prime ticket section
  cveModalTab('details');
  document.getElementById('cve-tab-ticket-badge').style.display = 'none';
  document.getElementById('cve-modal-ticket-body').innerHTML =
    `<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dim);padding:20px">Loading…</div>`;
  const ackBtn = document.getElementById('cve-ack-btn');
  ackBtn.textContent     = 'Acknowledge';
  ackBtn.style.opacity   = '1';
  ackBtn.dataset.cveId   = c.cve_id;
  const mmBtn = document.getElementById('cve-mindmap-btn');
  mmBtn.textContent    = '⬡ Mind Map';
  mmBtn.disabled       = false;
  mmBtn.dataset.cveId  = c.cve_id;

  // inject/reset inline mindmap container
  const mmContainerId = `mm-cve-inline-${c.cve_id}`;
  let mmWrap = document.getElementById(mmContainerId);
  if (!mmWrap) {
    const section = document.createElement('div');
    section.id = mmContainerId;
    section.style.display = 'none';
    section.innerHTML = '<div class="mm-diagram" style="background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px;padding:12px;overflow:auto;max-height:400px"></div>';
    document.getElementById('cve-modal-body').appendChild(section);
  } else {
    mmWrap.style.display = 'none';
    delete _mmInline[`cve:${c.cve_id}`];
  }

  document.getElementById('cve-modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  // Fetch ticket data in background
  fetch(`/api/cve/${encodeURIComponent(c.cve_id)}/ticket`, { headers: _authAndClientHeaders() })
    .then(r => r.json())
    .then(async ticket => {
      if (!ticket.ticket_id) {
        try {
          const idResp = await fetch('/api/cve/next-ticket-id', { headers: _authAndClientHeaders() });
          const idData = await idResp.json();
          ticket._nextTicketId = idData.ticket_id;
        } catch(e) {}
      }
      _cveTicketCache[c.cve_id] = ticket;
      _renderCveTicketBody(c.cve_id, ticket, c);
      if (ticket.acknowledged_by) {
        document.getElementById('cve-tab-ticket-badge').style.display = '';
        ackBtn.textContent   = '✓ Acknowledged';
        ackBtn.style.opacity = '0.6';
      }
    })
    .catch(() => {
      _cveTicketCache[c.cve_id] = {};
      _renderCveTicketBody(c.cve_id, {}, c);
    });
}

function closeCveModal() {
  document.getElementById('cve-modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

function handleCveModalOverlayClick(e) {
  if (e.target === document.getElementById('cve-modal-overlay')) closeCveModal();
}

// ── CVE TICKET & ACKNOWLEDGE ──────────────────────────────
const _cveTicketCache = {};   // cve_id → ticket object

function cveModalTab(tab) {
  const isDetails = tab === 'details';
  document.getElementById('cve-modal-body').style.display        = isDetails ? '' : 'none';
  document.getElementById('cve-modal-ticket-body').style.display = isDetails ? 'none' : '';
  const dBtn = document.getElementById('cve-tab-details-btn');
  const tBtn = document.getElementById('cve-tab-ticket-btn');
  dBtn.style.borderBottomColor = isDetails ? 'var(--accent)' : 'transparent';
  dBtn.style.color             = isDetails ? 'var(--text-bright)' : 'var(--text-dim)';
  tBtn.style.borderBottomColor = isDetails ? 'transparent' : 'var(--accent)';
  tBtn.style.color             = isDetails ? 'var(--text-dim)' : 'var(--text-bright)';
}

function _field(id, label, type, value, opts = '') {
  const val = value || '';
  if (type === 'textarea') {
    return `<div class="cve-ticket-field ${opts}"><label>${label}</label><textarea id="ctf-${id}">${esc(val)}</textarea></div>`;
  }
  if (type === 'checkbox') {
    return `<div class="cve-ticket-field ${opts}"><label><input type="checkbox" id="ctf-${id}" ${val ? 'checked' : ''}> ${label}</label></div>`;
  }
  if (type === 'select-status') {
    const opts2 = ['','Open','In Progress','Resolved','Risk Accepted','Closed'];
    return `<div class="cve-ticket-field ${opts}"><label>${label}</label><select id="ctf-${id}">${opts2.map(o=>`<option ${o===val?'selected':''}>${o}</option>`).join('')}</select></div>`;
  }
  if (type === 'select-exploitation') {
    const opts2 = [
      ['', '— Select —'],
      ['Active Exploitation',       'Active Exploitation — Confirmed widespread use by threat actors (high priority)'],
      ['Limited Exploitation',      'Limited Exploitation — Spotted in isolated incidents or specific campaigns (medium priority)'],
      ['No Known Exploitation',     'No Known Exploitation — No current evidence of exploitation (low priority, monitoring status)'],
      ['Unknown/Under Investigation','Unknown/Under Investigation — Insufficient intelligence data or analysis pending'],
    ];
    return `<div class="cve-ticket-field ${opts}"><label>${label}</label><select id="ctf-${id}">${opts2.map(([v,l])=>`<option value="${esc(v)}" ${v===val?'selected':''}>${esc(l)}</option>`).join('')}</select></div>`;
  }
  if (type === 'select-risk') {
    const opts2 = ['','Risk Acceptance','Risk Mitigation','Risk Transfer','No Risk (Not Affected)'];
    return `<div class="cve-ticket-field ${opts}"><label>${label}</label><select id="ctf-${id}">${opts2.map(o=>`<option ${o===val?'selected':''}>${esc(o)}</option>`).join('')}</select></div>`;
  }
  if (type === 'readonly') {
    return `<div class="cve-ticket-field ${opts}"><label>${label}</label><input type="text" id="ctf-${id}" value="${esc(val)}" readonly style="opacity:0.6;cursor:default"></div>`;
  }
  return `<div class="cve-ticket-field ${opts}"><label>${label}</label><input type="${type}" id="ctf-${id}" value="${esc(val)}"></div>`;
}

function _fmtDt(val) {
  if (!val) return '';
  return val.replace('T', ' ').replace(/\.\d+Z?$/, '').substring(0, 19);
}

function _renderCveTicketBody(cveId, t, cveData) {
  const isNew = !t.ticket_id;
  const cve   = cveData || _cveDataMap[cveId] || {};

  // Pre-fill affected fields from CVE DB data when creating new ticket
  const affectedAsset   = t.affected_asset   || (isNew ? Object.keys(cve.affected && cve.affected[0] || {}).join(', ') : '');
  const affectedVersion = t.affected_version || (isNew ? (cve.affected || []).flatMap(e => Object.values(e).flat()).join(', ') : '');
  const fixedVersion    = t.fixed_version    || '';

  const ticketIdVal     = t.ticket_id || t._nextTicketId || '';
  const reportedDateVal = t.cve_reported_date || _fmtDt(cve.published) || '';
  const detectionVal    = _fmtDt(cve.detected_on) || _fmtDt(t.detection_time) || '';
  const ackTimeVal      = t.acknowledge_time || '';

  const ackBanner = t.acknowledged_by
    ? `<div class="cve-ack-banner">✓ Acknowledged by <strong>${esc(t.acknowledged_by)}</strong> on ${esc(t.acknowledge_time || '')}</div>`
    : '';
  const html = `
    ${ackBanner}
    <div class="cve-ticket-grid">
      ${_field('ticket_id',              'Ticket ID (auto-generated)',   'readonly',           ticketIdVal)}
      ${_field('cve_reported_date',      'CVE Reported Date',            'readonly',           reportedDateVal)}
      ${_field('detection_time',         'Detection Time',               'readonly',           detectionVal)}
      ${_field('acknowledge_time',       'Acknowledge Time',             'readonly',           ackTimeVal)}
      ${_field('affected_asset',         'Affected Asset / Product',     'text',               affectedAsset)}
      ${_field('affected_version',       'Affected Version',             'text',               affectedVersion)}
      ${_field('fixed_version',          'Fixed Version',                'text',               fixedVersion)}
      ${_field('asset_owner',            'Asset Owner',                  'text',               t.asset_owner)}
      ${_field('owner_email',            'Owner Email',                  'email',              t.owner_email)}
      ${_field('owner_team',             'Owner Team',                   'text',               t.owner_team)}
      ${_field('active_exploitation',    'Active Exploitation',          'select-exploitation',t.active_exploitation, 'full')}
      ${_field('remediation_date_plan',  'Remediation Date Plan',        'date',               t.remediation_date_plan)}
      ${_field('remediation_status',     'Remediation Status',           'select-status',      t.remediation_status)}
      ${_field('actual_remediation_date','Actual Remediation Date',      'date',               t.actual_remediation_date)}
      ${_field('closure_date',           'Closure Date',                 'date',               t.closure_date)}
      ${_field('risk_acceptance',        'Risk Acceptance',              'select-risk',        t.risk_acceptance)}
      <div style="display:flex;gap:16px;align-items:center">
        ${_field('escalation_required',  'Escalation Required',          'checkbox',           t.escalation_required)}
      </div>
      ${_field('comments',               'Comments / Notes',             'textarea',           t.comments, 'full')}
    </div>
    <div style="display:flex;justify-content:flex-end;margin-top:14px">
      <button class="btn-apply" onclick="_saveCveTicket('${esc(cveId)}')">SAVE TICKET</button>
    </div>`;
  document.getElementById('cve-modal-ticket-body').innerHTML = html;
}

function _saveCveTicket(cveId) {
  requireTAAuth(async ({ pass }) => {
    const g = id => document.getElementById('ctf-' + id);
    const cached = _cveTicketCache[cveId] || {};
    const payload = {
      ticket_id:              g('ticket_id')?.value || '',
      cve_reported_date:      g('cve_reported_date')?.value || cached.cve_reported_date || '',
      affected_asset:         g('affected_asset')?.value || '',
      affected_version:       g('affected_version')?.value || '',
      fixed_version:          g('fixed_version')?.value || '',
      asset_owner:            g('asset_owner')?.value || '',
      owner_email:            g('owner_email')?.value || '',
      owner_team:             g('owner_team')?.value || '',
      active_exploitation:    g('active_exploitation')?.value || '',
      remediation_date_plan:  g('remediation_date_plan')?.value || '',
      remediation_status:     g('remediation_status')?.value || '',
      actual_remediation_date:g('actual_remediation_date')?.value || '',
      escalation_required:    g('escalation_required')?.checked || false,
      comments:               g('comments')?.value || '',
      risk_acceptance:        g('risk_acceptance')?.value || '',
      closure_date:           g('closure_date')?.value || '',
      cve_id: cveId,
    };
    let r;
    try {
      r = await fetch(`/api/cve/${encodeURIComponent(cveId)}/ticket`, {
        method: 'PUT',
        headers: _authAndClientHeaders({ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pass }),
        body: JSON.stringify(payload),
      });
    } catch(e) {
      _authShowError(`Network error: ${e.message}`);
      return;
    }
    if (r.ok) {
      closeAuthModal();
      _cveTicketCache[cveId] = payload;
      _cveToast('Ticket saved.', true);
    } else if (r.status === 401) {
      _jwtClear();
      _authShowError('Wrong password — try again.');
    } else {
      _authShowError(`Server error ${r.status} — check server logs.`);
    }
  }, { subtitle: `Save ticket for ${cveId}` });
}

function acknowledgeCve() {
  const cveId = document.getElementById('cve-ack-btn').dataset.cveId;
  if (!cveId) return;
  const ticket = _cveTicketCache[cveId] || {};
  if (ticket.acknowledged_by) {
    _cveToast(`Already acknowledged by ${ticket.acknowledged_by}.`, false);
    return;
  }

  requireTAAuth(async ({ pass, analyst }) => {
    let r;
    try {
      r = await fetch(`/api/cve/${encodeURIComponent(cveId)}/acknowledge`, {
        method: 'POST',
        headers: _authAndClientHeaders({ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pass }),
        body: JSON.stringify({ analyst_name: analyst }),
      });
    } catch(e) {
      _authShowError(`Network error: ${e.message}`);
      return;
    }
    if (r.ok) {
      closeAuthModal();
      const now = new Date();
      const utc7 = new Date(now.getTime() + 7 * 60 * 60 * 1000);
      const ackTime = utc7.toISOString().replace('T', ' ').replace(/\.\d+Z$/, '');
      const today   = ackTime.split(' ')[0];
      _cveTicketCache[cveId] = { ..._cveTicketCache[cveId], acknowledged_by: analyst, acknowledge_time: ackTime };
      _cveAckMap[cveId] = analyst;
      _renderCveTicketBody(cveId, _cveTicketCache[cveId], _cveDataMap[cveId]);
      document.getElementById('cve-tab-ticket-badge').style.display = '';
      const ackBtn = document.getElementById('cve-ack-btn');
      ackBtn.textContent   = '✓ Acknowledged';
      ackBtn.style.opacity = '0.6';
      cveModalTab('ticket');
      _cveToast(`Acknowledged by ${analyst}`, true);
      _patchCveRowAck(cveId, analyst);
    } else if (r.status === 401) {
      _jwtClear();
      _authShowError('Wrong password — try again.');
    } else {
      _authShowError(`Server error ${r.status} — check server logs.`);
    }
  }, { analystName: true, subtitle: `Acknowledge ${cveId} as CTI analyst`, bypassCache: true });
}

function generateCveMindmap() {
  const btn   = document.getElementById('cve-mindmap-btn');
  const cveId = btn?.dataset.cveId;
  if (!cveId) return;
  mmOpenEditor('cve', cveId, cveId);
}


function _cvePageSize() {
  return parseInt(document.getElementById('cve-page-size')?.value || '20', 10);
}

function cveChangePage(page) {
  if (page < 1) return;
  const totalPages = Math.ceil(_cveTotal / _cvePageSize());
  if (page > totalPages) return;
  _cvePage = page;
  loadCvePanel(false);
}

function cveChangePageSize(val) {
  _cvePage = 1;
  loadCvePanel(false);
}

function _renderCvePager(total, page) {
  const pageSize   = _cvePageSize();
  const totalPages = Math.ceil(total / pageSize) || 1;
  const prevBtn    = document.getElementById('cve-page-prev');
  const nextBtn    = document.getElementById('cve-page-next');
  const infoEl     = document.getElementById('cve-page-info');
  if (!prevBtn) return;
  const start = (page - 1) * pageSize + 1;
  const end   = Math.min(page * pageSize, total);
  infoEl.textContent   = total ? `${start}–${end} of ${total}` : '0 results';
  prevBtn.disabled     = page <= 1;
  nextBtn.disabled     = page >= totalPages;
  document.getElementById('cve-pager').style.display = total > pageSize ? '' : 'none';
}

async function loadCvePanel(resetPage = true) {
  await _loadCveTechOptions();

  if (resetPage) _cvePage = 1;

  const search    = document.getElementById('cve-search')?.value.trim()    || '';
  const severity  = document.getElementById('cve-severity')?.value         || '';
  const tech      = document.getElementById('cve-tech')?.value             || '';
  const dateStart = document.getElementById('cve-date-start')?.value       || '';
  const dateEnd   = document.getElementById('cve-date-end')?.value         || '';
  const includeFp = document.getElementById('cve-show-fp')?.checked || false;
  const unackedOnly = document.getElementById('cve-unacked-filter')?.checked || false;

  const params = new URLSearchParams({
    page: _cvePage, page_size: _cvePageSize(),
    include_fp: includeFp, sort_by: _cveSortBy, sort_dir: _cveSortDir,
  });
  if (search)      params.set('search',     search);
  if (severity)    params.append('severity', severity);
  if (tech)        params.append('tech',    tech);
  if (dateStart)   params.set('date_start', dateStart);
  if (dateEnd)     params.set('date_end',   dateEnd);
  if (unackedOnly) params.set('ack_filter', 'unacked');
  _updateCveSortUI();

  document.getElementById('cve-tbody').innerHTML = `<tr><td colspan="12">${loadingHTML()}</td></tr>`;

  _cveSelected.clear();
  _updateCveBulkButtons();
  let data  = { cves: [], total: 0 };
  let stats = { total: 0, critical: 0, high: 0, medium: 0 };
  try {
    const ch = _authAndClientHeaders();
    const statsParams = new URLSearchParams({ include_fp: includeFp });
    if (search)    statsParams.set('search',     search);
    if (severity)  statsParams.set('severity',   severity);
    if (tech)      statsParams.set('tech',       tech);
    if (dateStart) statsParams.set('date_start', dateStart);
    if (dateEnd)   statsParams.set('date_end',   dateEnd);
    if (unackedOnly) statsParams.set('ack_filter', 'unacked');
    const [r1, r2, r3] = await Promise.all([
      fetch(`/api/cve?${params}`, { headers: ch }),
      fetch(`/api/cve/stats?${statsParams}`, { headers: ch }),
      fetch('/api/cve/ack-statuses', { headers: ch }),
    ]);
    if (r1.ok) data  = await r1.json();
    if (r2.ok) stats = await r2.json();
    if (r3.ok) _cveAckMap = await r3.json();
  } catch(e) { console.error(e); }

  _cveTotal = data.total;

  document.getElementById('stat-cve-total').textContent    = data.total;
  document.getElementById('stat-cve-critical').textContent = stats.critical;
  document.getElementById('stat-cve-high').textContent     = stats.high;
  document.getElementById('stat-cve-medium').textContent   = stats.medium;

  data.cves.forEach(c => { _cveDataMap[c.cve_id] = c; });

  document.getElementById('cve-tbody').innerHTML = data.cves.length
    ? data.cves.map(renderCveRow).join('')
    : `<tr><td colspan="12">${emptyHTML('No CVEs found. Run newCveThreat.py to populate.')}</td></tr>`;
  document.getElementById('cve-count').textContent = data.total;
  document.getElementById('cve-submenu-count').textContent = data.total;
  const _tsvCveBadge = document.getElementById('tsv-cve-count-badge');
  if (_tsvCveBadge) _tsvCveBadge.textContent = data.total;

  _renderCvePager(data.total, _cvePage);
  return data.total;
}

// ── CVE SUB-VIEW SWITCH ───────────────────────────────────
let _cveView = 'cves';

function cveSwitchView(view) {
  _cveView = view;
  document.getElementById('cveview-cves').style.display    = view === 'cves'    ? '' : 'none';
  document.getElementById('cveview-pkgvuln').style.display = view === 'pkgvuln' ? '' : 'none';
  document.getElementById('cveview-cves-btn').classList.toggle('active', view === 'cves');
  document.getElementById('cveview-pv-btn').classList.toggle('active',   view === 'pkgvuln');
  if (view === 'pkgvuln') loadPkgVulnPanel();
}

// ── TECH STACK VULN INNER SUB-VIEW ────────────────────────
let _tsvSubview = 'cves';

function cveSwitchTSVSubview(sub) {
  _tsvSubview = sub;
  document.getElementById('cveview-sub-cves').style.display  = sub === 'cves'      ? '' : 'none';
  document.getElementById('cveview-techstack').style.display = sub === 'techstack' ? '' : 'none';
  document.getElementById('tsv-cves-btn').classList.toggle('active', sub === 'cves');
  document.getElementById('tsv-ts-btn').classList.toggle('active',   sub === 'techstack');
  if (sub === 'techstack') { _tsState.page = 1; loadTechStack(); }
}

