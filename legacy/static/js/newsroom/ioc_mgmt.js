// ── IOC MANAGEMENT ────────────────────────────────────────────

let _iocPageSize = 50;
let _iocPage = 1;
let _iocTotal = 0;
let _iocSortBy = 'last_seen';
let _iocStatFilter = null;
let _iocActionabilityFilter = null;

const _IOC_TYPE_STYLE = {
  ip:           { label: 'IP',        bg: 'rgba(218,54,51,0.12)',   border: 'rgba(218,54,51,0.35)',   color: 'var(--red)' },
  domain:       { label: 'DOMAIN',    bg: 'rgba(227,179,65,0.12)',  border: 'rgba(227,179,65,0.35)',  color: 'var(--orange)' },
  url:          { label: 'URL',       bg: 'rgba(47,129,247,0.12)',  border: 'rgba(47,129,247,0.35)',  color: 'var(--accent)' },
  url_with_path:{ label: 'URL+PATH',  bg: 'rgba(47,129,247,0.08)',  border: 'rgba(47,129,247,0.25)',  color: 'var(--accent)' },
  email:        { label: 'EMAIL',     bg: 'rgba(88,166,255,0.12)', border: 'rgba(88,166,255,0.35)', color: '#58A6FF' },
  sha256:       { label: 'SHA256',    bg: 'rgba(83,52,131,0.2)',    border: 'rgba(83,52,131,0.4)',    color: '#a78bdb' },
  sha1:         { label: 'SHA1',      bg: 'rgba(83,52,131,0.15)',   border: 'rgba(83,52,131,0.3)',    color: '#a78bdb' },
  md5:          { label: 'MD5',       bg: 'rgba(83,52,131,0.15)',   border: 'rgba(83,52,131,0.3)',    color: '#a78bdb' },
  cve:          { label: 'CVE',       bg: 'rgba(52,168,83,0.12)',   border: 'rgba(52,168,83,0.35)',   color: '#34a853' },
};

function _iocTypeBadge(type) {
  const s = _IOC_TYPE_STYLE[type] || { label: type.toUpperCase(), bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.15)', color: 'var(--text-dim)' };
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 6px;border-radius:2px;background:${s.bg};border:1px solid ${s.border};color:${s.color}">${s.label}</span>`;
}

const _ACTIONABILITY_STYLE = {
  block_now:   { label: 'BLOCK NOW',   bg: 'rgba(218,54,51,0.15)',  border: 'rgba(218,54,51,0.45)',  color: 'var(--red)' },
  investigate: { label: 'INVESTIGATE', bg: 'rgba(255,165,0,0.12)',  border: 'rgba(255,165,0,0.4)',   color: '#ffaa00' },
  monitor:     { label: 'MONITOR',     bg: 'rgba(227,179,65,0.12)', border: 'rgba(227,179,65,0.35)', color: 'var(--orange)' },
  archive:     { label: 'ARCHIVE',     bg: 'rgba(255,255,255,0.04)',border: 'rgba(255,255,255,0.15)',color: 'var(--text-dim)' },
};

function _iocActionabilityChip(label) {
  if (!label) return '';
  const s = _ACTIONABILITY_STYLE[label] || _ACTIONABILITY_STYLE.archive;
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 6px;border-radius:2px;background:${s.bg};border:1px solid ${s.border};color:${s.color}">${s.label}</span>`;
}

function _iocConfidenceChip(score) {
  if (score == null) return '';
  const s = score >= 75 ? { bg: 'rgba(52,168,83,0.15)', border: 'rgba(52,168,83,0.4)', color: '#34a853' }
          : score >= 40 ? { bg: 'rgba(255,165,0,0.12)',  border: 'rgba(255,165,0,0.4)',  color: '#ffaa00' }
          :                { bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.15)', color: 'var(--text-dim)' };
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 6px;border-radius:2px;background:${s.bg};border:1px solid ${s.border};color:${s.color}">${score}</span>`;
}

