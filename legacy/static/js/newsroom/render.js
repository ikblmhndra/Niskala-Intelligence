// ── RENDERING ─────────────────────────────────────────────
function renderNewsItem(a) {
  const key  = storeArticle(a);
  const tags = [...(a.impacted_industries||[]).slice(0,2), ...(a.threat_actors||[]).slice(0,1)];
  const srEntry = _srScoreMap[a.source?.toLowerCase()];
  const srBadge = srEntry
    ? `<span class="sr-inline-badge" title="${srEntry.admiralty_code} — ${srEntry.reliability_grade}: Reliability, ${srEntry.credibility_code}: Credibility">${srEntry.admiralty_code}</span>`
    : '';
  const iocCount = Object.values(a.iocs || {}).reduce((s, v) => s + v.length, 0);
  const iocBadge = iocCount > 0
    ? `<span class="ioc-badge" title="${iocCount} indicator(s) of compromise extracted">IOC:${iocCount}</span>`
    : '';
  return `<div class="news-item" onclick="openModal(${key})">
    <div class="news-item-header">
      <div class="news-headline">${esc(a.title)}</div>
    </div>
    <div class="news-meta">
      ${tags.map(t=>`<span class="news-tag">${esc(t)}</span>`).join('')}
      ${iocBadge}
      <span class="news-time">${timeAgo(a.posted_on)}</span>
      <span class="news-source">${esc(a.source)}${srBadge}</span>
    </div>
  </div>`;
}

// ── RANSOMWARE VICTIMS ───────────────────────────────────
let _rwVictimPage = 1;
const RW_VICTIM_PAGE_SIZE = 20;

function renderRwVictimRow(v) {
  const url = v.post_url && v.post_url !== 'Unknown'
    ? `<a href="${esc(v.post_url)}" target="_blank" rel="noopener" style="color:var(--red);text-decoration:none">↗</a>`
    : '—';
  return `<div style="display:grid;grid-template-columns:80px 1fr 76px 14px;gap:4px;padding:5px 4px;border-bottom:1px solid rgba(255,255,255,.04);align-items:start;min-width:0">
    <span style="color:#DA3633;font-weight:600;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(v.group_name)}">${esc(v.group_name)}</span>
    <div style="min-width:0">
      <div style="color:var(--text-bright);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(v.victim)}">${esc(v.victim)}</div>
      <div style="color:var(--text-dim);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(v.industry)}">${esc(v.industry)}</div>
    </div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">
      <div title="Published">${esc((v.published||'').slice(0,10))}</div>
      <div style="opacity:.6;font-size:9px" title="Discovered">${esc((v.discovered||'').slice(0,10))}</div>
    </div>
    <span>${url}</span>
  </div>`;
}

function renderRwVictimHeader() {
  return `<div style="display:grid;grid-template-columns:80px 1fr 76px 14px;gap:4px;padding:4px 4px 3px;background:rgba(255,255,255,.03);font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em">
    <span>Group</span><span>Victim / Industry</span><span>Published / Disc.</span><span></span>
  </div>`;
}

async function loadRwVictims(page) {
  _rwVictimPage = page || 1;
  const el    = document.getElementById('rw-victim-list');
  const pager = document.getElementById('rw-victim-pager');
  el.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-dim)">Loading…</div>';

  const params = new URLSearchParams({
    page:      _rwVictimPage,
    page_size: RW_VICTIM_PAGE_SIZE,
  });
  const group    = document.getElementById('rw-f-group')?.value.trim();
  const country  = document.getElementById('rw-f-country')?.value.trim();
  const industry = document.getElementById('rw-f-industry')?.value.trim();
  if (group)    params.set('group',    group);
  if (country)  params.set('country',  country);
  if (industry) params.set('industry', industry);

  try {
    const resp = await fetch(`/api/ransomware/victims?${params}`, { headers: _authHeader() });
    if (!resp.ok) throw new Error(resp.statusText);
    const data = await resp.json();
    document.getElementById('rw-count').textContent = `${data.total} victims`;
    state.rw.total = data.total;
    if (!data.victims.length) {
      el.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-dim)">No victims found</div>';
      pager.innerHTML = '';
      return;
    }
    el.innerHTML = renderRwVictimHeader() + data.victims.map(renderRwVictimRow).join('');
    const totalPages = Math.ceil(data.total / RW_VICTIM_PAGE_SIZE);
    pager.innerHTML = totalPages > 1
      ? `<span style="color:var(--text-dim)">Page ${_rwVictimPage} / ${totalPages} &nbsp;</span>`
        + (_rwVictimPage > 1 ? `<button class="btn-apply" style="font-size:10px;padding:2px 8px;margin:0 2px" onclick="loadRwVictims(${_rwVictimPage-1})">‹ Prev</button>` : '')
        + (_rwVictimPage < totalPages ? `<button class="btn-apply" style="font-size:10px;padding:2px 8px;margin:0 2px" onclick="loadRwVictims(${_rwVictimPage+1})">Next ›</button>` : '')
      : '';
  } catch(e) {
    el.innerHTML = `<div style="padding:12px;text-align:center;color:var(--red)">Error: ${e.message}</div>`;
  }
}

