// ── PIR article overlay state ──────────────────────────────────
let _pirArtState   = {pirId:null, pirTitle:null, page:1, pageSize:15, total:0};
let _pirArticleData = [];
let _pirNoteState  = {pirId:'', articleUrl:'', articleTitle:''};

async function viewPirArticles(pirId, pirTitle) {
  _pirArtState = {pirId, pirTitle, page:1, pageSize:15, total:0};
  document.getElementById('pir-art-title').textContent = pirTitle;
  document.getElementById('pir-art-overlay').style.display = 'block';
  await _fetchPirArticles();
}

async function _fetchPirArticles() {
  const {pirId, page, pageSize} = _pirArtState;
  const listEl = document.getElementById('pir-art-list');
  listEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);">Loading…</div>';
  try {
    const resp = await fetch(`/api/pir/${pirId}/articles?page=${page}&page_size=${pageSize}`);
    const data = await resp.json();
    _pirArtState.total = data.total;
    const pages = Math.max(1, Math.ceil(data.total / pageSize));
    document.getElementById('pir-art-count').textContent = data.total.toLocaleString() + ' matching articles';
    document.getElementById('pir-art-pageinfo').textContent = `Page ${page} of ${pages}`;
    document.getElementById('pir-art-prev').disabled = page <= 1;
    document.getElementById('pir-art-next').disabled = page >= pages;
    if (!data.articles.length) {
      listEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);">No articles found.</div>';
      return;
    }
    _pirArticleData = data.articles;
    listEl.innerHTML = data.articles.map((a, i) => {
      const notedBadge = a.has_note
        ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--green);border:1px solid rgba(61,201,175,0.4);border-radius:2px;padding:1px 5px;background:rgba(61,201,175,0.08);white-space:nowrap;">&#10003; NOTED</span>`
        : '';
      return `
      <div style="padding:10px;background:var(--surface2);border-radius:3px;border:1px solid var(--border);">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
          <a href="${a.url}" target="_blank" style="color:var(--text-bright);font-size:13px;font-weight:600;text-decoration:none;flex:1;">${a.title}</a>
          <div style="display:flex;gap:4px;align-items:center;flex-shrink:0;">
            ${notedBadge}
            <button onclick="openPirNote(${i})" class="pir-btn" style="font-size:10px;padding:3px 8px;">📝 Note</button>
          </div>
        </div>
        <div style="margin-top:4px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);">
          ${[a.source, a.posted_on, a.news_type].filter(Boolean).join(' \xb7 ')}
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    listEl.innerHTML = '<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px;">Error loading articles.</div>';
    console.error(e);
  }
}

function pirArtPage(delta) {
  const pages = Math.max(1, Math.ceil(_pirArtState.total / _pirArtState.pageSize));
  _pirArtState.page = Math.max(1, Math.min(pages, _pirArtState.page + delta));
  _fetchPirArticles();
}

function closePirArticles() {
  closePirNote();
  document.getElementById('pir-art-overlay').style.display = 'none';
}

// ── PIR Analyst Notes ──────────────────────────────────────────
async function openPirNote(idx) {
  const a = _pirArticleData[idx];
  _pirNoteState = {pirId: _pirArtState.pirId, articleUrl: a.url, articleTitle: a.title};
  document.getElementById('pir-note-article-title').textContent = a.title;
  document.getElementById('pir-note-text').value    = '';
  document.getElementById('pir-note-analyst').value = '';
  document.getElementById('pir-note-updated').textContent = '';
  document.getElementById('pir-note-modal').style.display = 'flex';
  try {
    const resp = await fetch(`/api/pir/${_pirArtState.pirId}/note?url=${encodeURIComponent(a.url)}`);
    const data = await resp.json();
    document.getElementById('pir-note-text').value    = data.note    || '';
    document.getElementById('pir-note-analyst').value = data.analyst || '';
    if (data.updated_at) document.getElementById('pir-note-updated').textContent = 'Last saved: ' + data.updated_at.slice(0,16).replace('T',' ');
  } catch(e) { console.error(e); }
}

function closePirNote() {
  document.getElementById('pir-note-modal').style.display = 'none';
}

function savePirNote() {
  requireTAAuth(async ({ pass }) => {
    const note    = document.getElementById('pir-note-text').value;
    const analyst = document.getElementById('pir-note-analyst').value.trim();
    try {
      const resp = await fetch(`/api/pir/${_pirNoteState.pirId}/note`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pass},
        body: JSON.stringify({url: _pirNoteState.articleUrl, note, analyst}),
      });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) { alert('Error saving note'); return; }
      closeAuthModal();
      closePirNote();
      _fetchPirArticles();
    } catch(e) { console.error(e); alert('Request failed'); }
  }, { subtitle: 'Save analyst note' });
}

// ── PIR Export ────────────────────────────────────────────────
async function exportPir(pirId, pirTitle) {
  try {
    const resp = await fetch(`/api/pir/${pirId}/export/docx`);
    if (resp.status === 501) { alert('python-docx not installed on server.\nRun: pip install python-docx'); return; }
    if (!resp.ok) { alert('Export failed'); return; }
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `PIR_${pirTitle.replace(/[^a-zA-Z0-9]/g,'_')}_${new Date().toISOString().slice(0,10)}.docx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) { console.error(e); alert('Export error'); }
}