async function iocmgmtLoad(page) {
  _iocPage = page || 1;
  const tbody = document.getElementById('iocmgmt-tbody');
  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-dim);padding:24px">Loading…</td></tr>`;

  const type   = document.getElementById('iocmgmt-type-filter').value;
  _iocStatFilter = type || null;
  const search = document.getElementById('iocmgmt-search').value.trim();
  const params = new URLSearchParams({ page: _iocPage, page_size: _iocPageSize });
  if (type)   params.set('ioc_type', type);
  if (search) params.set('search', search);
  if (_iocSortBy === 'confidence') params.set('sort_by', 'confidence');
  if (_iocActionabilityFilter) params.set('actionability', _iocActionabilityFilter);

  try {
    const ch = _authAndClientHeaders();
    const [listResp, statsResp] = await Promise.all([
      fetch(`/api/iocs?${params}`, { headers: ch }),
      fetch('/api/iocs/stats', { headers: ch }),
    ]);
    if (!listResp.ok) throw new Error(listResp.statusText);
    const data  = await listResp.json();
    const stats = statsResp.ok ? await statsResp.json() : null;

    _iocTotal = data.total;
    document.getElementById('iocmgmt-total').textContent = `${data.total} IOCs`;
    document.getElementById('iocmgmt-footer-total').textContent = `${data.total} IOCs total`;
    document.getElementById('intel-iocmgmt-count').textContent = data.total;

    if (stats) _renderIocStats(stats);

    if (!data.iocs.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-dim);padding:24px">No IOCs found</td></tr>`;
      document.getElementById('iocmgmt-pager').innerHTML = '';
      return;
    }

    tbody.innerHTML = data.iocs.map(ioc => `
      <tr style="cursor:pointer" onclick="iocmgmtOpenDetail('${esc(ioc.type)}','${esc(ioc.value.replace(/'/g,"\\x27"))}')">
        <td>${_iocTypeBadge(ioc.type)}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright);word-break:break-all">${esc(ioc.value)}</td>
        <td style="text-align:center">${_iocConfidenceChip(ioc.confidence_score)}</td>
        <td style="text-align:center">${_iocActionabilityChip(ioc.actionability_label)}</td>
        <td style="text-align:center;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dim)">${ioc.seen_count || 1}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${esc(ioc.first_seen || '—')}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${esc(ioc.last_seen || '—')}</td>
        <td style="text-align:center;white-space:nowrap" onclick="event.stopPropagation()">
          <button onclick="iocmgmtFeedback('${esc(ioc._id)}',this,'tp')" title="True Positive"
            style="background:rgba(52,168,83,0.1);border:1px solid rgba(52,168,83,0.35);color:#34a853;border-radius:3px;padding:2px 6px;font-size:11px;cursor:pointer">👍</button>
          <button onclick="iocmgmtFeedback('${esc(ioc._id)}',this,'fp')" title="False Positive"
            style="background:rgba(218,54,51,0.1);border:1px solid rgba(218,54,51,0.35);color:var(--red);border-radius:3px;padding:2px 6px;font-size:11px;cursor:pointer;margin-left:3px">👎</button>
        </td>
      </tr>`).join('');

    _renderIocPager();
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--red);padding:24px">Error: ${esc(e.message)}</td></tr>`;
  }
}


function iocmgmtSetActionabilityFilter(val) {
  _iocActionabilityFilter = val || null;
  iocmgmtLoad(1);
}

function iocmgmtSetSort(val) {
  _iocSortBy = val;
  iocmgmtLoad(1);
}

function iocmgmtSetPageSize(val) {
  _iocPageSize = parseInt(val, 10) || 50;
  iocmgmtLoad(1);
}

function iocmgmtToggleStatFilter(type) {
  _iocStatFilter = _iocStatFilter === type ? null : type;
  const sel = document.getElementById('iocmgmt-type-filter');
  if (sel) sel.value = _iocStatFilter || '';
  iocmgmtLoad(1);
}

function _renderIocStats(stats) {
  const el = document.getElementById('iocmgmt-stats');
  el.innerHTML = stats.by_type.map(t => {
    const s = _IOC_TYPE_STYLE[t.type] || {};
    const active = _iocStatFilter === t.type;
    const bg     = active ? (s.color || 'var(--text-dim)') : (s.bg || 'rgba(255,255,255,0.05)');
    const color  = active ? 'var(--bg, #0d1117)' : (s.color || 'var(--text-dim)');
    const border = s.border || 'rgba(255,255,255,0.1)';
    return `<button onclick="iocmgmtToggleStatFilter('${t.type}')"
      title="${active ? 'Clear filter' : 'Filter by ' + (s.label||t.type)}"
      style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 8px;border-radius:2px;background:${bg};border:1px solid ${border};color:${color};cursor:pointer;transition:background .15s">
      ${(s.label||t.type).toUpperCase()}: ${t.count}
    </button>`;
  }).join('');
}

