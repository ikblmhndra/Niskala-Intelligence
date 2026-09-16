// ── THREAT ACTOR ROOM ─────────────────────────────────────
const _taState   = { page: 1, pageSize: 50, total: 0, sortBy: 'name', sortDir: 'asc' };
let   _taGroupMap = {};   // _id → group (for safe deletion)

async function loadTAGroups() {
  const tbody = document.getElementById('ta-tbody');
  tbody.innerHTML = `<tr><td colspan="5" class="ta-td">${loadingHTML()}</td></tr>`;

  try {
    const params = new URLSearchParams({
      page:      _taState.page,
      page_size: _taState.pageSize,
      sort_by:   _taState.sortBy,
      sort_dir:  _taState.sortDir,
    });
    const search = document.getElementById('ta-search').value.trim();
    if (search) params.set('search', search);

    const _taCtrl = new AbortController();
    const _taTimeout = setTimeout(() => _taCtrl.abort(), 15000);
    const [groupResp, wlNamesResp] = await Promise.all([
      fetch(`/api/ta/groups?${params}`, { signal: _taCtrl.signal }),
      fetch('/api/ta/watchlist-names', { headers: _clientHeader(), signal: _taCtrl.signal }),
    ]);
    clearTimeout(_taTimeout);
    if (!groupResp.ok) throw new Error(groupResp.statusText);
    const d = await groupResp.json();
    const wlNamesData = wlNamesResp.ok ? await wlNamesResp.json() : { names: [] };
    const watchedSet = new Set((wlNamesData.names || []).map(n => n.toLowerCase()));

    _taState.total = d.total;
    document.getElementById('ta-total').textContent =
      `${d.total} group${d.total !== 1 ? 's' : ''} tracked`;
    document.getElementById('ta-count').textContent = d.total;

    _taGroupMap = {};
    if (!d.groups.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="ta-td">${emptyHTML('No threat actor groups found')}</td></tr>`;
    } else {
      const offset = (_taState.page - 1) * _taState.pageSize;
      tbody.innerHTML = d.groups.map((g, i) => {
        _taGroupMap[g._id] = g;
        const isWatched = watchedSet.has(g.name.toLowerCase());
        const watchBtn = isWatched
          ? `<button class="ta-watch-btn watched" data-name="${esc(g.name)}"
                     onclick="taUnwatchFromTracked(this.dataset.name)" title="Remove from watchlist">◎ UNWATCH</button>`
          : `<button class="ta-watch-btn" data-name="${esc(g.name)}"
                     onclick="taWatchGroup(this.dataset.name)" title="Add to watchlist">⊕ WATCH</button>`;
        return `<tr>
          <td class="ta-td ta-num">${offset + i + 1}</td>
          <td class="ta-td ta-name">${esc(g.name)}</td>
          <td class="ta-td ta-date">${esc(g.added_date)}</td>
          <td class="ta-td"><span class="ta-source-badge">${esc(g.source)}</span></td>
          <td class="ta-td" style="white-space:nowrap">
            ${watchBtn}
            <button class="ta-delete-btn" data-id="${esc(g._id)}"
                    onclick="taDeleteGroup(this.dataset.id)">✕ REMOVE</button>
          </td>
        </tr>`;
      }).join('');
    }

    _renderTAPager();
    _updateSortHeaders();
  } catch (e) {
    console.error('TA load error:', e);
    tbody.innerHTML = `<tr><td colspan="5" class="ta-td">${emptyHTML('Failed to load groups')}</td></tr>`;
  }
}

function taSortBy(field) {
  if (_taState.sortBy === field) {
    _taState.sortDir = _taState.sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    _taState.sortBy  = field;
    _taState.sortDir = 'asc';
  }
  _taState.page = 1;
  loadTAGroups();
}

function _updateSortHeaders() {
  ['name', 'added_date', 'source'].forEach(field => {
    const th  = document.getElementById('th-' + field);
    if (!th) return;
    const ind = th.querySelector('.sort-ind');
    if (field === _taState.sortBy) {
      th.classList.add('sort-active');
      ind.textContent = _taState.sortDir === 'asc' ? '↑' : '↓';
    } else {
      th.classList.remove('sort-active');
      ind.textContent = '⇅';
    }
  });
}

function _renderTAPager() {
  const totalPages = Math.max(1, Math.ceil(_taState.total / _taState.pageSize));
  const el = document.getElementById('ta-pager');
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="taGoPage(-1)" ${_taState.page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${_taState.page}</strong> / ${totalPages}</span>
    <button class="pager-btn" onclick="taGoPage(1)" ${_taState.page >= totalPages ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

async function taGoPage(delta) {
  const totalPages = Math.ceil(_taState.total / _taState.pageSize);
  _taState.page = Math.min(Math.max(1, _taState.page + delta), totalPages);
  await loadTAGroups();
}

function taSearchInput() {
  _taState.page = 1;   // reset to page 1 on new search
  loadTAGroups();
}

function taSetPageSize() {
  _taState.pageSize = parseInt(document.getElementById('ta-page-size').value, 10);
  _taState.page = 1;
  loadTAGroups();
}

function _taStatus(msg, ok) {
  const el = document.getElementById('ta-status');
  el.textContent = msg;
  el.className = `ta-status show ${ok ? 'ok' : 'err'}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3500);
}

function taAddGroup() {
  const input = document.getElementById('ta-input');
  const name  = input.value.trim();
  if (!name) return;

  requireTAAuth(async (password) => {
    try {
      const resp = await fetch('/api/ta/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + password },
        body: JSON.stringify({ name }),
      });
      if (resp.status === 401) { _authFailed(); return; }
      const d = await resp.json();
      if (d.success) {
        input.value = '';
        _taStatus(`"${name}" added`, true);
        _taState.page = 1;
        loadTAGroups();
      } else {
        const reason = d.reason === 'whitelisted' ? 'group is whitelisted' : 'group already exists';
        _taStatus(`Cannot add "${name}": ${reason}`, false);
      }
    } catch (e) {
      console.error(e);
      _taStatus('Failed to add group', false);
    }
  });
}