// ── PIR CRUD ───────────────────────────────────────────────────
async function loadPirs() {
  const listEl = document.getElementById('pir-list');
  listEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);padding:20px 0;">Loading…</div>';
  await _pirEnsureOptions();
  try {
    const resp = await fetch('/api/pir', { headers: _authAndClientHeaders() });
    const pirs = await resp.json();

    if (!pirs.length) {
      listEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);padding:20px 0;">No PIRs defined. Click + NEW PIR to create one.</div>';
      return;
    }

    const maxCov = Math.max(...pirs.map(p => p.coverage_count), 1);
    listEl.innerHTML = '';

    pirs.forEach(p => {
      const card = document.createElement('div');
      card.className = 'pir-card';
      const c = p.criteria || {};
      const tags = [
        ...(c.threat_actors||[]).map(x=>`TA:${x}`),
        ...(c.industries||[]).map(x=>`IND:${x}`),
        ...(c.countries||[]).map(x=>`CTY:${x}`),
        ...(c.keywords||[]).map(x=>`KW:${x}`),
        ...(c.ttps||[]).map(x=>`TTP:${x}`),
        ...(c.news_types||[]).map(x=>`TYPE:${x}`),
      ];
      const pct = Math.min(100, Math.round((p.coverage_count / maxCov) * 100));
      const statusColor = p.status === 'active' ? 'var(--green)' : 'var(--text-dim)';
      const gapBadge = p.is_gap ? `<span class="pir-gap-badge" title="This PIR matched articles historically but has no matches in the last 14 days — active collection gap.">COVERAGE GAP</span>` : '';
      const viewBtn = p.coverage_count > 0
        ? `<button class="pir-btn" onclick='viewPirArticles("${p.id}",${JSON.stringify(p.title)})'>View ${p.coverage_count.toLocaleString()}</button>`
        : '';

      card.innerHTML = `
        <span class="pir-badge ${p.priority}">${p.priority}</span>
        <div class="pir-body">
          <div class="pir-title">${p.title}${gapBadge}</div>
          ${p.description ? `<div class="pir-desc">${p.description}</div>` : ''}
          <div class="pir-criteria-tags">${tags.map(t=>`<span class="pir-tag">${t}</span>`).join('')}</div>
          <div class="pir-meta" style="margin-top:6px;">
            ${p.owner ? `<span>Owner: ${p.owner}</span>` : ''}
            ${p.start_date ? `<span>From: ${p.start_date}</span>` : ''}
            ${p.end_date   ? `<span>Until: ${p.end_date}</span>` : ''}
            ${p.last_match ? `<span>Last Hit: ${p.last_match}</span>` : ''}
            ${p.recent_coverage !== undefined ? `<span>14d: ${p.recent_coverage}</span>` : ''}
            <span style="color:${statusColor}">${p.status.toUpperCase()}</span>
          </div>
        </div>
        <div class="pir-coverage">
          <div class="pir-cov-num">${p.coverage_count.toLocaleString()}</div>
          <div class="pir-cov-label">articles</div>
          <div class="pir-cov-bar"><div class="pir-cov-fill" style="width:${pct}%"></div></div>
        </div>
        <div class="pir-actions">
          ${viewBtn}
          <button class="pir-btn" onclick='exportPir("${p.id}",${JSON.stringify(p.title)})'>Export</button>
          <button class="pir-btn" onclick='openPirModal(${JSON.stringify(p)})'>Edit</button>
          <button class="pir-btn del" onclick="deletePir('${p.id}')">Del</button>
        </div>`;
      listEl.appendChild(card);
    });
  } catch(e) {
    listEl.innerHTML = '<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px;padding:10px;">Error loading PIRs.</div>';
    console.error(e);
  }
}