function _renderIocPager() {
  const el = document.getElementById('iocmgmt-pager');
  const total = Math.ceil(_iocTotal / _iocPageSize);
  if (total <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="iocmgmtLoad(${_iocPage - 1})" ${_iocPage <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${_iocPage}</strong> / ${total}</span>
    <button class="pager-btn" onclick="iocmgmtLoad(${_iocPage + 1})" ${_iocPage >= total ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

async function iocmgmtOpenDetail(type, value) {
  const modal = document.getElementById('iocmgmt-modal');
  const body  = document.getElementById('iocmgmt-modal-body');
  body.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-dim)">Loading…</div>';
  modal.style.display = '';

  try {
    const ch = _authAndClientHeaders();
    const [resp, taResp] = await Promise.all([
      fetch(`/api/iocs/${encodeURIComponent(type)}/${encodeURIComponent(value)}`, { headers: ch }),
      fetch(`/api/iocs/ta-links/${encodeURIComponent(type)}/${encodeURIComponent(value)}`, { headers: ch }),
    ]);
    if (!resp.ok) throw new Error(resp.statusText);
    const ioc = await resp.json();
    const taData = taResp.ok ? await taResp.json() : null;

    const sources = ioc.sources || [];
    const sourcesHtml = sources.length
      ? sources.map(s => `
        <div style="padding:10px 12px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:4px">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:var(--text-dim)">${esc(s.feature_type||'—')}</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${esc(s.source_name||'—')}</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);margin-left:auto">${esc(s.first_seen||'')}</span>
          </div>
          <a href="${esc(s.url||'#')}" target="_blank" rel="noopener"
             style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent);text-decoration:none;word-break:break-all"
             onclick="event.stopPropagation()">${esc(s.url||'—')}</a>
          ${s.context ? `<div style="font-size:10px;color:var(--text-dim);font-style:italic;margin-top:2px">${esc(s.context)}</div>` : ''}
        </div>`).join('')
      : '<div style="padding:12px;color:var(--text-dim);font-size:11px">No source articles recorded.</div>';

    const tags = (ioc.tags||[]).map(t =>
      `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;border-radius:2px;background:rgba(47,129,247,0.1);border:1px solid rgba(47,129,247,0.3);color:var(--accent)">${esc(t)}</span>`
    ).join('');

    body.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap">
        ${_iocTypeBadge(ioc.type)}
        <span style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--text-bright);word-break:break-all">${esc(ioc.value)}</span>
        ${_iocConfidenceChip(ioc.confidence_score)}
        ${_iocActionabilityChip(ioc.actionability_label)}
        <button onclick="iocmgmtDelete('${esc(ioc._id)}',this)"
          style="margin-left:auto; margin-right:10px ;padding:4px 10px;font-size:10px;background:rgba(218,54,51,0.08);border:1px solid rgba(218,54,51,0.35);color:var(--red);border-radius:3px;cursor:pointer">🗑 Delete IOC</button>
      </div>
      ${ioc.recommended_action ? `<div style="margin-bottom:14px;font-family:'IBM Plex Mono',monospace;font-size:10px;padding:7px 10px;border-radius:3px;background:rgba(255,255,255,0.03);border:1px solid var(--border);color:var(--text-bright)">⚡ ${esc(ioc.recommended_action)}</div>` : ''}
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px">
        <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:4px;padding:10px">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Seen Count</div>
          <div style="font-size:18px;font-weight:700;color:var(--text-bright)">${ioc.seen_count||1}</div>
        </div>
        <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:4px;padding:10px">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">First Seen</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright)">${esc(ioc.first_seen||'—')}</div>
        </div>
        <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:4px;padding:10px">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">Last Seen</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright)">${esc(ioc.last_seen||'—')}</div>
        </div>
      </div>
      ${tags ? `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px">${tags}</div>` : ''}
      ${_renderIocEnrichment(ioc.enrichment)}
      ${_renderIocTaLinks(taData, type, value)}
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">
        Linked Articles (${sources.length})
      </div>
      <div style="border:1px solid var(--border);border-radius:4px;overflow:hidden">
        ${sourcesHtml}
      </div>`;
  } catch(e) {
    body.innerHTML = `<div style="color:var(--red);padding:16px">Error: ${esc(e.message)}</div>`;
  }
}

function _renderIocTaLinks(taData, iocType, iocValue) {
  if (!taData) return '';
  const actors = (taData.threat_actors || []);
  const label = `Linked Threat Actors (${actors.length})`;
  const manualActors = actors.filter(a => a.source === 'manual' || a.source === 'both').map(a => a.name);

  const rows = actors.map(ta => {
    const watchedBadge = ta.is_watched
      ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:rgba(255,165,0,0.12);border:1px solid rgba(255,165,0,0.4);color:#ffaa00;margin-left:6px">WATCHED</span>`
      : '';
    const attackBadge = ta.attack_group_id
      ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:rgba(83,52,131,0.15);border:1px solid rgba(83,52,131,0.35);color:#a78bdb;margin-left:6px">${esc(ta.attack_group_id)}</span>`
      : '';
    const sourceBadge = ta.source === 'manual'
      ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:rgba(47,129,247,0.1);border:1px solid rgba(47,129,247,0.3);color:var(--accent);margin-left:6px">MANUAL</span>`
      : ta.source === 'both'
      ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:rgba(47,129,247,0.1);border:1px solid rgba(47,129,247,0.3);color:var(--accent);margin-left:6px">MANUAL+ART</span>`
      : '';
    const aliases = (ta.attack_group_aliases || []).slice(0, 4);
    const aliasHtml = aliases.length
      ? `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-top:3px">aka: ${aliases.map(a => esc(a)).join(', ')}</div>`
      : '';
    const isManual = ta.source === 'manual' || ta.source === 'both';
    const removeBtn = isManual
      ? `<button onclick="iocmgmtRemoveTa('${esc(iocType)}','${esc(iocValue.replace(/'/g,"\\x27"))}','${esc(ta.name.replace(/'/g,"\\x27"))}')" title="Remove manual tag"
           style="margin-left:8px;background:none;border:none;cursor:pointer;color:var(--text-dim);font-size:11px;padding:0;line-height:1" onmouseover="this.style.color='var(--red)'" onmouseout="this.style.color='var(--text-dim)'">✕</button>`
      : '';
    return `
      <div style="padding:9px 12px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:2px">
        <div style="display:flex;align-items:center;flex-wrap:wrap">
          <span style="font-size:12px;color:var(--text-bright)">${esc(ta.name)}</span>
          ${watchedBadge}${attackBadge}${sourceBadge}${removeBtn}
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-left:auto">${ta.article_count > 0 ? ta.article_count + ' article' + (ta.article_count !== 1 ? 's' : '') : 'manual only'}</span>
        </div>
        ${aliasHtml}
      </div>`;
  }).join('');

  const listHtml = actors.length
    ? `<div style="border:1px solid var(--border);border-radius:4px;overflow:hidden">${rows}</div>`
    : `<div style="border:1px solid var(--border);border-radius:4px;padding:12px;color:var(--text-dim);font-size:11px">No threat actors linked.</div>`;

  const addForm = `
    <div style="display:flex;gap:6px;margin-top:8px">
      <input id="ioc-ta-input-${esc(iocType)}" type="text" placeholder="Add threat actor name…"
             style="flex:1;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:3px;padding:5px 8px;font-size:11px;color:var(--text-bright);font-family:'IBM Plex Mono',monospace"
             onkeydown="if(event.key==='Enter')iocmgmtAddTa('${esc(iocType)}','${esc(iocValue.replace(/'/g,"\\x27"))}')">
      <button onclick="iocmgmtAddTa('${esc(iocType)}','${esc(iocValue.replace(/'/g,"\\x27"))}')"
              style="padding:5px 12px;background:rgba(47,129,247,0.15);border:1px solid rgba(47,129,247,0.4);color:var(--accent);border-radius:3px;font-size:11px;cursor:pointer">+ Link TA</button>
    </div>`;

  return `
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;margin-top:16px">
      ${label}
    </div>
    <div id="ioc-ta-list-${esc(iocType)}-${esc(iocValue.replace(/[^a-zA-Z0-9]/g,'_'))}">
      ${listHtml}
    </div>
    ${addForm}
    <div style="margin-bottom:16px"></div>`;
}