const RW_ARTICLE_PAGE_SIZE = 8;

async function loadRwArticles(page) {
  state.rw.page = page || 1;
  const el = document.getElementById('rw-list');
  el.innerHTML = loadingHTML();

  try {
    const params = new URLSearchParams({ page: state.rw.page, page_size: RW_ARTICLE_PAGE_SIZE });
    const resp = await fetch(`/api/ransomware/related-articles?${params}`, { headers: _authHeader() });
    if (!resp.ok) throw new Error(resp.statusText);
    const data = await resp.json();

    el.innerHTML = data.articles.length
      ? data.articles.map(renderRwItem).join('')
      : emptyHTML('No related ransomware articles');

    state.rw.total = data.total;
    _renderRwArticlePager();
    return data.total;
  } catch(e) {
    el.innerHTML = `<div style="padding:12px;text-align:center;color:var(--red)">Error: ${e.message}</div>`;
    return 0;
  }
}

function _renderRwArticlePager() {
  const el = document.getElementById('rw-pager');
  if (!el) return;
  const total = Math.ceil(state.rw.total / RW_ARTICLE_PAGE_SIZE);
  if (total <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="loadRwArticles(${state.rw.page - 1})" ${state.rw.page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${state.rw.page}</strong> / ${total}</span>
    <button class="pager-btn" onclick="loadRwArticles(${state.rw.page + 1})" ${state.rw.page >= total ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

function renderRwItem(a) {
  const key     = storeArticle(a);
  const actors  = a.threat_actors || [];
  const group   = actors.length ? actors[0] : 'Unknown Group';
  const country = (a.mentioned_countries||[]).slice(0,1).join(', ') || '—';
  const industry= (a.impacted_industries||[]).slice(0,1).join(', ') || '—';
  const victimBadge = a.victim_name
    ? `<span class="rw-badge" style="color:var(--red);border-color:rgba(218,54,51,.3)">🎯 ${esc(a.victim_name)}</span>`
    : '';
  return `<div class="rw-item" onclick="openModal(${key})">
    <div class="rw-group-name">${esc(group)}</div>
    <div class="rw-victim">${esc(a.title)}</div>
    <div class="rw-detail">
      ${victimBadge}
      <span class="rw-badge">🌐 ${esc(country)}</span>
      <span class="rw-badge">${esc(industry)}</span>
      <span class="rw-badge">${timeAgo(a.posted_on)}</span>
    </div>
  </div>`;
}

function renderTableRow(a) {
  const key = storeArticle(a);
  return `<tr onclick="openModal(${key})" style="cursor:pointer">
    <td style="max-width:280px;font-size:12px;color:var(--text-bright);line-height:1.4">${esc(a.title)}</td>
    <td style="font-size:11px;color:var(--text-dim);white-space:nowrap">${esc(a.source)}</td>
    <td><span class="news-tag">${esc(a.news_type)}</span></td>
    <td style="font-size:11px;color:var(--text-dim);max-width:180px">${esc((a.impacted_industries||[]).join(', ')||'—')}</td>
    <td style="font-size:11px;color:var(--text-dim);max-width:180px">${esc((a.mentioned_countries||[]).join(', ')||'—')}</td>
    <td style="font-size:11px;color:var(--text-dim)">${esc((a.threat_actors||[]).join(', ')||'—')}</td>
    <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);white-space:nowrap">${esc(a.posted_on)}</td>
  </tr>`;
}

// ── PAGER ─────────────────────────────────────────────────
function renderPager(panelId) {
  const s = state[panelId];
  const total = Math.max(1, Math.ceil(s.total / PAGE_SIZE));
  const el = document.getElementById(panelId + '-pager');
  if (!el) return;
  if (total <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="goPage('${panelId}',-1)" ${s.page<=1?'disabled':''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${s.page}</strong> / ${total}</span>
    <button class="pager-btn" onclick="goPage('${panelId}',1)" ${s.page>=total?'disabled':''}>Next ▶</button>
  </div>`;
}

async function goPage(panelId, delta) {
  const s = state[panelId];
  const total = Math.ceil(s.total / PAGE_SIZE);
  s.page = Math.min(Math.max(1, s.page + delta), total);
  if (panelId === 'rw') { await loadRwArticles(state.rw.page); return; }
  if (panelId === 'watchlist')  { await loadWatchlistPanel();  return; }
  if (panelId === 'techstack')  { await loadTechStackPanel();  return; }
  await loadPanel(panelId);
}

