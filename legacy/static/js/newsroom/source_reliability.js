// ── SOURCE RELIABILITY DB ─────────────────────────────────────

let _srPage = 1, _srPageSize = 50, _srSortBy = 'source_name', _srSortDir = 'asc';
let _srSearchTimer = null;
let _srEditId = null;  // null = add mode, string = edit mode
let _srScoreMap = {};  // normalized source name → entry, used by article modal

async function loadSRScoreMap() {
  try {
    const res  = await fetch('/api/sr/entries?page_size=500&sort_by=source_name');
    const data = await res.json();
    _srScoreMap = {};
    (data.entries || []).forEach(e => {
      _srScoreMap[e.source_name.toLowerCase()] = e;
    });
  } catch (_) { /* non-fatal */ }
}

function srSearchInput() {
  clearTimeout(_srSearchTimer);
  _srSearchTimer = setTimeout(() => { _srPage = 1; loadSREntries(); }, 350);
}

function srSetPageSize() {
  _srPageSize = parseInt(document.getElementById('sr-page-size').value);
  _srPage = 1;
  loadSREntries();
}

function srSort(th) {
  const col = th.dataset.col;
  if (_srSortBy === col) {
    _srSortDir = _srSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    _srSortBy = col;
    _srSortDir = 'asc';
  }
  document.querySelectorAll('.ta-th--sortable').forEach(h => h.classList.remove('sort-active'));
  th.classList.add('sort-active');
  th.querySelector('.sort-ind').textContent = _srSortDir === 'asc' ? '↑' : '↓';
  _srPage = 1;
  loadSREntries();
}