async function openPirModal(pir) {
  _pirEditId = pir?.id || null;
  document.getElementById('pir-modal-title').textContent = pir ? 'Edit PIR' : 'New PIR';
  document.getElementById('pir-f-title').value    = pir?.title || '';
  document.getElementById('pir-f-desc').value     = pir?.description || '';
  document.getElementById('pir-f-priority').value = pir?.priority || 'P2';
  document.getElementById('pir-f-owner').value    = pir?.owner || '';
  document.getElementById('pir-f-keywords').value    = (pir?.criteria?.keywords || []).join(', ');
  document.getElementById('pir-f-start-date').value  = pir?.start_date || '';
  document.getElementById('pir-f-end-date').value    = pir?.end_date   || '';
  document.getElementById('pir-f-status-wrap').style.display = pir ? 'block' : 'none';
  document.getElementById('pir-f-status').value   = pir?.status || 'active';

  await _pirEnsureOptions();
  const c = pir?.criteria || {};
  _MS_FIELDS.forEach(f => {
    const apiKey = f === 'tas' ? 'threat_actors' : f;
    pirMsSet(f, c[apiKey] || []);
  });

  document.getElementById('pir-modal').style.display = 'flex';
}

function closePirModal() {
  document.getElementById('pir-modal').style.display = 'none';
  _MS_FIELDS.forEach(f => pirMsSet(f, []));
  _pirEditId = null;
}

function savePir() {
  const title = document.getElementById('pir-f-title').value.trim();
  if (!title) { alert('Title is required'); return; }

  requireTAAuth(async (password) => {
    const payload = {
      title,
      description: document.getElementById('pir-f-desc').value.trim(),
      priority:    document.getElementById('pir-f-priority').value,
      owner:       document.getElementById('pir-f-owner').value.trim(),
      criteria: {
        threat_actors: [..._pirSelected.tas],
        industries:    [..._pirSelected.industries],
        countries:     [..._pirSelected.countries],
        news_types:    [..._pirSelected.news_types],
        ttps:          [..._pirSelected.ttps],
        keywords:      document.getElementById('pir-f-keywords').value.split(',').map(s=>s.trim()).filter(Boolean),
      },
    };
    const startDate = document.getElementById('pir-f-start-date').value;
    const endDate   = document.getElementById('pir-f-end-date').value;
    if (startDate) payload.start_date = startDate;
    if (endDate)   payload.end_date   = endDate;
    if (_pirEditId) {
      payload.status     = document.getElementById('pir-f-status').value;
      payload.start_date = startDate || null;
      payload.end_date   = endDate   || null;
    }

    const url    = _pirEditId ? `/api/pir/${_pirEditId}` : '/api/pir';
    const method = _pirEditId ? 'PUT' : 'POST';
    try {
      const resp = await fetch(url, {
        method,
        headers: _authAndClientHeaders({'Content-Type':'application/json','Authorization':'Bearer '+password}),
        body: JSON.stringify(payload),
      });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) { alert('Error: ' + (await resp.json()).detail); return; }
      closePirModal();
      loadPirs();
    } catch(e) { console.error(e); alert('Request failed'); }
  });
}