function taDeleteGroup(groupId) {
  const g = _taGroupMap[groupId];
  if (!g) return;

  requireTAAuth((password) => {
    showConfirmModal({
      title:   'Remove Threat Actor',
      okLabel: '✕ Remove',
      body: `
        <p style="font-size:13px;color:var(--text);line-height:1.7;margin-bottom:14px">
          Remove <strong style="color:var(--red);letter-spacing:.03em">${esc(g.name)}</strong>
          from threat actor tracking?
        </p>
        <p style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);
                  border:1px solid var(--border-bright);background:var(--surface2);
                  padding:8px 12px;border-radius:2px;line-height:1.6">
          ⚠&nbsp; This group will be whitelisted and cannot be re-added.
        </p>`,
      onConfirm: async () => {
        try {
          const resp = await fetch(
            `/api/ta/groups/${encodeURIComponent(groupId)}?group_name=${encodeURIComponent(g.name)}`,
            { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + password } }
          );
          if (resp.status === 401) { _authFailed(); return; }
          const d = await resp.json();
          if (d.success) {
            _taStatus(`"${g.name}" removed`, true);
            loadTAGroups();
          }
        } catch (e) {
          console.error(e);
          _taStatus('Failed to remove group', false);
        }
      },
    });
  });
}

// ── WHITELIST SUB-VIEW ────────────────────────────────────
let _taView = 'tracked';   // 'tracked' | 'whitelist' | 'watchlist'

const _wlState = { page: 1, pageSize: 50, total: 0, sortBy: 'name', sortDir: 'asc' };

function taSwitchView(view) {
  _taView = view;
  document.getElementById('ta-view-tracked').style.display   = view === 'tracked'   ? '' : 'none';
  document.getElementById('ta-view-whitelist').style.display  = view === 'whitelist' ? '' : 'none';
  document.getElementById('ta-view-watchlist').style.display  = view === 'watchlist' ? '' : 'none';
  document.getElementById('taview-tracked').classList.toggle('active',   view === 'tracked');
  document.getElementById('taview-whitelist').classList.toggle('active', view === 'whitelist');
  document.getElementById('taview-watchlist').classList.toggle('active', view === 'watchlist');

  if (view === 'whitelist') {
    _wlState.page = 1;
    loadWLGroups();
  }
  if (view === 'watchlist') {
    _tawState.page = 1;
    loadTAWatchlist();
  }
}