function _verdictStyle(verdict) {
  switch ((verdict || '').toLowerCase()) {
    case 'malicious':  return 'color:var(--red);';
    case 'suspicious': return 'color:var(--orange);';
    case 'clean':      return 'color:var(--accent);';
    default:           return 'color:var(--text-dim);';
  }
}

function _scoreColor(score) {
  if (score >= 75) return 'var(--red)';
  if (score >= 25) return 'var(--orange)';
  if (score > 0)   return 'var(--orange)';
  return 'var(--text-dim)';
}

function _renderProviderCard(p) {
  const families = (p.malware_families || []).filter(Boolean).slice(0, 6);
  const tags     = (p.tags || []).slice(0, 8);
  const raw      = p.raw || {};
  const rawKeys  = Object.keys(raw).filter(k => raw[k] !== null && raw[k] !== '');

  return `
    <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px;padding:12px;margin-bottom:10px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em">${esc(p.name || p.key)}</span>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;border-radius:2px;background:rgba(255,255,255,0.05);border:1px solid var(--border);${_verdictStyle(p.verdict)}">${esc((p.verdict || 'unknown').toUpperCase())}</span>
      </div>
      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:${families.length || tags.length || rawKeys.length ? '10px' : '0'}">
        <div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-bottom:2px">SCORE</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:700;color:${_scoreColor(p.score || 0)}">${p.score ?? '—'}<span style="font-size:9px;color:var(--text-dim)">/100</span></div>
        </div>
        ${rawKeys.map(k => `
        <div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-bottom:2px">${esc(k.replace(/_/g,' ').toUpperCase())}</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright)">${esc(String(raw[k]))}</div>
        </div>`).join('')}
      </div>
      ${families.length ? `<div style="margin-bottom:6px">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-bottom:4px">MALWARE FAMILIES</div>
        <div style="display:flex;gap:4px;flex-wrap:wrap">${families.map(f =>
          `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;border-radius:2px;background:rgba(218,54,51,0.1);border:1px solid rgba(218,54,51,0.3);color:var(--red)">${esc(f)}</span>`
        ).join('')}</div>
      </div>` : ''}
      ${tags.length ? `<div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-bottom:4px">TAGS</div>
        <div style="display:flex;gap:4px;flex-wrap:wrap">${tags.map(t =>
          `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;border-radius:2px;background:rgba(255,255,255,0.04);border:1px solid var(--border);color:var(--text-dim)">${esc(t)}</span>`
        ).join('')}</div>
      </div>` : ''}
    </div>`;
}

