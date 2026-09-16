// ── TECH STACK MANAGEMENT ────────────────────────────────
const _tsState = { page: 1, pageSize: 50, total: 0 };
let   _tsMap   = {};  // _id → item

const _EXPOSURE_CYCLE  = ['internal', 'public', 'both'];
const _EXPOSURE_LABEL  = { internal: 'Internal', public: 'Public', both: 'Both' };
const _EXPOSURE_COLOR  = {
  internal: 'rgba(47,129,247,0.15)',
  public:   'rgba(218,54,51,0.15)',
  both:     'rgba(227,179,65,0.15)',
};
const _EXPOSURE_BORDER = {
  internal: 'rgba(47,129,247,0.5)',
  public:   'rgba(218,54,51,0.5)',
  both:     'rgba(227,179,65,0.5)',
};
const _EXPOSURE_TEXT   = {
  internal: 'var(--accent)',
  public:   'var(--red)',
  both:     'var(--orange)',
};
const _EXPOSURE_MULT   = { internal: '1×', public: '1.5×', both: '1.25×' };

const _HOSTING_CYCLE  = ['on_prem', 'cloud', 'saas'];
const _HOSTING_LABEL  = { on_prem: 'On-Prem', cloud: 'Cloud', saas: 'SaaS' };
const _HOSTING_COLOR  = { on_prem: 'rgba(110,124,255,0.12)', cloud: 'rgba(47,129,247,0.12)', saas: 'rgba(227,179,65,0.12)' };
const _HOSTING_BORDER = { on_prem: 'rgba(110,124,255,0.5)',  cloud: 'rgba(47,129,247,0.5)',  saas: 'rgba(227,179,65,0.5)' };
const _HOSTING_TEXT   = { on_prem: 'var(--accent2)',         cloud: 'var(--accent)',          saas: 'var(--orange)' };
const _HOSTING_MULT   = { on_prem: '1×', cloud: '1×', saas: '0.8×' };

function _tsExposureBadge(id, exposure) {
  const e = exposure || 'internal';
  const opts = _EXPOSURE_CYCLE.map(v =>
    `<option value="${v}" ${v === e ? 'selected' : ''}>${_EXPOSURE_LABEL[v]} ${_EXPOSURE_MULT[v]}</option>`
  ).join('');
  return `<select
    data-id="${esc(id)}"
    onchange="tsChangeExposure(this)"
    title="Internet exposure — affects CVE adjusted risk score"
    style="font-size:10px;padding:3px 6px;background:${_EXPOSURE_COLOR[e]};border:1px solid ${_EXPOSURE_BORDER[e]};color:${_EXPOSURE_TEXT[e]};border-radius:4px;cursor:pointer;outline:none"
  >${opts}</select>`;
}

async function tsChangeExposure(sel) {
  const id   = sel.dataset.id;
  const next = sel.value;
  const prev = (_tsMap[id] || {}).exposure || 'internal';

  sel.disabled = true;
  try {
    const resp = await fetch(`/api/techstack/${encodeURIComponent(id)}/exposure`, {
      method: 'PATCH',
      headers: _authAndClientHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ exposure: next }),
    });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) throw new Error(resp.statusText);
    if (_tsMap[id]) _tsMap[id].exposure = next;
    sel.style.background  = _EXPOSURE_COLOR[next];
    sel.style.borderColor = _EXPOSURE_BORDER[next];
    sel.style.color       = _EXPOSURE_TEXT[next];
    _tsStatus(`Exposure updated to "${_EXPOSURE_LABEL[next]}"`, true);
  } catch(e) {
    _tsStatus('Failed to update exposure', false);
    sel.value = prev;
  } finally {
    sel.disabled = false;
  }
}

function _tsHostingBadge(id, hosting) {
  const h = hosting || 'on_prem';
  const opts = _HOSTING_CYCLE.map(v =>
    `<option value="${v}" ${v === h ? 'selected' : ''}>${_HOSTING_LABEL[v]} ${_HOSTING_MULT[v]}</option>`
  ).join('');
  return `<select
    data-id="${esc(id)}"
    onchange="tsChangeHosting(this)"
    title="Hosting model — affects CVE adjusted risk score"
    style="font-size:10px;padding:3px 6px;background:${_HOSTING_COLOR[h]};border:1px solid ${_HOSTING_BORDER[h]};color:${_HOSTING_TEXT[h]};border-radius:4px;cursor:pointer;outline:none"
  >${opts}</select>`;
}