async function loadWLGroups() {
  const tbody = document.getElementById('wl-tbody');
  tbody.innerHTML = `<tr><td colspan="4" class="ta-td">${loadingHTML()}</td></tr>`;

  try {
    const params = new URLSearchParams({
      page:      _wlState.page,
      page_size: _wlState.pageSize,
      sort_by:   _wlState.sortBy,
      sort_dir:  _wlState.sortDir,
    });
    const search = document.getElementById('wl-search').value.trim();
    if (search) params.set('search', search);

    const resp = await fetch(`/api/ta/whitelist?${params}`);
    if (!resp.ok) throw new Error(resp.statusText);
    const d = await resp.json();

    _wlState.total = d.total;
    document.getElementById('wl-total').textContent =
      `${d.total} group${d.total !== 1 ? 's' : ''} whitelisted`;
    document.getElementById('wl-submenu-count').textContent = d.total;

    if (!d.items.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="ta-td">${emptyHTML('No whitelisted groups')}</td></tr>`;
    } else {
      const offset = (_wlState.page - 1) * _wlState.pageSize;
      tbody.innerHTML = d.items.map((item, i) => `<tr>
        <td class="ta-td ta-num">${offset + i + 1}</td>
        <td class="ta-td ta-name">${esc(item.name)}</td>
        <td class="ta-td ta-date">${esc(item.added_date || '—')}</td>
        <td class="ta-td">
          <button class="ta-restore-btn" data-name="${esc(item.name)}"
                  onclick="taRestoreGroup(this.dataset.name)">↩ RESTORE</button>
        </td>
      </tr>`).join('');
    }

    _renderWLPager();
    _updateWLSortHeaders();
  } catch (e) {
    console.error('WL load error:', e);
    tbody.innerHTML = `<tr><td colspan="4" class="ta-td">${emptyHTML('Failed to load whitelist')}</td></tr>`;
  }
}

function wlSortBy(field) {
  if (_wlState.sortBy === field) {
    _wlState.sortDir = _wlState.sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    _wlState.sortBy  = field;
    _wlState.sortDir = 'asc';
  }
  _wlState.page = 1;
  loadWLGroups();
}

function _updateWLSortHeaders() {
  ['name', 'added_date'].forEach(field => {
    const th  = document.getElementById('wl-th-' + field);
    if (!th) return;
    const ind = th.querySelector('.sort-ind');
    if (field === _wlState.sortBy) {
      th.classList.add('sort-active');
      ind.textContent = _wlState.sortDir === 'asc' ? '↑' : '↓';
    } else {
      th.classList.remove('sort-active');
      ind.textContent = '⇅';
    }
  });
}

function _renderWLPager() {
  const totalPages = Math.max(1, Math.ceil(_wlState.total / _wlState.pageSize));
  const el = document.getElementById('wl-pager');
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="wlGoPage(-1)" ${_wlState.page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${_wlState.page}</strong> / ${totalPages}</span>
    <button class="pager-btn" onclick="wlGoPage(1)" ${_wlState.page >= totalPages ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

async function wlGoPage(delta) {
  const totalPages = Math.ceil(_wlState.total / _wlState.pageSize);
  _wlState.page = Math.min(Math.max(1, _wlState.page + delta), totalPages);
  await loadWLGroups();
}

function wlSearchInput() {
  _wlState.page = 1;
  loadWLGroups();
}

function wlSetPageSize() {
  _wlState.pageSize = parseInt(document.getElementById('wl-page-size').value, 10);
  _wlState.page = 1;
  loadWLGroups();
}

function taRestoreGroup(name) {
  requireTAAuth((password) => {
    showConfirmModal({
      title:   'Restore Threat Actor',
      okLabel: '↩ Restore',
      okColor: 'var(--green)',
      body: `
        <p style="font-size:13px;color:var(--text);line-height:1.7;margin-bottom:14px">
          Restore <strong style="color:var(--green);letter-spacing:.03em">${esc(name)}</strong>
          to threat actor tracking?
        </p>
        <p style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);
                  border:1px solid var(--border-bright);background:var(--surface2);
                  padding:8px 12px;border-radius:2px;line-height:1.6">
          ℹ&nbsp; This group will be removed from the whitelist and can be tracked again.
        </p>`,
      onConfirm: async () => {
        try {
          const resp = await fetch(
            `/api/ta/whitelist/${encodeURIComponent(name)}`,
            { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + password } }
          );
          if (resp.status === 401) { _authFailed(); return; }
          const d = await resp.json();
          if (d.success) {
            _taStatus(`"${name}" restored`, true);
            loadWLGroups();
          } else {
            _taStatus(`Could not restore "${name}"`, false);
          }
        } catch (e) {
          console.error(e);
          _taStatus('Failed to restore group', false);
        }
      },
    });
  });
}

// ── TA WATCHLIST MANAGEMENT ───────────────────────────────
const _tawState = { page: 1, pageSize: 50, total: 0, sortBy: 'name', sortDir: 'asc' };

async function loadTAWatchlist() {
  const grid = document.getElementById('taw-card-grid');
  grid.innerHTML = `<div class="loading-state" style="grid-column:1/-1">${loadingHTML()}</div>`;

  try {
    const params = new URLSearchParams({
      page:      _tawState.page,
      page_size: _tawState.pageSize,
      sort_by:   _tawState.sortBy,
      sort_dir:  _tawState.sortDir,
    });
    const search = document.getElementById('taw-search').value.trim();
    if (search) params.set('search', search);

    const resp = await fetch(`/api/ta/watchlist?${params}`, { headers: _clientHeader() });
    if (!resp.ok) throw new Error(resp.statusText);
    const d = await resp.json();

    _tawState.total = d.total;
    document.getElementById('taw-total').textContent =
      `${d.total} group${d.total !== 1 ? 's' : ''} watched`;
    document.getElementById('taw-submenu-count').textContent = d.total;

    if (!d.items.length) {
      grid.innerHTML = `<div class="loading-state" style="grid-column:1/-1">${emptyHTML('No groups in watchlist')}</div>`;
    } else {
      // Check which actors already have profiles + fetch article counts in parallel
      const [profileChecks, articleChecks] = await Promise.all([
        Promise.allSettled(
          d.items.map(item =>
            fetch(`/api/ta/profile/${encodeURIComponent(item.name)}`).then(r => r.json())
          )
        ),
        Promise.allSettled(
          d.items.map(item =>
            fetch(`/api/articles?threat_actor=${encodeURIComponent(item.name)}&page_size=1`, { headers: _clientHeader() })
              .then(r => r.json())
          )
        ),
      ]);
      grid.innerHTML = d.items.map((item, i) => {
        const profileResult = profileChecks[i];
        const hasProfile = profileResult.status === 'fulfilled' && profileResult.value.exists;
        const ds = item.dormancy_state || 'DORMANT';
        const dsIcon = ds === 'ACTIVE' ? '🟢' : ds === 'RESURGENT' ? '🔴' : '🟡';
        const dsColor = ds === 'ACTIVE' ? 'var(--green)' : ds === 'RESURGENT' ? 'var(--red)' : 'var(--accent3)';
        const mmContainerId = `taw-mm-${esc(item.name).replace(/\s+/g,'-')}`;

        const artData = articleChecks[i];
        const artTotal = (artData.status === 'fulfilled' && artData.value.total != null) ? artData.value.total : 0;
        const artLabel = artTotal > 0 ? `📰 ${artTotal} Article${artTotal !== 1 ? 's' : ''}` : '📰 No Articles';

        return `<div class="taw-card" id="taw-card-${esc(item.name).replace(/\s+/g,'-')}">
          <div class="taw-card-name" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">${esc(item.name)} <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;border-radius:2px;background:${dsColor}22;color:${dsColor};border:1px solid ${dsColor}44;">${dsIcon} ${ds}</span></div>
          <div class="taw-card-meta">
            <span>Added: ${esc(item.added_date || '—')}</span>
            <span class="taw-card-badge ${hasProfile ? 'has-profile' : 'no-profile'}">${hasProfile ? '✓ PROFILE' : 'NO PROFILE'}</span>
          </div>
          <div class="taw-card-actions">
            <button class="taw-btn-ai" data-name="${esc(item.name)}"
                    onclick="taGenerateProfile(this, this.dataset.name)">⚡ AI Generate</button>
            ${hasProfile ? `<button class="taw-btn-view" data-name="${esc(item.name)}"
                    onclick="taViewProfile(this.dataset.name)">👁 View Profile</button>` : ''}
            <button id="mm-toggle-btn-${mmContainerId}" class="taw-btn-mm"
                    onclick="mmToggleInline('${mmContainerId}','threat_actor','${esc(item.name)}')">⬡ Mind Map</button>
            <button class="ta-delete-btn" data-name="${esc(item.name)}"
                    onclick="taUnwatchGroup(this.dataset.name)" style="flex:0">✕</button>
          </div>
          <button class="taw-btn-articles" onclick="tawOpenArticlesModal('${esc(item.name)}')" ${artTotal === 0 ? 'disabled' : ''}>
            ${artLabel}
          </button>
          <div id="${mmContainerId}" style="display:none;margin-top:8px">
            <div class="mm-diagram" style="background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px;padding:12px;overflow:auto;max-height:400px"></div>
          </div>
        </div>`;
      }).join('');
    }

    _renderTAWPager();
    _updateTAWSortHeaders();
  } catch (e) {
    console.error('TAW load error:', e);
    grid.innerHTML = `<div class="loading-state" style="grid-column:1/-1">${emptyHTML('Failed to load watchlist')}</div>`;
  }
}

const _tawArtModal = { name: null, page: 1, pageSize: 20, total: 0 };

async function tawOpenArticlesModal(name) {
  _tawArtModal.name = name;
  _tawArtModal.page = 1;
  document.getElementById('taw-art-modal-title').textContent = name;
  document.getElementById('taw-art-modal').style.display = 'block';
  document.body.style.overflow = 'hidden';
  await _tawArtModalLoad();
}

function tawCloseArticlesModal() {
  document.getElementById('taw-art-modal').style.display = 'none';
  document.body.style.overflow = '';
  _tawArtModal.name = null;
}

async function _tawArtModalLoad() {
  const body = document.getElementById('taw-art-modal-body');
  const pager = document.getElementById('taw-art-modal-pager');
  body.innerHTML = `<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Loading…</div></div>`;
  pager.innerHTML = '';

  const params = new URLSearchParams({
    threat_actor: _tawArtModal.name,
    page: _tawArtModal.page,
    page_size: _tawArtModal.pageSize,
  });

  try {
    const resp = await fetch(`/api/articles?${params}`, { headers: _clientHeader() });
    if (!resp.ok) throw new Error(resp.statusText);
    const data = await resp.json();
    _tawArtModal.total = data.total || 0;

    document.getElementById('taw-art-modal-count').textContent =
      `${_tawArtModal.total} article${_tawArtModal.total !== 1 ? 's' : ''}`;

    body.innerHTML = data.articles && data.articles.length
      ? data.articles.map(renderNewsItem).join('')
      : `<div class="empty-state" style="padding:40px 0;text-align:center;color:var(--text-dim)">No articles found for this threat actor</div>`;

    const totalPages = Math.max(1, Math.ceil(_tawArtModal.total / _tawArtModal.pageSize));
    if (totalPages > 1) {
      const prev = _tawArtModal.page > 1;
      const next = _tawArtModal.page < totalPages;
      pager.innerHTML = `
        <button class="pager-btn" onclick="_tawArtModalPage(${_tawArtModal.page - 1})" ${prev ? '' : 'disabled'}>‹ Prev</button>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">
          Page ${_tawArtModal.page} / ${totalPages}
        </span>
        <button class="pager-btn" onclick="_tawArtModalPage(${_tawArtModal.page + 1})" ${next ? '' : 'disabled'}>Next ›</button>`;
    }
  } catch (e) {
    body.innerHTML = `<div class="empty-state" style="padding:40px 0;text-align:center;color:var(--red)">Failed to load articles</div>`;
  }
}

async function _tawArtModalPage(page) {
  _tawArtModal.page = page;
  document.getElementById('taw-art-modal-body').scrollTop = 0;
  await _tawArtModalLoad();
}

function tawSortBy(field) {
  if (_tawState.sortBy === field) {
    _tawState.sortDir = _tawState.sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    _tawState.sortBy  = field;
    _tawState.sortDir = 'asc';
  }
  _tawState.page = 1;
  loadTAWatchlist();
}

function _updateTAWSortHeaders() {
  ['name', 'added_date'].forEach(field => {
    const btn = document.getElementById('taw-th-' + field);
    if (!btn) return;
    const ind = btn.querySelector('.sort-ind');
    if (field === _tawState.sortBy) {
      btn.classList.add('sort-active');
      if (ind) ind.textContent = _tawState.sortDir === 'asc' ? '↑' : '↓';
    } else {
      btn.classList.remove('sort-active');
      if (ind) ind.textContent = '⇅';
    }
  });
}

function _renderTAWPager() {
  const totalPages = Math.max(1, Math.ceil(_tawState.total / _tawState.pageSize));
  const el = document.getElementById('taw-pager');
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="tawGoPage(-1)" ${_tawState.page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${_tawState.page}</strong> / ${totalPages}</span>
    <button class="pager-btn" onclick="tawGoPage(1)" ${_tawState.page >= totalPages ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

async function tawGoPage(delta) {
  const totalPages = Math.ceil(_tawState.total / _tawState.pageSize);
  _tawState.page = Math.min(Math.max(1, _tawState.page + delta), totalPages);
  await loadTAWatchlist();
}

function tawSearchInput() { _tawState.page = 1; loadTAWatchlist(); }

function tawOpenNavigator() {
  const layerUrl = encodeURIComponent(`${window.location.origin}/api/ta/watchlist/navigator-layer`);
  window.open(`https://mitre-attack.github.io/attack-navigator/#layerURL=${layerUrl}`, '_blank');
}

function tawSetPageSize() {
  _tawState.pageSize = parseInt(document.getElementById('taw-page-size').value, 10);
  _tawState.page = 1;
  loadTAWatchlist();
}

function taWatchGroup(name) {
  requireTAAuth(async (password) => {
    try {
      const resp = await fetch('/api/ta/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + password, ..._clientHeader() },
        body: JSON.stringify({ name }),
      });
      if (resp.status === 401) { _authFailed(); return; }
      const d = await resp.json();
      if (d.success) {
        _taStatus(`"${name}" added to watchlist`, true);
        loadTAGroups();
      } else {
        _taStatus(`"${name}" already in watchlist`, false);
      }
    } catch (e) {
      console.error(e);
      _taStatus('Failed to add to watchlist', false);
    }
  });
}