function deletePir(pirId) {
  requireTAAuth((password) => {
    showConfirmModal({
      title:   'Delete PIR',
      okLabel: '✕ Delete',
      okColor: 'var(--red)',
      body: `<p style="font-size:13px;color:var(--text);line-height:1.7">Delete this PIR? This action cannot be undone.</p>`,
      onConfirm: async () => {
        try {
          const resp = await fetch(`/api/pir/${pirId}`, {
            method: 'DELETE',
            headers: _authAndClientHeaders({'Authorization': 'Bearer ' + password}),
          });
          if (resp.status === 401) { _authFailed(); return; }
          if (!resp.ok) { alert('Error deleting PIR'); return; }
          loadPirs();
        } catch(e) { console.error(e); }
      },
    });
  });
}

// ── RFI TRACKER ───────────────────────────────────────────────

let _rfiEditId    = null;
let _rfiFilter    = null;   // null = all

const _RFI_STATUS_COLOR = {
  open:        'var(--yellow, #f59e0b)',
  in_progress: 'var(--blue,  #3b82f6)',
  closed:      'var(--text-dim)',
};
const _RFI_STATUS_LABEL = { open: 'OPEN', in_progress: 'IN PROGRESS', closed: 'CLOSED' };

function rfiSetFilter(status) {
  _rfiFilter = status;
  ['all','open','in_progress','closed'].forEach(k => {
    document.getElementById(`rfi-f-${k}`).classList.toggle('active', (status ?? 'all') === k);
  });
  loadRfis();
}

async function loadRfis() {
  const listEl = document.getElementById('rfi-list');
  if (!_jwtValid()) {
    listEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);padding:20px 0;">Sign in to view RFIs.</div>';
    return;
  }
  listEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);padding:20px 0;">Loading…</div>';
  try {
    const qs  = _rfiFilter ? `?status=${_rfiFilter}&page_size=100` : '?page_size=100';
    const resp = await fetch(`/api/rfi${qs}`, {
      headers: _authAndClientHeaders(),
    });
    if (resp.status === 401) { _authFailed(); return; }
    const data = await resp.json();
    const rfis = data.rfis || [];

    // update count badge
    document.getElementById('intel-rfi-count').textContent = data.total ?? rfis.length;

    if (!rfis.length) {
      listEl.innerHTML = '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim);padding:20px 0;">No RFIs found. Click + NEW RFI to create one.</div>';
      return;
    }
    listEl.innerHTML = '';
    rfis.forEach(r => {
      const card = document.createElement('div');
      card.className = 'pir-card';
      const sc = _RFI_STATUS_COLOR[r.status] || 'var(--text-dim)';
      const sl = _RFI_STATUS_LABEL[r.status]  || r.status.toUpperCase();
      const due = r.due_date ? `Due: ${r.due_date}` : '';
      const linkedPir = r.linked_pir ? `<span class="pir-tag">PIR: ${r.linked_pir.slice(-6)}</span>` : '';
      const responsePreview = r.response ? `<div class="pir-desc" style="margin-top:4px;font-style:italic;">${r.response.slice(0,120)}${r.response.length>120?'…':''}</div>` : '';
      card.innerHTML = `
        <span class="pir-badge" style="background:${sc}20;border-color:${sc}50;color:${sc};min-width:80px;text-align:center;">${sl}</span>
        <div class="pir-body">
          <div class="pir-title" style="font-size:13px;">${r.question}</div>
          ${responsePreview}
          <div class="pir-meta" style="margin-top:6px;">
            <span>From: ${r.requester}</span>
            ${due ? `<span>${due}</span>` : ''}
            ${r.created_at ? `<span>Created: ${r.created_at.slice(0,10)}</span>` : ''}
            ${linkedPir}
          </div>
        </div>
        <div class="pir-actions">
          <button class="pir-btn" onclick='openRfiModal(${JSON.stringify(r)})'>Edit</button>
          <button class="pir-btn del" onclick="deleteRfi('${r.id}')">Del</button>
        </div>`;
      listEl.appendChild(card);
    });
  } catch(e) {
    listEl.innerHTML = '<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px;padding:10px;">Error loading RFIs.</div>';
    console.error(e);
  }
}