function _renderIocEnrichment(enrichment) {
  if (!enrichment) return '';
  const providers = (enrichment.providers || []).filter(p => p && p.key);
  if (!providers.length) return '';
  const updatedAt = enrichment.updated_at || '';
  return `
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;display:flex;align-items:center;gap:8px">
      TIP Enrichment
      ${updatedAt ? `<span style="font-size:9px;color:var(--text-dim);font-weight:normal;text-transform:none">updated ${esc(updatedAt)}</span>` : ''}
    </div>
    ${providers.map(_renderProviderCard).join('')}`;
}

async function iocmgmtAddTa(type, value) {
  const input = document.getElementById(`ioc-ta-input-${type}`);
  const actor = (input?.value || '').trim();
  if (!actor) return;
  try {
    const resp = await fetch(
      `/api/iocs/${encodeURIComponent(type)}/${encodeURIComponent(value)}/threat-actors`,
      { method: 'POST', headers: { 'Content-Type': 'application/json', ..._authAndClientHeaders() },
        body: JSON.stringify({ threat_actors: [actor] }) }
    );
    if (!resp.ok) throw new Error(await resp.text());
    input.value = '';
    iocmgmtOpenDetail(type, value);
  } catch(e) {
    alert(`Failed to link TA: ${e.message}`);
  }
}

async function iocmgmtRemoveTa(type, value, actor) {
  try {
    const resp = await fetch(
      `/api/iocs/${encodeURIComponent(type)}/${encodeURIComponent(value)}/threat-actors/${encodeURIComponent(actor)}`,
      { method: 'DELETE', headers: _authAndClientHeaders() }
    );
    if (!resp.ok) throw new Error(await resp.text());
    iocmgmtOpenDetail(type, value);
  } catch(e) {
    alert(`Failed to remove TA: ${e.message}`);
  }
}