function taUnwatchFromTracked(name) {
  requireTAAuth((password) => {
    showConfirmModal({
      title:   'Remove from Watchlist',
      okLabel: '✕ Remove',
      okColor: 'var(--red)',
      body: `<p style="font-size:13px;color:var(--text);line-height:1.7">
        Remove <strong style="color:var(--accent)">${esc(name)}</strong> from the watchlist?
      </p>`,
      onConfirm: async () => {
        try {
          const resp = await fetch(
            `/api/ta/watchlist/${encodeURIComponent(name)}`,
            { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + password, ..._clientHeader() } }
          );
          if (resp.status === 401) { _authFailed(); return; }
          if ((await resp.json()).success) {
            _taStatus(`"${name}" removed from watchlist`, true);
            loadTAGroups();
          }
        } catch (e) {
          console.error(e);
          _taStatus('Failed to remove from watchlist', false);
        }
      },
    });
  });
}

function taUnwatchGroup(name) {
  requireTAAuth((password) => {
    showConfirmModal({
      title:   'Remove from Watchlist',
      okLabel: '✕ Remove',
      okColor: 'var(--red)',
      body: `<p style="font-size:13px;color:var(--text);line-height:1.7">
        Remove <strong style="color:var(--accent)">${esc(name)}</strong> from the watchlist?
      </p>`,
      onConfirm: async () => {
        try {
          const resp = await fetch(
            `/api/ta/watchlist/${encodeURIComponent(name)}`,
            { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + password, ..._clientHeader() } }
          );
          if (resp.status === 401) { _authFailed(); return; }
          if ((await resp.json()).success) {
            _taStatus(`"${name}" removed from watchlist`, true);
            loadTAWatchlist();
          }
        } catch (e) {
          console.error(e);
          _taStatus('Failed to remove from watchlist', false);
        }
      },
    });
  });
}