async function tsChangeHosting(sel) {
  const id   = sel.dataset.id;
  const next = sel.value;
  const prev = (_tsMap[id] || {}).hosting_type || 'on_prem';

  sel.disabled = true;
  try {
    const resp = await fetch(`/api/techstack/${encodeURIComponent(id)}/hosting`, {
      method: 'PATCH',
      headers: _authAndClientHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ hosting_type: next }),
    });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) throw new Error(resp.statusText);
    if (_tsMap[id]) _tsMap[id].hosting_type = next;
    sel.style.background  = _HOSTING_COLOR[next];
    sel.style.borderColor = _HOSTING_BORDER[next];
    sel.style.color       = _HOSTING_TEXT[next];
    _tsStatus(`Hosting updated to "${_HOSTING_LABEL[next]}"`, true);
  } catch(e) {
    _tsStatus('Failed to update hosting', false);
    sel.value = prev;
  } finally {
    sel.disabled = false;
  }
}

async function loadTechStack() {
  const tbody = document.getElementById('ts-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="ta-td">${loadingHTML()}</td></tr>`;

  try {
    const params = new URLSearchParams({
      page: _tsState.page, page_size: _tsState.pageSize, sort_by: 'name', sort_dir: 'asc',
    });
    const search = document.getElementById('ts-search').value.trim();
    if (search) params.set('search', search);

    const resp = await fetch(`/api/techstack?${params}`, { headers: _authAndClientHeaders() });
    if (!resp.ok) throw new Error(resp.statusText);
    const d = await resp.json();

    _tsState.total = d.total;
    document.getElementById('ts-total').textContent =
      `${d.total} tech stack${d.total !== 1 ? 's' : ''} tracked`;
    document.getElementById('ts-submenu-count').textContent = d.total;

    _tsMap = {};
    if (!d.items.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="ta-td">${emptyHTML('No tech stacks added yet')}</td></tr>`;
    } else {
      const offset = (_tsState.page - 1) * _tsState.pageSize;
      tbody.innerHTML = d.items.map((t, i) => {
        _tsMap[t._id] = t;
        return `<tr>
          <td class="ta-td ta-num">${offset + i + 1}</td>
          <td class="ta-td ta-name">${esc(t.name)}</td>
          <td class="ta-td ta-date">${esc(t.added_date)}</td>
          <td class="ta-td"><span class="ta-source-badge">${esc(t.source)}</span></td>
          <td class="ta-td">${_tsExposureBadge(t._id, t.exposure || 'internal')}</td>
          <td class="ta-td">${_tsHostingBadge(t._id, t.hosting_type || 'on_prem')}</td>
          <td class="ta-td" style="display:flex;gap:6px;align-items:center">
            <button class="ta-delete-btn" data-id="${esc(t._id)}"
                    onclick="tsDeleteTech(this.dataset.id)">✕ REMOVE</button>
            <button class="btn-reset" data-id="${esc(t._id)}" data-name="${esc(t.name)}"
                    style="font-size:10px;padding:4px 8px;border-color:rgba(47,129,247,0.4);color:var(--accent)"
                    onclick="tsBackfillHistorical(this.dataset.id, this.dataset.name, this)"
                    title="Fetch CVEs from NVD for the past 180 days">↺ Historical</button>
          </td>
        </tr>`;
      }).join('');
    }
    _renderTSPager();
  } catch(e) {
    console.error('TS load error:', e);
    tbody.innerHTML = `<tr><td colspan="7" class="ta-td">${emptyHTML('Failed to load tech stacks')}</td></tr>`;
  }
}

function _renderTSPager() {
  const totalPages = Math.max(1, Math.ceil(_tsState.total / _tsState.pageSize));
  const el = document.getElementById('ts-pager');
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="tsGoPage(-1)" ${_tsState.page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${_tsState.page}</strong> / ${totalPages}</span>
    <button class="pager-btn" onclick="tsGoPage(1)" ${_tsState.page >= totalPages ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

async function tsGoPage(delta) {
  const totalPages = Math.ceil(_tsState.total / _tsState.pageSize);
  _tsState.page = Math.min(Math.max(1, _tsState.page + delta), totalPages);
  await loadTechStack();
}

function tsSearchInput() { _tsState.page = 1; loadTechStack(); }

function tsSetPageSize() {
  _tsState.pageSize = parseInt(document.getElementById('ts-page-size').value, 10);
  _tsState.page = 1;
  loadTechStack();
}

function _tsStatus(msg, ok) {
  const el = document.getElementById('ts-status');
  el.textContent = msg;
  el.className = `ta-status show ${ok ? 'ok' : 'err'}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3500);
}

function tsAddTech() {
  const input       = document.getElementById('ts-input');
  const name        = input.value.trim();
  const exposure    = (document.getElementById('ts-exposure-select')?.value)  || 'internal';
  const hosting_type = (document.getElementById('ts-hosting-select')?.value)  || 'on_prem';
  if (!name) return;

  requireTAAuth(async (password) => {
    try {
      const resp = await fetch('/api/techstack', {
        method: 'POST',
        headers: _authAndClientHeaders({ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + password }),
        body: JSON.stringify({ name, exposure, hosting_type }),
      });
      if (resp.status === 401) { _authFailed(); return; }
      const d = await resp.json();
      if (d.success) {
        input.value = '';
        _tsStatus(`"${name}" added`, true);
        _tsState.page = 1;
        loadTechStack();
      } else {
        _tsStatus(`Cannot add "${name}": already exists`, false);
      }
    } catch(e) {
      console.error(e);
      _tsStatus('Failed to add tech stack', false);
    }
  });
}

function tsDeleteTech(techId) {
  const t = _tsMap[techId];
  if (!t) return;

  requireTAAuth((password) => {
    showConfirmModal({
      title:   'Remove Tech Stack',
      okLabel: '✕ Remove',
      body: `<p style="font-size:13px;color:var(--text);line-height:1.7;margin-bottom:14px">
        Remove <strong style="color:var(--red)">${esc(t.name)}</strong> from tech stack tracking?
      </p>
      <p style="font-size:12px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;line-height:1.7">
        All CVEs found for this tech under your client will also be deleted.
      </p>`,
      onConfirm: async () => {
        try {
          const resp = await fetch(
            `/api/techstack/${encodeURIComponent(techId)}`,
            { method: 'DELETE', headers: _authAndClientHeaders({ 'Authorization': 'Bearer ' + password }) }
          );
          if (resp.status === 401) { _authFailed(); return; }
          const d = await resp.json();
          if (d.success) {
            const cveMsg = d.cves_deleted > 0 ? ` + ${d.cves_deleted} CVE(s) deleted` : '';
            _tsStatus(`"${t.name}" removed${cveMsg}`, true);
            loadTechStack();
            if (typeof loadCvePanel === 'function') loadCvePanel();
          }
        } catch(e) {
          console.error(e);
          _tsStatus('Failed to remove', false);
        }
      },
    });
  });
}

async function tsBackfillHistorical(techId, techName, btn) {
  btn.disabled = true;
  btn.textContent = '⏳';
  try {
    const resp = await fetch(`/api/techstack/${encodeURIComponent(techId)}/backfill-historical`, {
      method: 'POST',
      headers: _authAndClientHeaders(),
    });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) throw new Error(resp.statusText);
    _tsStatus(`Historical backfill started for "${techName}" (180 days)`, true);
  } catch(e) {
    _tsStatus(`Backfill failed: ${e.message}`, false);
  } finally {
    btn.disabled = false;
    btn.textContent = '↺ Historical';
  }
}

async function tsBackfillCves(btn) {
  btn.disabled = true;
  btn.textContent = '⏳ Backfilling…';
  try {
    const resp = await fetch('/api/techstack/backfill-cves', {
      method: 'POST',
      headers: _authAndClientHeaders(),
    });
    if (resp.status === 401) { _authFailed(); return; }
    const d = await resp.json();
    const total = d.total_backfilled || 0;
    _tsStatus(
      total > 0
        ? `Backfilled ${total} CVE(s) across ${Object.keys(d.by_tech || {}).length} tech(s)`
        : 'No new CVEs to backfill (index migration may be needed)',
      total > 0,
    );
    if (total > 0 && typeof loadCvePanel === 'function') loadCvePanel();
  } catch(e) {
    _tsStatus('Backfill failed: ' + e.message, false);
  } finally {
    btn.disabled = false;
    btn.textContent = '↺ Backfill CVEs';
  }
}