async function iocmgmtDelete(iocId, btn) {
  if (!confirm('Delete this IOC permanently? This cannot be undone.')) return;
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const resp = await fetch(`/api/iocs/${encodeURIComponent(iocId)}`, {
      method: 'DELETE',
      headers: _authAndClientHeaders(),
    });
    if (!resp.ok) throw new Error(await resp.text());
    document.getElementById('iocmgmt-modal').style.display = 'none';
    iocmgmtLoad(_iocPage);
  } catch(e) {
    btn.disabled = false;
    btn.textContent = '🗑 Delete IOC';
    alert(`Delete failed: ${e.message}`);
  }
}

// ── IOC ALLOWLIST ──────────────────────────────────────────

const _TYPE_LABEL = { url_domain: 'URL Domain', email_domain: 'Email Domain', ip: 'IP Address' };

async function allowlistLoad() {
  const tbody = document.getElementById('allowlist-tbody');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-dim);padding:16px">Loading…</td></tr>`;
  try {
    const resp = await fetch('/api/iocs/allowlist', { headers: _authAndClientHeaders() });
    if (!resp.ok) throw new Error(resp.statusText);
    const data = await resp.json();
    const entries = data.entries || [];
    if (!entries.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-dim);padding:16px">No allowlist entries</td></tr>`;
      return;
    }
    tbody.innerHTML = entries.map(e => `
      <tr>
        <td style="padding:5px 8px">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(47,129,247,0.08);border:1px solid rgba(47,129,247,0.25);color:var(--accent)">
            ${esc(_TYPE_LABEL[e.type] || e.type)}
          </span>
        </td>
        <td style="padding:5px 8px;color:var(--text-bright)">${esc(e.value)}</td>
        <td style="padding:5px 8px;color:var(--text-dim)">${esc(e.added_by || '—')}</td>
        <td style="padding:5px 8px;color:var(--text-dim)">${esc((e.added_at || '').slice(0, 10))}</td>
        <td style="padding:5px 8px;text-align:center">
          <button onclick="allowlistRemove('${esc(e._id)}', this)"
            style="background:none;border:none;cursor:pointer;color:var(--text-dim);font-size:12px"
            onmouseover="this.style.color='var(--red)'" onmouseout="this.style.color='var(--text-dim)'">✕</button>
        </td>
      </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--red);padding:16px">Error: ${esc(e.message)}</td></tr>`;
  }
}