// ── TA PROFILE GENERATION & MODAL ────────────────────────
let _tapCurrentActor = null;
let _tapCurrentProfile = null;

function taGenerateProfile(btn, actorName) {
  requireTAAuth(async (password) => {
    btn.disabled = true;
    btn.textContent = '⏳ Generating…';
    try {
      const resp = await fetch('/api/ta/profile/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + password },
        body: JSON.stringify({ name: actorName }),
      });
      if (resp.status === 401) { _authFailed(); btn.disabled = false; btn.textContent = '⚡ AI Generate'; return; }
      if (!resp.ok) throw new Error(await resp.text());
      const d = await resp.json();
      if (d.success) {
        _taStatus(`Profile generated for "${actorName}"`, true);
        loadTAWatchlist();
        taShowProfileModal(actorName, d.profile);
      }
    } catch (e) {
      console.error(e);
      _taStatus('Profile generation failed', false);
      btn.disabled = false;
      btn.textContent = '⚡ AI Generate';
    }
  });
}

async function taViewProfile(actorName) {
  try {
    const resp = await fetch(`/api/ta/profile/${encodeURIComponent(actorName)}`);
    const d = await resp.json();
    if (d.exists) {
      taShowProfileModal(actorName, d.profile);
    } else {
      _taStatus('No profile found — generate one first', false);
    }
  } catch (e) {
    console.error(e);
    _taStatus('Failed to load profile', false);
  }
}

function taRegenProfile() {
  if (!_tapCurrentActor) return;
  closeTAProfileModal();
  // Find the button in card grid
  const cards = document.querySelectorAll('.taw-card');
  for (const card of cards) {
    const btn = card.querySelector('.taw-btn-ai');
    if (btn && btn.dataset.name === _tapCurrentActor) {
      taGenerateProfile(btn, _tapCurrentActor);
      return;
    }
  }
  // Fallback: trigger without a real button
  const fakeBtn = { disabled: false, textContent: '', dataset: { name: _tapCurrentActor } };
  taGenerateProfile(fakeBtn, _tapCurrentActor);
}

let _tapTimelineChart = null;

function _tapDormancyBadge(state) {
  const map = { ACTIVE: ['🟢', 'var(--green)'], DORMANT: ['🟡', 'var(--accent3)'], RESURGENT: ['🔴', 'var(--red)'] };
  const [icon, color] = map[state] || ['⚪', 'var(--text-dim)'];
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:2px 8px;border-radius:2px;background:${color}22;color:${color};border:1px solid ${color}44;margin-left:8px;">${icon} ${state}</span>`;
}

async function _tapLoadTimeline(actorName) {
  const wrap = document.getElementById('tap-timeline-wrap');
  if (!wrap) return;
  wrap.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim);padding:8px 0;">Loading timeline…</div>';
  try {
    const resp = await fetch(`/api/ta/${encodeURIComponent(actorName)}/timeline?months=24`, {
      headers: _authHeader(),
    });
    if (!resp.ok) throw new Error(resp.statusText);
    const tl = await resp.json();

    const badgeEl = document.getElementById('tap-dormancy-badge');
    if (badgeEl) badgeEl.innerHTML = _tapDormancyBadge(tl.dormancy_state);

    wrap.innerHTML = `<div style="position:relative;height:160px;margin-bottom:8px;"><canvas id="tap-timeline-canvas"></canvas></div>
      <div id="tap-timeline-transitions" style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);line-height:1.8;"></div>`;

    if (_tapTimelineChart) { _tapTimelineChart.destroy(); _tapTimelineChart = null; }
    const ctx = document.getElementById('tap-timeline-canvas').getContext('2d');
    _tapTimelineChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: tl.months,
        datasets: [
          { label: 'Articles', data: tl.article_counts, borderColor: 'rgba(47,129,247,.8)', backgroundColor: 'rgba(47,129,247,.15)', fill: true, tension: 0.3, pointRadius: 2 },
          { label: 'Tweets',   data: tl.tweet_counts,   borderColor: 'rgba(0,191,255,.8)',   backgroundColor: 'rgba(0,191,255,.1)',  fill: true, tension: 0.3, pointRadius: 2 },
          { label: 'Ransom',   data: tl.ransom_counts,  borderColor: 'rgba(218,54,51,.8)',   backgroundColor: 'rgba(218,54,51,.1)', fill: true, tension: 0.3, pointRadius: 2 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#8B949E', font: { size: 9 }, boxWidth: 10 } } },
        scales: {
          x: { ticks: { color: '#8B949E', font: { size: 8 }, maxTicksLimit: 12 }, grid: { color: '#30363D' } },
          y: { ticks: { color: '#8B949E', font: { size: 9 } }, grid: { color: '#30363D' }, beginAtZero: true, stacked: true },
        },
      },
    });

    const transEl = document.getElementById('tap-timeline-transitions');
    if (tl.state_transitions?.length) {
      transEl.innerHTML = tl.state_transitions.map(t =>
        `<span style="margin-right:16px">⟶ ${t.month}: <span style="color:var(--text)">${t.from}</span> → <span style="color:var(--accent3)">${t.to}</span></span>`
      ).join('');
    } else {
      transEl.innerHTML = '<span style="color:var(--text-dim)">No state transitions in 24-month window</span>';
    }
  } catch (e) {
    console.error('Timeline load error:', e);
    wrap.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--red);padding:8px 0;">Failed to load timeline</div>';
  }
}