async function _rfiLoadPirOptions() {
  const sel = document.getElementById('rfi-f-linked-pir');
  sel.innerHTML = '<option value="">— None —</option>';
  try {
    const resp = await fetch('/api/pir', {
      headers: _authAndClientHeaders(),
    });
    if (!resp.ok) return;
    const pirs = await resp.json();
    (pirs || []).forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `[${p.priority}] ${p.title}`;
      sel.appendChild(opt);
    });
  } catch(e) { /* non-fatal */ }
}

async function openRfiModal(rfi) {
  _rfiEditId = rfi?.id || null;
  document.getElementById('rfi-modal-title').textContent = rfi ? 'Edit RFI' : 'New RFI';
  document.getElementById('rfi-f-requester').value  = rfi?.requester  || '';
  document.getElementById('rfi-f-question').value   = rfi?.question   || '';
  document.getElementById('rfi-f-due-date').value   = rfi?.due_date   || '';
  document.getElementById('rfi-f-status').value     = rfi?.status     || 'open';
  document.getElementById('rfi-f-response').value   = rfi?.response   || '';

  if (_jwtValid()) await _rfiLoadPirOptions();
  if (rfi?.linked_pir) document.getElementById('rfi-f-linked-pir').value = rfi.linked_pir;

  document.getElementById('rfi-modal').style.display = 'flex';
}

function closeRfiModal() {
  document.getElementById('rfi-modal').style.display = 'none';
  _rfiEditId = null;
}

function saveRfi() {
  const requester = document.getElementById('rfi-f-requester').value.trim();
  const question  = document.getElementById('rfi-f-question').value.trim();
  if (!requester || !question) { alert('Requester and Question are required'); return; }

  requireTAAuth(async (password) => {
    const payload = {
      requester,
      question,
      status:     document.getElementById('rfi-f-status').value,
      response:   document.getElementById('rfi-f-response').value.trim(),
      due_date:   document.getElementById('rfi-f-due-date').value || null,
      linked_pir: document.getElementById('rfi-f-linked-pir').value || null,
    };
    const url    = _rfiEditId ? `/api/rfi/${_rfiEditId}` : '/api/rfi';
    const method = _rfiEditId ? 'PUT' : 'POST';
    try {
      const resp = await fetch(url, {
        method,
        headers: _authAndClientHeaders({'Content-Type': 'application/json', 'Authorization': 'Bearer ' + password}),
        body: JSON.stringify(payload),
      });
      if (resp.status === 401) { _authFailed(); return; }
      if (!resp.ok) { alert('Error: ' + (await resp.json()).detail); return; }
      closeRfiModal();
      loadRfis();
    } catch(e) { console.error(e); alert('Request failed'); }
  });
}

function deleteRfi(rfiId) {
  requireTAAuth((password) => {
    showConfirmModal({
      title:   'Delete RFI',
      okLabel: '✕ Delete',
      okColor: 'var(--red)',
      body: `<p style="font-size:13px;color:var(--text);line-height:1.7">Delete this RFI? This action cannot be undone.</p>`,
      onConfirm: async () => {
        try {
          const resp = await fetch(`/api/rfi/${rfiId}`, {
            method:  'DELETE',
            headers: _authAndClientHeaders({'Authorization': 'Bearer ' + password}),
          });
          if (resp.status === 401) { _authFailed(); return; }
          if (!resp.ok) { alert('Error deleting RFI'); return; }
          loadRfis();
        } catch(e) { console.error(e); }
      },
    });
  });
}