async function allowlistAdd() {
  const type  = document.getElementById('allowlist-type').value;
  const value = document.getElementById('allowlist-value').value.trim();
  const status = document.getElementById('allowlist-status');
  if (!value) return;
  status.textContent = 'Adding…';
  try {
    const resp = await fetch('/api/iocs/allowlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ..._authAndClientHeaders() },
      body: JSON.stringify({ type, value }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const entry = await resp.json();
    document.getElementById('allowlist-value').value = '';
    const deleted = entry.deleted_iocs || 0;
    status.textContent = deleted ? `Added. ${deleted} existing IOC${deleted !== 1 ? 's' : ''} removed.` : 'Added.';
    setTimeout(() => { status.textContent = ''; }, 4000);
    await allowlistLoad();
    iocmgmtLoad(1);
  } catch(e) {
    status.textContent = `Error: ${e.message}`;
  }
}

async function allowlistRemove(entryId, btn) {
  btn.disabled = true;
  try {
    const resp = await fetch(`/api/iocs/allowlist/${encodeURIComponent(entryId)}`, {
      method: 'DELETE',
      headers: _authAndClientHeaders(),
    });
    if (!resp.ok) throw new Error(await resp.text());
    await allowlistLoad();
  } catch(e) {
    btn.disabled = false;
    alert(`Remove failed: ${e.message}`);
  }
}

// ── FP ANALYTICS ──────────────────────────────────────────

async function fpAnalyticsLoad(force) {
  const body = document.getElementById('ioc-fp-analytics-body');
  if (!body) return;
  body.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:16px;font-size:11px">Loading…</div>';
  try {
    const params = force ? '?force=true' : '';
    const resp = await fetch(`/api/iocs/fp-analytics${params}`, { headers: _authAndClientHeaders() });
    if (!resp.ok) throw new Error(resp.statusText);
    const d = await resp.json();
    body.innerHTML = _renderFpAnalytics(d);

    const suppCount = Object.values(d.fp_by_source || {}).reduce((acc, s) => acc + s.fp_count, 0);
    const badge = document.getElementById('ioc-fp-suppressed-badge');
    if (badge) badge.textContent = suppCount ? `${suppCount} total FP verdicts` : '';
  } catch(e) {
    body.innerHTML = `<div style="color:var(--red);padding:12px;font-size:11px">Error: ${esc(e.message)}</div>`;
  }
}

function _fpBar(rate) {
  const pct = Math.round(rate * 100);
  const color = pct >= 50 ? 'var(--red)' : pct >= 25 ? '#ffaa00' : '#34a853';
  return `<div style="display:flex;align-items:center;gap:8px">
    <div style="flex:1;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden">
      <div style="width:${pct}%;height:100%;background:${color};border-radius:3px"></div>
    </div>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${color};min-width:36px">${pct}%</span>
  </div>`;
}

function _renderFpAnalytics(d) {
  const bySource = Object.entries(d.fp_by_source || {})
    .sort((a, b) => b[1].fp_rate - a[1].fp_rate);
  const byType = Object.entries(d.fp_by_type || {})
    .sort((a, b) => b[1].fp_rate - a[1].fp_rate);
  const suggestions = d.suggested_allowlist || [];

  const sourceRows = bySource.length ? bySource.map(([name, s]) => {
    const highFp = s.fp_rate > 0.5 && s.total_iocs >= 5;
    const warn = highFp
      ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 5px;border-radius:2px;background:rgba(218,54,51,0.12);border:1px solid rgba(218,54,51,0.35);color:var(--red);margin-left:6px">HIGH FP</span>`
      : '';
    return `<tr>
      <td style="padding:5px 8px;color:var(--text-bright);font-family:'IBM Plex Mono',monospace;font-size:10px">${esc(name)}${warn}</td>
      <td style="padding:5px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${s.fp_count} / ${s.total_iocs}</td>
      <td style="padding:5px 8px;min-width:140px">${_fpBar(s.fp_rate)}</td>
    </tr>`;
  }).join('') : `<tr><td colspan="3" style="padding:12px;text-align:center;color:var(--text-dim);font-size:11px">No feedback data yet</td></tr>`;

  const typeRows = byType.length ? byType.map(([itype, s]) => `<tr>
    <td style="padding:5px 8px">${_iocTypeBadge(itype)}</td>
    <td style="padding:5px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${s.fp_count} / ${s.total_iocs}</td>
    <td style="padding:5px 8px;min-width:140px">${_fpBar(s.fp_rate)}</td>
  </tr>`).join('') : `<tr><td colspan="3" style="padding:12px;text-align:center;color:var(--text-dim);font-size:11px">No feedback data yet</td></tr>`;

  const suggRows = suggestions.length ? suggestions.map(s => `<tr>
    <td style="padding:5px 8px">${_iocTypeBadge(s.ioc_type)}</td>
    <td style="padding:5px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-bright);word-break:break-all">${esc(s.value)}</td>
    <td style="padding:5px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--red)">${s.fp_count} FP</td>
    <td style="padding:5px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">${esc(s.allowlist_type)}</td>
  </tr>`).join('') : `<tr><td colspan="4" style="padding:12px;text-align:center;color:var(--text-dim);font-size:11px">No suggestions — need ≥3 FP verdicts and 0 TP on same IOC</td></tr>`;

  const tableStyle = 'width:100%;border-collapse:collapse;font-family:\'IBM Plex Mono\',monospace;font-size:11px';
  const thStyle = 'text-align:left;padding:4px 8px;color:var(--text-dim);border-bottom:1px solid var(--border)';

  return `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
      <div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">FP Rate by Source</div>
        <table style="${tableStyle}">
          <thead><tr>
            <th style="${thStyle}">Source</th>
            <th style="${thStyle};text-align:center;width:80px">FP/Total</th>
            <th style="${thStyle}">Rate</th>
          </tr></thead>
          <tbody>${sourceRows}</tbody>
        </table>
      </div>
      <div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">FP Rate by IOC Type</div>
        <table style="${tableStyle}">
          <thead><tr>
            <th style="${thStyle}">Type</th>
            <th style="${thStyle};text-align:center;width:80px">FP/Total</th>
            <th style="${thStyle}">Rate</th>
          </tr></thead>
          <tbody>${typeRows}</tbody>
        </table>
      </div>
    </div>
    <div style="margin-bottom:8px;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em">
        Suggested Allowlist Entries (${suggestions.length})
      </div>
      ${suggestions.length ? `<button onclick="fpAnalyticsApplySuggestions(this)"
        style="padding:3px 10px;font-size:10px;background:rgba(218,54,51,0.08);border:1px solid rgba(218,54,51,0.35);color:var(--red);border-radius:3px;cursor:pointer">
        Apply All to Allowlist
      </button>` : ''}
    </div>
    <table style="${tableStyle}">
      <thead><tr>
        <th style="${thStyle};width:90px">Type</th>
        <th style="${thStyle}">IOC Value</th>
        <th style="${thStyle};text-align:center;width:70px">Verdicts</th>
        <th style="${thStyle};width:100px">Allowlist As</th>
      </tr></thead>
      <tbody>${suggRows}</tbody>
    </table>`;
}

async function fpAnalyticsApplySuggestions(btn) {
  if (!confirm('Bulk-add all suggested entries to the IOC allowlist? Matching IOCs will be deleted.')) return;
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const resp = await fetch('/api/iocs/fp-analytics/apply-suggestions', {
      method: 'POST',
      headers: _authAndClientHeaders(),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const r = await resp.json();
    btn.textContent = `✓ Added ${r.added}`;
    setTimeout(() => fpAnalyticsLoad(true), 1500);
    iocmgmtLoad(1);
    allowlistLoad();
  } catch(e) {
    btn.disabled = false;
    btn.textContent = 'Apply All to Allowlist';
    alert(`Failed: ${e.message}`);
  }
}

async function iocmgmtFeedback(iocId, btn, verdict) {
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const resp = await fetch(`/api/iocs/${encodeURIComponent(iocId)}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ..._authAndClientHeaders() },
      body: JSON.stringify({ verdict }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const updated = await resp.json();
    btn.textContent = '✓';
    const row = btn.closest('tr');
    if (row) {
      const chip = row.querySelector('td:nth-child(3) span');
      if (chip && updated.confidence_score != null) {
        const s = updated.confidence_score >= 75 ? { bg: 'rgba(52,168,83,0.15)', border: 'rgba(52,168,83,0.4)', color: '#34a853' }
                : updated.confidence_score >= 40  ? { bg: 'rgba(255,165,0,0.12)',  border: 'rgba(255,165,0,0.4)',  color: '#ffaa00' }
                :                                    { bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.15)', color: 'var(--text-dim)' };
        chip.style.background = s.bg;
        chip.style.borderColor = s.border;
        chip.style.color = s.color;
        chip.textContent = updated.confidence_score;
      }
      const actCell = row.querySelector('td:nth-child(4)');
      if (actCell && updated.actionability_label) {
        actCell.innerHTML = _iocActionabilityChip(updated.actionability_label);
      }
    }
    if (verdict === 'fp' && updated.source_fp_warning) {
      const w = updated.source_fp_warning;
      _showSourceFpWarning(w.source_name, w.fp_rate, w.fp_count, w.total_iocs);
    }
    setTimeout(() => { btn.disabled = false; btn.textContent = orig; }, 1500);
  } catch(e) {
    btn.textContent = '✗';
    btn.disabled = false;
    setTimeout(() => { btn.textContent = orig; }, 1500);
  }
}

function _showSourceFpWarning(sourceName, fpRate, fpCount, totalIocs) {
  const pct = Math.round(fpRate * 100);
  const existing = document.getElementById('fp-source-warning-banner');
  if (existing) existing.remove();
  const banner = document.createElement('div');
  banner.id = 'fp-source-warning-banner';
  banner.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;background:rgba(218,54,51,0.15);border:1px solid rgba(218,54,51,0.5);border-radius:5px;padding:12px 16px;max-width:360px;font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-bright)';
  banner.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <span style="color:var(--red);font-size:14px">⚠</span>
      <strong style="color:var(--red)">High FP Source Warning</strong>
      <button onclick="this.closest('#fp-source-warning-banner').remove()" style="margin-left:auto;background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:14px">✕</button>
    </div>
    <div style="color:var(--text-dim);line-height:1.5">
      Source <strong style="color:var(--text-bright)">${esc(sourceName)}</strong> now has a
      <strong style="color:var(--red)">${pct}% FP rate</strong> (${fpCount}/${totalIocs} IOCs).
      Consider reviewing or suppressing IOCs from this source.
    </div>`;
  document.body.appendChild(banner);
  setTimeout(() => banner.remove(), 12000);
}

// Close modal on backdrop click
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('iocmgmt-modal').addEventListener('click', function(e) {
    if (e.target === this) this.style.display = 'none';
  });
});