function taShowProfileModal(actorName, profile) {
  _tapCurrentActor = actorName;
  _tapCurrentProfile = profile;
  document.getElementById('tap-actor-name').textContent = actorName;
  const mmInline = document.getElementById('mm-ta-inline');
  if (mmInline) { mmInline.style.display = 'none'; delete _mmInline?.['threat_actor:' + actorName]; }
  document.getElementById('tap-regen-btn').dataset.actor = actorName;

  // Meta chips
  const id = profile.identity || {};
  const meta = profile.profile_metadata || {};
  const conf = meta.analyst_confidence || 'unknown';
  const confClass = conf === 'high' ? 'green' : conf === 'medium' ? 'amber' : '';
  const tlp = meta.tlp_marking || '';
  const tlpClass = tlp.includes('RED') ? 'red' : tlp.includes('AMBER') ? 'amber' : tlp.includes('GREEN') ? 'green' : '';
  document.getElementById('tap-meta-row').innerHTML = [
    id.actor_type     ? `<span class="tap-chip blue">${esc(id.actor_type.toUpperCase())}</span>` : '',
    id.active_status  ? `<span class="tap-chip">${esc(id.active_status)}</span>` : '',
    conf !== 'unknown' ? `<span class="tap-chip ${confClass}">CONFIDENCE: ${esc(conf.toUpperCase())}</span>` : '',
    tlp               ? `<span class="tap-chip ${tlpClass}">${esc(tlp)}</span>` : '',
    id.sponsoring_nation ? `<span class="tap-chip">🏴 ${esc(id.sponsoring_nation)}</span>` : '',
  ].filter(Boolean).join('');

  const timelineSection = `<div class="tap-section" id="tap-timeline-section">
    <div class="tap-section-title">ACTIVITY TIMELINE <span id="tap-dormancy-badge" style="display:inline"></span></div>
    <div id="tap-timeline-wrap" style="margin-top:8px;">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);padding:8px 0;">Loading…</div>
    </div>
  </div>`;
  document.getElementById('tap-body').innerHTML = timelineSection + _renderProfileBody(profile);
  document.getElementById('ta-profile-modal').style.display = 'block';
  document.body.style.overflow = 'hidden';
  _tapLoadTimeline(actorName);
}

function closeTAProfileModal() {
  document.getElementById('ta-profile-modal').style.display = 'none';
  document.body.style.overflow = '';
  if (_tapTimelineChart) { _tapTimelineChart.destroy(); _tapTimelineChart = null; }
  _tapCurrentActor = null;
  _tapCurrentProfile = null;
}

function taGenerateMindmap() {
  if (!_tapCurrentActor) { _taStatus('No profile loaded', false); return; }
  mmToggleInline('mm-ta-inline', 'threat_actor', _tapCurrentActor);
}

function _tapList(arr) {
  if (!arr || !arr.length) return '<span style="color:var(--text-dim)">—</span>';
  return arr.map(v => `<span class="tap-tag">${esc(String(v))}</span>`).join('');
}
function _tapVal(v) {
  return (v == null || v === '') ? '<span style="color:var(--text-dim)">—</span>' : `<span class="tap-val">${esc(String(v))}</span>`;
}