async function loadSREntries() {
  const tbody  = document.getElementById('sr-tbody');
  const search = document.getElementById('sr-search').value.trim();
  const grade  = document.getElementById('sr-grade-filter').value;
  tbody.innerHTML = '<tr><td colspan="9" class="ta-td"><div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Loading…</div></div></td></tr>';

  try {
    const params = new URLSearchParams({
      page: _srPage, page_size: _srPageSize,
      sort_by: _srSortBy, sort_dir: _srSortDir,
    });
    if (search) params.set('search', search);
    if (grade)  params.set('grade', grade);

    const res  = await fetch(`/api/sr/entries?${params}`);
    const data = await res.json();
    const entries = data.entries || [];

    document.getElementById('sr-total').textContent =
      `${data.total} source${data.total !== 1 ? 's' : ''} rated`;
    document.getElementById('intel-scores-count').textContent = data.total;

    // Pager
    const totalPages = Math.ceil(data.total / _srPageSize);
    const pager = document.getElementById('sr-pager');
    pager.innerHTML = totalPages > 1 ? `
      <div class="pager">
        <button class="pager-btn" onclick="_srPrev()" ${_srPage <= 1 ? 'disabled' : ''}>← Prev</button>
        <span class="pager-info">Page <strong>${_srPage}</strong> / ${totalPages}</span>
        <button class="pager-btn" onclick="_srNext(${totalPages})" ${_srPage >= totalPages ? 'disabled' : ''}>Next →</button>
      </div>` : '';

    if (!entries.length) {
      tbody.innerHTML = '<tr><td colspan="9" class="ta-td"><div class="intel-empty">No entries found</div></td></tr>';
      return;
    }

    const offset = (_srPage - 1) * _srPageSize;
    tbody.innerHTML = entries.map((e, i) => `
      <tr>
        <td class="ta-td ta-num">${offset + i + 1}</td>
        <td class="ta-td ta-name">${escHtml(e.source_name)}</td>
        <td class="ta-td ta-date">${escHtml(e.analyst_name)}</td>
        <td class="ta-td">
          <span class="admiral-grade admiral-${escHtml(e.reliability_grade)}" title="${escHtml(e.admiralty_code)}"
                style="width:auto;padding:2px 8px;font-size:12px">${escHtml(e.admiralty_code)}</span>
        </td>
        <td class="ta-td">
          <span class="admiral-grade admiral-${escHtml(e.reliability_grade)}">${escHtml(e.reliability_grade)}</span>
        </td>
        <td class="ta-td">
          <span style="font-family:'Share Tech Mono',monospace;font-size:13px;color:var(--text-dim)">${escHtml(e.credibility_code)}</span>
        </td>
        <td class="ta-td" style="font-size:11px;color:var(--text-dim);max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escHtml(e.notes)}">${escHtml(e.notes) || '—'}</td>
        <td class="ta-td ta-date">${escHtml(e.last_updated || e.added_date)}</td>
        <td class="ta-td" style="white-space:nowrap">
          <button class="ta-restore-btn" style="margin-right:4px" onclick='openSREditModal(${JSON.stringify(e)})'>Edit</button>
          <button class="ta-delete-btn" onclick="srDeleteEntry('${e._id}','${escHtml(e.source_name)}')">Remove</button>
        </td>
      </tr>`).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="ta-td" style="color:var(--red)">Error: ${err.message}</td></tr>`;
  }
}

function _srPrev() { if (_srPage > 1) { _srPage--; loadSREntries(); } }
function _srNext(total) { if (_srPage < total) { _srPage++; loadSREntries(); } }

// ── SR Modal ──

function _updateCodePreview() {
  const g = document.getElementById('sr-input-grade').value;
  const c = document.getElementById('sr-input-code').value;
  const el = document.getElementById('sr-code-preview');
  if (g && c) {
    el.textContent = g + c;
    el.className = `admiral-grade admiral-${g}`;
    el.style.cssText = 'font-size:22px;padding:3px 10px;border-radius:3px';
  } else {
    el.textContent = '—';
    el.removeAttribute('class');
    el.style.cssText = 'font-family:\'Share Tech Mono\',monospace;font-size:20px;color:var(--text-dim)';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  ['sr-input-grade','sr-input-code'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', _updateCodePreview);
  });
  document.addEventListener('click', e => {
    const wrap = document.querySelector('.sr-source-wrap');
    if (wrap && !wrap.contains(e.target)) {
      const dd = document.getElementById('sr-source-dd');
      if (dd) dd.classList.remove('open');
    }
  });
  if (window._ssoPrefillError) {
    openLoginModal();
    _authShowError(window._ssoPrefillError);
    delete window._ssoPrefillError;
  }
});

function _srPopulateModal(entry) {
  const isEdit = !!entry;
  _srEditId = isEdit ? entry._id : null;
  document.getElementById('sr-modal-title').textContent = isEdit ? 'Edit Source Rating' : 'Add Source Rating';
  document.getElementById('sr-input-source').value    = isEdit ? entry.source_name : '';
  document.getElementById('sr-input-source').disabled = isEdit;
  document.getElementById('sr-input-analyst').value  = isEdit ? entry.analyst_name : '';
  document.getElementById('sr-input-grade').value    = isEdit ? entry.reliability_grade : '';
  document.getElementById('sr-input-code').value     = isEdit ? entry.credibility_code : '';
  document.getElementById('sr-input-notes').value    = isEdit ? (entry.notes || '') : '';
  document.getElementById('sr-modal-err').style.display = 'none';
  _updateCodePreview();
  document.getElementById('sr-modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

let _srSourceList = [];
let _srDdActiveIdx = -1;

async function _srLoadUngradedSources() {
  try {
    const res = await fetch('/api/sr/ungraded-sources');
    const data = await res.json();
    _srSourceList = data.sources || [];
  } catch (_) { _srSourceList = []; }
  _srRenderSourceDd('');
}

function _srRenderSourceDd(filter) {
  const dd = document.getElementById('sr-source-dd');
  if (!dd) return;
  const q = filter.toLowerCase();
  const matches = q ? _srSourceList.filter(s => s.toLowerCase().includes(q)) : _srSourceList;
  _srDdActiveIdx = -1;
  if (!matches.length) {
    dd.innerHTML = '<li class="sr-dd-empty">No ungraded sources found</li>';
  } else {
    dd.innerHTML = matches.map(s =>
      `<li onclick="srSourcePick(${JSON.stringify(s)})">${escHtml(s)}</li>`
    ).join('');
  }
}

function srSourceOpen() {
  const dd = document.getElementById('sr-source-dd');
  if (!dd || document.getElementById('sr-input-source').disabled) return;
  _srRenderSourceDd(document.getElementById('sr-input-source').value);
  dd.classList.add('open');
}

function srSourceFilter() {
  const inp = document.getElementById('sr-input-source');
  _srRenderSourceDd(inp ? inp.value : '');
  const dd = document.getElementById('sr-source-dd');
  if (dd) dd.classList.add('open');
}

function srSourcePick(name) {
  const inp = document.getElementById('sr-input-source');
  if (inp) inp.value = name;
  const dd = document.getElementById('sr-source-dd');
  if (dd) dd.classList.remove('open');
}

function srSourceKey(e) {
  const dd = document.getElementById('sr-source-dd');
  if (!dd || !dd.classList.contains('open')) return;
  const items = dd.querySelectorAll('li:not(.sr-dd-empty)');
  if (!items.length) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    _srDdActiveIdx = Math.min(_srDdActiveIdx + 1, items.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    _srDdActiveIdx = Math.max(_srDdActiveIdx - 1, 0);
  } else if (e.key === 'Enter' && _srDdActiveIdx >= 0) {
    e.preventDefault();
    items[_srDdActiveIdx].click();
    return;
  } else if (e.key === 'Escape') {
    dd.classList.remove('open');
    return;
  }
  items.forEach((li, i) => li.classList.toggle('sr-dd-active', i === _srDdActiveIdx));
  if (_srDdActiveIdx >= 0) items[_srDdActiveIdx].scrollIntoView({ block: 'nearest' });
}

function openSRAddModal() {
  requireTAAuth(() => {
    _srLoadUngradedSources();
    _srPopulateModal(null);
  });
}

function openSREditModal(entry) {
  requireTAAuth(() => _srPopulateModal(entry));
}

function closeSRModal() {
  document.getElementById('sr-modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

function srModalSubmit() {
  requireTAAuth(async (password) => {
    const source  = document.getElementById('sr-input-source').value.trim();
    const analyst = document.getElementById('sr-input-analyst').value.trim();
    const grade   = document.getElementById('sr-input-grade').value;
    const code    = document.getElementById('sr-input-code').value;
    const notes   = document.getElementById('sr-input-notes').value.trim();
    const errEl   = document.getElementById('sr-modal-err');

    if (!analyst || !grade || !code || (!_srEditId && !source)) {
      errEl.textContent = 'All required fields must be filled.';
      errEl.style.display = '';
      return;
    }

    try {
      let res;
      if (_srEditId) {
        res = await fetch(`/api/sr/entries/${_srEditId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + password },
          body: JSON.stringify({ analyst_name: analyst, reliability_grade: grade, credibility_code: code, notes }),
        });
      } else {
        res = await fetch('/api/sr/entries', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + password },
          body: JSON.stringify({ source_name: source, analyst_name: analyst, reliability_grade: grade, credibility_code: code, notes }),
        });
      }

      if (res.status === 401) { _authFailed(); return; }
      const data = await res.json();
      if (!data.success) {
        errEl.textContent = data.reason === 'duplicate' ? 'Source already exists.' : `Error: ${data.reason}`;
        errEl.style.display = '';
        return;
      }
      closeSRModal();
      _srShowStatus(_srEditId ? 'Updated.' : 'Source added.', false);
      loadSREntries();
      loadSRScoreMap();
    } catch (e) {
      errEl.textContent = `Error: ${e.message}`;
      errEl.style.display = '';
    }
  });
}

async function srDeleteEntry(id, name) {
  showConfirmModal({
    title: 'Remove Source Rating',
    body:  `<p style="font-size:13px;color:var(--text);line-height:1.7">Remove the source rating for <strong style="color:var(--text-bright)">${escHtml(name)}</strong>?</p>`,
    okLabel: 'Remove',
    onConfirm: () => requireTAAuth(async (password) => {
      const res  = await fetch(`/api/sr/entries/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer ' + password },
      });
      if (res.status === 401) { _authFailed(); return; }
      const data = await res.json();
      if (!data.success) { _srShowStatus('Delete failed.', true); return; }
      _srShowStatus('Removed.', false);
      loadSREntries();
      loadSRScoreMap();
    }),
  });
}

function _srShowStatus(msg, isErr) {
  const el = document.getElementById('sr-status');
  el.textContent = msg;
  el.className = `ta-status show ${isErr ? 'err' : 'ok'}`;
  setTimeout(() => el.classList.remove('show'), 3000);
}