function _renderProfileBody(p) {
  const id   = p.identity || {};
  const mot  = p.motivation || {};
  const tgt  = p.targeting_profile || {};
  const cap  = p.capability_assessment || {};
  const inf  = p.infrastructure || {};
  const det  = p.detection_and_defense || {};
  const rel  = p.organizational_relevance || {};
  const gaps = p.intelligence_gaps || [];
  const refs = p.references || [];
  const camps= p.campaign_history || [];

  const sec = (title, html) => `<div class="tap-section">
    <div class="tap-section-title">${title}</div>${html}</div>`;

  const kv = (label, val) => `<div class="tap-kv"><span class="tap-key">${label}</span>${val}</div>`;

  // Identity
  const identityHtml = `<div class="tap-grid">
    ${kv('Primary Name', _tapVal(id.primary_name))}
    ${kv('Actor Type', _tapVal(id.actor_type))}
    ${kv('Sponsoring Nation', _tapVal(id.sponsoring_nation))}
    ${kv('Affiliated Group', _tapVal(id.affiliated_group))}
    ${kv('First Observed', _tapVal(id.first_observed))}
    ${kv('Last Active', _tapVal(id.last_active))}
    ${kv('Active Status', _tapVal(id.active_status))}
    ${kv('MITRE ID', _tapVal((id.tracking_ids || {}).mitre_group_id))}
  </div>
  ${((id.tracking_ids || {}).other_ids || []).length ? `<div style="margin-top:8px">${kv('Other IDs', `<div class="tap-tags" style="margin-top:4px">${_tapList((id.tracking_ids||{}).other_ids)}</div>`)}</div>` : ''}
  ${(id.aliases || []).length ? `<div style="margin-top:8px"><span class="tap-key">ALIASES</span><div class="tap-tags" style="margin-top:4px">${_tapList(id.aliases)}</div></div>` : ''}`;

  // Motivation
  const motivHtml = `<div class="tap-grid">
    ${kv('Primary', _tapVal(mot.primary_motivation))}
    ${kv('Approach', _tapVal(mot.targeting_approach))}
  </div>
  ${(mot.secondary_motivations||[]).length ? `<div style="margin-top:8px"><span class="tap-key">SECONDARY</span><div class="tap-tags" style="margin-top:4px">${_tapList(mot.secondary_motivations)}</div></div>` : ''}
  ${(mot.strategic_objectives||[]).length ? `<div style="margin-top:8px"><span class="tap-key">OBJECTIVES</span><div class="tap-tags" style="margin-top:4px">${_tapList(mot.strategic_objectives)}</div></div>` : ''}`;

  // Targeting
  const tgtHtml = `<div class="tap-grid">
    ${kv('Sectors', `<div class="tap-tags" style="margin-top:4px">${_tapList(tgt.targeted_sectors)}</div>`)}
    ${kv('Geographies', `<div class="tap-tags" style="margin-top:4px">${_tapList(tgt.targeted_geographies)}</div>`)}
    ${kv('Org Types', `<div class="tap-tags" style="margin-top:4px">${_tapList(tgt.targeted_organization_types)}</div>`)}
    ${kv('High-Value Assets', `<div class="tap-tags" style="margin-top:4px">${_tapList(tgt.high_value_assets_targeted)}</div>`)}
  </div>`;

  // Capability
  const malware = (cap.known_malware || []);
  const malwareHtml = malware.length ? `<table class="tap-table">
    <thead><tr><th>Name</th><th>Type</th><th>Notes</th></tr></thead>
    <tbody>${malware.map(m => `<tr>
      <td style="color:var(--accent);font-weight:600">${esc(m.name||'—')}</td>
      <td><span class="tap-tag">${esc(m.type||'—')}</span></td>
      <td style="color:var(--text-dim)">${esc(m.notes||'—')}</td>
    </tr>`).join('')}</tbody></table>` : '<span style="color:var(--text-dim)">None documented</span>';

  const vulns = (cap.exploited_vulnerabilities || []);
  const vulnsHtml = vulns.length ? `<table class="tap-table">
    <thead><tr><th>CVE</th><th>Product</th><th>Notes</th></tr></thead>
    <tbody>${vulns.map(v => `<tr>
      <td style="color:var(--accent3);font-family:'IBM Plex Mono',monospace;font-size:10px">${esc(v.cve_id||'—')}</td>
      <td>${esc(v.product||'—')}</td>
      <td style="color:var(--text-dim)">${esc(v.notes||'—')}</td>
    </tr>`).join('')}</tbody></table>` : '<span style="color:var(--text-dim)">None documented</span>';

  const ttps = cap.attack_techniques || {};
  const ttpPhases = Object.entries(ttps).filter(([,v]) => v && v.length);
  const ttpHtml = ttpPhases.length ? ttpPhases.map(([phase, techs]) =>
    `<div style="margin-bottom:8px"><span class="tap-key">${phase.replace(/_/g,' ').toUpperCase()}</span>
    <div class="tap-tags" style="margin-top:4px">${_tapList(techs)}</div></div>`
  ).join('') : '<span style="color:var(--text-dim)">None documented</span>';

  const capHtml = `<div class="tap-grid" style="margin-bottom:12px">
    ${kv('Sophistication', _tapVal(cap.sophistication_level))}
    ${kv('Dev Capability', _tapVal(cap.development_capability))}
  </div>
  <div style="margin-bottom:10px"><span class="tap-key">KNOWN TOOLS</span><div class="tap-tags" style="margin-top:4px">${_tapList(cap.known_tools)}</div></div>
  <div style="margin-bottom:10px"><span class="tap-key">MALWARE</span><div style="margin-top:6px">${malwareHtml}</div></div>
  <div style="margin-bottom:10px"><span class="tap-key">EXPLOITED VULNERABILITIES</span><div style="margin-top:6px">${vulnsHtml}</div></div>
  <div><span class="tap-key">ATTACK TECHNIQUES (MITRE)</span><div style="margin-top:6px">${ttpHtml}</div></div>`;

  // Infrastructure
  const iocs = inf.known_iocs || {};
  const iocHtml = [
    (iocs.ips||[]).length ? `<div><span class="tap-key">IPs</span><div class="tap-tags" style="margin-top:4px">${_tapList(iocs.ips)}</div></div>` : '',
    (iocs.domains||[]).length ? `<div><span class="tap-key">DOMAINS</span><div class="tap-tags" style="margin-top:4px">${_tapList(iocs.domains)}</div></div>` : '',
    (iocs.hashes||[]).length ? `<div><span class="tap-key">HASHES</span><div class="tap-tags" style="margin-top:4px">${_tapList(iocs.hashes)}</div></div>` : '',
    (iocs.urls||[]).length ? `<div><span class="tap-key">URLs</span><div class="tap-tags" style="margin-top:4px">${_tapList(iocs.urls)}</div></div>` : '',
  ].filter(Boolean).join('<div style="margin-top:8px"></div>') || '<span style="color:var(--text-dim)">None documented</span>';

  const infraHtml = `<div class="tap-grid" style="margin-bottom:12px">
    ${kv('Infrastructure Reuse', _tapVal(inf.infrastructure_reuse))}
    ${kv('Notes', _tapVal(inf.infrastructure_notes))}
  </div>
  ${(inf.c2_patterns||[]).length ? `<div style="margin-bottom:10px"><span class="tap-key">C2 PATTERNS</span><div class="tap-tags" style="margin-top:4px">${_tapList(inf.c2_patterns)}</div></div>` : ''}
  ${(inf.hosting_preferences||[]).length ? `<div style="margin-bottom:10px"><span class="tap-key">HOSTING</span><div class="tap-tags" style="margin-top:4px">${_tapList(inf.hosting_preferences)}</div></div>` : ''}
  <div><span class="tap-key">IOCs</span><div style="margin-top:6px;display:flex;flex-direction:column;gap:8px">${iocHtml}</div></div>`;

  // Campaigns
  const campHtml = camps.length ? `<table class="tap-table">
    <thead><tr><th>Campaign</th><th>Date Range</th><th>Sectors</th><th>Source</th></tr></thead>
    <tbody>${camps.map(c => `<tr>
      <td style="color:var(--text-bright);font-weight:600">${esc(c.campaign_name||'—')}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;white-space:nowrap">${esc(c.date_range||'—')}</td>
      <td><div class="tap-tags">${_tapList(c.targeted_sectors)}</div></td>
      <td style="color:var(--text-dim);font-size:10px">${esc(c.source_reference||'—')}</td>
    </tr>`).join('')}</tbody></table>` : '<span style="color:var(--text-dim)">None documented</span>';

  // Detection
  const detOpp = (det.detection_opportunities || []);
  const detOppHtml = detOpp.length ? `<table class="tap-table">
    <thead><tr><th>Layer</th><th>Description</th><th>MITRE Ref</th></tr></thead>
    <tbody>${detOpp.map(o => `<tr>
      <td><span class="tap-tag">${esc(o.layer||'—')}</span></td>
      <td style="color:var(--text)">${esc(o.description||'—')}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent3)">${esc(o.mitre_technique_ref||'—')}</td>
    </tr>`).join('')}</tbody></table>` : '<span style="color:var(--text-dim)">None documented</span>';

  const mitigations = (det.recommended_mitigations || []);
  const mitigHtml = mitigations.length ? `<table class="tap-table">
    <thead><tr><th>Mitigation</th><th>ID</th><th>Priority</th></tr></thead>
    <tbody>${mitigations.map(m => {
      const pClass = m.priority === 'immediate' ? 'color:var(--red)' : m.priority === 'short-term' ? 'color:var(--accent3)' : 'color:var(--text-dim)';
      return `<tr>
        <td>${esc(m.mitigation||'—')}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">${esc(m.mitre_mitigation_id||'—')}</td>
        <td style="font-size:10px;${pClass}">${esc(m.priority||'—')}</td>
      </tr>`;
    }).join('')}</tbody></table>` : '<span style="color:var(--text-dim)">None documented</span>';

  const detHtml = `<div style="margin-bottom:12px"><span class="tap-key">DETECTION OPPORTUNITIES</span><div style="margin-top:6px">${detOppHtml}</div></div>
  <div><span class="tap-key">RECOMMENDED MITIGATIONS</span><div style="margin-top:6px">${mitigHtml}</div></div>`;

  // Org Relevance
  const relHtml = `<div class="tap-grid" style="margin-bottom:12px">
    ${kv('Sector Relevance', _tapVal(rel.sector_relevance))}
    ${kv('Monitoring Priority', _tapVal(rel.monitoring_priority))}
  </div>
  ${rel.relevance_rationale ? `<div style="margin-bottom:10px"><span class="tap-key">RATIONALE</span><p style="font-size:12px;color:var(--text);margin:6px 0 0;line-height:1.6">${esc(rel.relevance_rationale)}</p></div>` : ''}
  ${(rel.recommended_actions||[]).length ? `<div><span class="tap-key">RECOMMENDED ACTIONS</span><table class="tap-table" style="margin-top:6px">
    <thead><tr><th>Timeframe</th><th>Action</th></tr></thead>
    <tbody>${(rel.recommended_actions).map(a => `<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;white-space:nowrap;color:var(--accent3)">${esc(a.timeframe||'—')}</td>
      <td>${esc(a.action||'—')}</td>
    </tr>`).join('')}</tbody></table></div>` : ''}`;

  // Gaps
  const gapsHtml = gaps.length ? `<ul style="margin:0;padding-left:18px;color:var(--text-dim);font-size:12px;line-height:1.8">${gaps.map(g => `<li>${esc(g)}</li>`).join('')}</ul>` : '<span style="color:var(--text-dim)">None documented</span>';

  // References
  const refsHtml = refs.length ? `<table class="tap-table">
    <thead><tr><th>Title</th><th>Source</th><th>Date</th></tr></thead>
    <tbody>${refs.map(r => `<tr>
      <td style="color:var(--text)">${r.url ? `<a href="${esc(r.url)}" target="_blank" style="color:var(--accent);text-decoration:none">${esc(r.title||r.url)}</a>` : esc(r.title||'—')}</td>
      <td style="color:var(--text-dim)">${esc(r.source||'—')}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;white-space:nowrap">${esc(r.date||'—')}</td>
    </tr>`).join('')}</tbody></table>` : '<span style="color:var(--text-dim)">None documented</span>';

  return [
    sec('Identity', identityHtml),
    sec('Motivation', motivHtml),
    sec('Targeting Profile', tgtHtml),
    sec('Capability Assessment', capHtml),
    sec('Infrastructure', infraHtml),
    sec('Campaign History', campHtml),
    sec('Detection & Defense', detHtml),
    sec('Organizational Relevance', relHtml),
    gaps.length ? sec('Intelligence Gaps', gapsHtml) : '',
    refs.length ? sec('References', refsHtml) : '',
  ].join('');
}

// ── WATCHLIST NEWS PANEL ──────────────────────────────────
async function loadWatchlistPanel() {
  const s      = state.watchlist;
  const btn    = document.getElementById('watchlist-refresh');
  const el     = document.getElementById('watchlist-list');
  const search = document.getElementById('filter-search')?.value.trim() || '';

  el.innerHTML = loadingHTML(true);

  let watchedNames = [];
  try {
    const wnResp = await fetch('/api/ta/watchlist-names', { headers: _clientHeader() });
    if (wnResp.ok) {
      const wnData = await wnResp.json();
      watchedNames = wnData.names || [];
    }
  } catch (e) { console.error(e); }

  if (!watchedNames.length) {
    el.innerHTML = emptyHTML('No threat actors in watchlist. Add via Threat Actor Room → Watchlist.', true);
    document.getElementById('watchlist-count').textContent = '0 items';
    if (btn) btn.classList.remove('spinning');
    return 0;
  }

  const params = new URLSearchParams({ page: s.page, page_size: 20 });
  watchedNames.forEach(n => params.append('threat_actor', n));
  if (search) params.set('search', search);

  let data = { articles: [], total: 0 };
  try {
    const resp = await fetch(`/api/articles?${params}`);
    if (resp.ok) data = await resp.json();
  } catch (e) { console.error(e); }

  s.total = data.total;
  el.innerHTML = data.articles.length
    ? data.articles.map(renderNewsItem).join('')
    : emptyHTML('No articles found for watched threat actors', true);

  document.getElementById('watchlist-count').textContent = `${data.total} items`;
  renderPager('watchlist');
  if (btn) btn.classList.remove('spinning');
  return data.total;
}

async function loadTechStackPanel() {
  const s   = state.techstack;
  const btn = document.getElementById('techstack-refresh');
  const el  = document.getElementById('techstack-list');
  const f   = getFilters();

  el.innerHTML = loadingHTML(true);
  if (btn) btn.classList.add('spinning');

  let techNames = [];
  try {
    const resp = await fetch('/api/techstack?page_size=500', { headers: _authAndClientHeaders() });
    if (resp.ok) {
      const data = await resp.json();
      techNames = (data.items || []).map(t => t.name);
    }
  } catch (e) { console.error(e); }

  if (!techNames.length) {
    el.innerHTML = emptyHTML('No tech stack configured. Add via Tech Stack settings.', true);
    document.getElementById('techstack-count').textContent = '0 items';
    if (btn) btn.classList.remove('spinning');
    return 0;
  }

  const params = new URLSearchParams({ page: s.page, page_size: 20 });
  techNames.forEach(n => params.append('title_keyword', n));
  if (f.dateStart) params.set('posted_on_start', f.dateStart);
  if (f.dateEnd)   params.set('posted_on_end',   f.dateEnd);
  if (f.industry)  params.append('industry', f.industry);
  if (f.actor)     params.append('threat_actor', f.actor);
  if (f.search)    params.set('search', f.search);

  let data = { articles: [], total: 0 };
  try {
    const resp = await fetch(`/api/articles?${params}`);
    if (resp.ok) data = await resp.json();
  } catch (e) { console.error(e); }

  s.total = data.total;
  el.innerHTML = data.articles.length
    ? data.articles.map(renderNewsItem).join('')
    : emptyHTML('No articles found for configured tech stack', true);

  document.getElementById('techstack-count').textContent = `${data.total} items`;
  renderPager('techstack');
  if (btn) btn.classList.remove('spinning');
  return data.total;
}

