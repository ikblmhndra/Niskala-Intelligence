// ── ATT&CK DATABASE ────────────────────────────────────────────

let _attackdbLoaded = false;
let _attackTechPage = 1, _attackTechTotal = 0, _attackTechPageSize = 50;
let _attackGrpPage  = 1, _attackGrpTotal  = 0, _attackGrpPageSize  = 50;
let _attackSwPage   = 1, _attackSwTotal   = 0, _attackSwPageSize   = 50;
let _attackMitPage  = 1, _attackMitTotal  = 0, _attackMitPageSize  = 50;
let _attackTechTimer = null, _attackGrpTimer = null, _attackSwTimer = null, _attackMitTimer = null;

const _DOMAIN_LABELS = {
  'enterprise-attack': 'Enterprise',
  'ics-attack': 'ICS',
  'mobile-attack': 'Mobile',
};

async function loadAttackDB() {
  _attackdbSetActiveTab('techniques');  // visual only — no data load
  await loadAttackStatus();
  if (!_attackdbLoaded) {
    _attackdbLoaded = true;
    await _loadTacticOptions();
    await _fetchTechniques();
  }
}

async function loadAttackStatus() {
  const row = document.getElementById('attackdb-status-row');
  row.innerHTML = '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim)">Loading sync status…</span>';
  try {
    const data = await fetch('/api/attack/status', { headers: _authHeader() }).then(r => r.json());
    row.innerHTML = data.map(d => _renderDomainCard(d)).join('');
  } catch {
    row.innerHTML = '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--red)">Failed to load sync status</span>';
  }
}

function _renderDomainCard(d) {
  const status = d.status || 'never';
  const color = status === 'success' ? 'var(--accent)' : status === 'error' ? 'var(--red)' : status === 'syncing' ? '#ffa000' : 'var(--text-dim)';
  const version = d.version ? `v${d.version}` : '—';
  const lastSync = d.last_sync ? new Date(d.last_sync).toLocaleDateString() : 'Never';
  const mitreModified = d.mitre_modified ? new Date(d.mitre_modified).toLocaleDateString() : '—';
  const techs = d.technique_count ?? '—';
  const groups = d.group_count ?? '—';
  const sw = d.software_count ?? '—';
  const mits = d.mitigation_count ?? '—';

  function _delta(val, key) {
    const d_val = d[`delta_${key}`];
    if (d_val == null || d_val === 0) return '';
    const sign = d_val > 0 ? '+' : '';
    const col = d_val > 0 ? 'var(--accent)' : 'var(--red)';
    return ` <span style="color:${col};font-size:9px">${sign}${d_val}</span>`;
  }

  let phaseHtml = '';
  if (status === 'syncing' && d.phase) {
    if (d.phase === 'downloading' && d.bytes_downloaded) {
      const mb = (d.bytes_downloaded / 1024 / 1024).toFixed(1);
      const pct = d.download_pct || '';
      const totalMb = d.bytes_total ? ` / ${(d.bytes_total / 1024 / 1024).toFixed(0)}MB` : '';
      phaseHtml = `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#ffa000;margin-top:2px">↓ downloading ${mb}MB${totalMb} ${pct}</div>`;
    } else if (d.phase) {
      phaseHtml = `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#ffa000;margin-top:2px">⟳ ${d.phase}</div>`;
    }
  }

  return `<div data-sync-status="${status}" style="background:var(--surface-2,rgba(255,255,255,0.03));border:1px solid var(--border);border-radius:5px;padding:12px 14px;min-width:200px;flex:1;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;color:var(--text-bright)">${d.label || d.domain_key}</span>
      <button class="btn-reset" style="font-size:10px;padding:2px 8px;" onclick="attackSyncDomain('${d.domain_key}')">Sync</button>
    </div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${color};margin-bottom:${phaseHtml?'2px':'6px'};">● ${status.toUpperCase()} · ${version}</div>${phaseHtml ? phaseHtml + '<div style="margin-bottom:4px"></div>' : ''}
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);line-height:1.6;">
      MITRE updated: ${mitreModified}<br>
      Last sync: ${lastSync}<br>
      Techniques: ${techs}${_delta(techs,'technique_count')} · Groups: ${groups}${_delta(groups,'group_count')}<br>
      Software: ${sw}${_delta(sw,'software_count')} · Mitigations: ${mits}${_delta(mits,'mitigation_count')}
    </div>
  </div>`;
}

async function attackSyncAll() {
  const btn = document.getElementById('attackdb-sync-all-btn');
  btn.disabled = true;
  btn.textContent = '⟳ Syncing…';
  try {
    await fetch('/api/attack/sync', { method: 'POST', headers: { 'Content-Type': 'application/json', ..._authHeader() }, body: JSON.stringify({}) });
    btn.textContent = '⟳ Sync started';
    setTimeout(() => {
      btn.textContent = '⟳ Sync All Domains';
      btn.disabled = false;
      _pollSyncStatus();
    }, 2000);
  } catch {
    btn.textContent = '⟳ Sync All Domains';
    btn.disabled = false;
  }
}

async function attackSyncDomain(key) {
  try {
    await fetch(`/api/attack/sync/${key}`, { method: 'GET', headers: _authHeader() });
    await loadAttackStatus();  // refresh immediately to show "syncing"
    _pollSyncStatus();
  } catch(e) {
    console.error(e);
  }
}

let _syncPollTimer = null;
function _pollSyncStatus() {
  if (_syncPollTimer) clearTimeout(_syncPollTimer);
  async function poll() {
    await loadAttackStatus();
    // keep polling while any domain is still syncing
    const cards = document.querySelectorAll('#attackdb-status-row [data-sync-status]');
    const stillSyncing = [...cards].some(el => el.dataset.syncStatus === 'syncing');
    if (stillSyncing) {
      _syncPollTimer = setTimeout(poll, 5000);
    }
  }
  setTimeout(poll, 2000);
}

// ── Browse tabs ────────────────────────────────────────────────

function _attackdbSetActiveTab(tab) {
  ['techniques','groups','software','mitigations'].forEach(t => {
    document.getElementById(`attackdb-browse-${t}`).style.display = t === tab ? '' : 'none';
    const btn = document.getElementById(`attackdb-tab-${t}`);
    btn.style.opacity = t === tab ? '1' : '0.45';
    btn.style.textDecoration = t === tab ? 'underline' : 'none';
  });
}

function attackdbSwitchBrowse(tab) {
  _attackdbSetActiveTab(tab);
  if (tab === 'techniques')  _fetchTechniques();
  if (tab === 'groups')      _attackGrpPage = 1, _fetchGroups();
  if (tab === 'software')    _attackSwPage = 1,  _fetchSoftware();
  if (tab === 'mitigations') _attackMitPage = 1, _fetchMitigations();
}

async function _loadTacticOptions() {
  try {
    const domain = document.getElementById('attackdb-tech-domain').value;
    const url = '/api/attack/tactics/distinct' + (domain ? `?domain=${domain}` : '');
    const tactics = await fetch(url).then(r => r.json());
    const sel = document.getElementById('attackdb-tech-tactic');
    // clear all except "All tactics" default
    while (sel.options.length > 1) sel.remove(1);
    tactics.forEach(shortname => {
      const opt = document.createElement('option');
      opt.value = shortname;
      // "initial-access" → "Initial Access"
      opt.textContent = shortname.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      sel.appendChild(opt);
    });
  } catch {}
}

// ── Techniques ─────────────────────────────────────────────────

function attackdbTechSearch() {
  clearTimeout(_attackTechTimer);
  _attackTechTimer = setTimeout(() => { _attackTechPage = 1; _fetchTechniques(); }, 350);
}

async function _fetchTechniques() {
  const search  = document.getElementById('attackdb-tech-search').value.trim();
  const domain  = document.getElementById('attackdb-tech-domain').value;
  const tactic  = document.getElementById('attackdb-tech-tactic').value;
  const subs    = document.getElementById('attackdb-tech-subs').value;  // "", "true", "false"
  const loading = document.getElementById('attackdb-tech-loading');
  const tbody   = document.getElementById('attackdb-tech-tbody');

  loading.style.display = '';
  tbody.innerHTML = '';

  const params = new URLSearchParams({page: _attackTechPage, page_size: _attackTechPageSize});
  if (search) params.set('search', search);
  if (domain) params.set('domain', domain);
  if (tactic) params.set('tactic', tactic);
  if (subs)   params.set('is_subtechnique', subs);  // "true" or "false"

  try {
    const data = await fetch(`/api/attack/techniques?${params}`, { headers: _authHeader() }).then(r => r.json());
    loading.style.display = 'none';
    _attackTechTotal = data.total;
    _updatePager('attackdb-tech', _attackTechPage, _attackTechPageSize, _attackTechTotal);

    if (!data.techniques.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding:12px 8px;color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px;">No techniques found</td></tr>';
      return;
    }
    tbody.innerHTML = data.techniques.map(t => `
      <tr style="border-bottom:1px solid var(--border);cursor:pointer;" onclick="showTechniqueDetail('${t.attack_id}')" onmouseover="this.style.background='rgba(47,129,247,0.05)'" onmouseout="this.style.background=''">
        <td style="padding:5px 8px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-size:11px;white-space:nowrap">${t.attack_id}</td>
        <td style="padding:5px 8px;color:var(--text-bright);font-family:'IBM Plex Mono',monospace;font-size:11px">${t.is_subtechnique ? '↳ ' : ''}${_esc(t.name)}</td>
        <td style="padding:5px 8px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:10px">${(t.tactics||[]).join(', ')}</td>
        <td style="padding:5px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px">${_domainBadges(t.domains)}</td>
      </tr>`).join('');
  } catch(e) {
    loading.style.display = 'none';
    tbody.innerHTML = `<tr><td colspan="4" style="padding:12px 8px;color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:11px;">Error loading techniques</td></tr>`;
  }
}

function attackdbTechPage(dir) {
  const maxPage = Math.ceil(_attackTechTotal / _attackTechPageSize);
  _attackTechPage = Math.max(1, Math.min(maxPage, _attackTechPage + dir));
  _fetchTechniques();
}

// ── Groups ─────────────────────────────────────────────────────

function attackdbGrpSearch() {
  clearTimeout(_attackGrpTimer);
  _attackGrpTimer = setTimeout(() => { _attackGrpPage = 1; _fetchGroups(); }, 350);
}

async function _fetchGroups() {
  const search  = document.getElementById('attackdb-grp-search').value.trim();
  const domain  = document.getElementById('attackdb-grp-domain').value;
  const loading = document.getElementById('attackdb-grp-loading');
  const tbody   = document.getElementById('attackdb-grp-tbody');

  loading.style.display = '';
  tbody.innerHTML = '';

  const params = new URLSearchParams({page: _attackGrpPage, page_size: _attackGrpPageSize});
  if (search) params.set('search', search);
  if (domain) params.set('domain', domain);

  try {
    const data = await fetch(`/api/attack/groups?${params}`, { headers: _authHeader() }).then(r => r.json());
    loading.style.display = 'none';
    _attackGrpTotal = data.total;
    _updatePager('attackdb-grp', _attackGrpPage, _attackGrpPageSize, _attackGrpTotal);

    if (!data.groups.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding:12px 8px;color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px;">No groups found</td></tr>';
      return;
    }
    tbody.innerHTML = data.groups.map(g => `
      <tr style="border-bottom:1px solid var(--border);cursor:pointer;" onclick="showGroupDetail('${g.group_id}')" onmouseover="this.style.background='rgba(47,129,247,0.05)'" onmouseout="this.style.background=''">
        <td style="padding:5px 8px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-size:11px">${g.group_id}</td>
        <td style="padding:5px 8px;color:var(--text-bright);font-family:'IBM Plex Mono',monospace;font-size:11px">${_esc(g.name)}</td>
        <td style="padding:5px 8px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:10px">${(g.aliases||[]).slice(0,3).map(_esc).join(', ')}</td>
        <td style="padding:5px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px">${_domainBadges(g.domains)}</td>
      </tr>`).join('');
  } catch {
    loading.style.display = 'none';
    tbody.innerHTML = `<tr><td colspan="4" style="padding:12px 8px;color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:11px;">Error loading groups</td></tr>`;
  }
}

function attackdbGrpPage(dir) {
  const maxPage = Math.ceil(_attackGrpTotal / _attackGrpPageSize);
  _attackGrpPage = Math.max(1, Math.min(maxPage, _attackGrpPage + dir));
  _fetchGroups();
}

// ── Software ───────────────────────────────────────────────────

function attackdbSwSearch() {
  clearTimeout(_attackSwTimer);
  _attackSwTimer = setTimeout(() => { _attackSwPage = 1; _fetchSoftware(); }, 350);
}

async function _fetchSoftware() {
  const search  = document.getElementById('attackdb-sw-search').value.trim();
  const domain  = document.getElementById('attackdb-sw-domain').value;
  const swType  = document.getElementById('attackdb-sw-type').value;
  const loading = document.getElementById('attackdb-sw-loading');
  const tbody   = document.getElementById('attackdb-sw-tbody');

  loading.style.display = '';
  tbody.innerHTML = '';

  const params = new URLSearchParams({page: _attackSwPage, page_size: _attackSwPageSize});
  if (search) params.set('search', search);
  if (domain) params.set('domain', domain);
  if (swType) params.set('type', swType);

  try {
    const data = await fetch(`/api/attack/software?${params}`, { headers: _authHeader() }).then(r => r.json());
    loading.style.display = 'none';
    _attackSwTotal = data.total;
    _updatePager('attackdb-sw', _attackSwPage, _attackSwPageSize, _attackSwTotal);

    if (!data.software.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="padding:12px 8px;color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px;">No software found</td></tr>';
      return;
    }
    tbody.innerHTML = data.software.map(s => `
      <tr style="border-bottom:1px solid var(--border);cursor:pointer;" onclick="showSoftwareDetail('${s.software_id}')" onmouseover="this.style.background='rgba(47,129,247,0.05)'" onmouseout="this.style.background=''">
        <td style="padding:5px 8px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-size:11px">${s.software_id}</td>
        <td style="padding:5px 8px;color:var(--text-bright);font-family:'IBM Plex Mono',monospace;font-size:11px">${_esc(s.name)}</td>
        <td style="padding:5px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px"><span style="background:${s.software_type==='malware'?'rgba(218,54,51,0.1)':'rgba(47,129,247,0.1)'};padding:1px 5px;border-radius:3px;color:${s.software_type==='malware'?'var(--red)':'var(--accent)'}">${s.software_type}</span></td>
        <td style="padding:5px 8px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:10px">${(s.platforms||[]).slice(0,3).join(', ')}</td>
        <td style="padding:5px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px">${_domainBadges(s.domains)}</td>
      </tr>`).join('');
  } catch {
    loading.style.display = 'none';
    tbody.innerHTML = `<tr><td colspan="5" style="padding:12px 8px;color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:11px;">Error loading software</td></tr>`;
  }
}

function attackdbSwPage(dir) {
  const maxPage = Math.ceil(_attackSwTotal / _attackSwPageSize);
  _attackSwPage = Math.max(1, Math.min(maxPage, _attackSwPage + dir));
  _fetchSoftware();
}

// ── Mitigations ────────────────────────────────────────────────

function attackdbMitSearch() {
  clearTimeout(_attackMitTimer);
  _attackMitTimer = setTimeout(() => { _attackMitPage = 1; _fetchMitigations(); }, 350);
}

async function _fetchMitigations() {
  const search  = document.getElementById('attackdb-mit-search').value.trim();
  const domain  = document.getElementById('attackdb-mit-domain').value;
  const loading = document.getElementById('attackdb-mit-loading');
  const tbody   = document.getElementById('attackdb-mit-tbody');

  loading.style.display = '';
  tbody.innerHTML = '';

  const params = new URLSearchParams({page: _attackMitPage, page_size: _attackMitPageSize});
  if (search) params.set('search', search);
  if (domain) params.set('domain', domain);

  try {
    const data = await fetch(`/api/attack/mitigations?${params}`, { headers: _authHeader() }).then(r => r.json());
    loading.style.display = 'none';
    _attackMitTotal = data.total;
    _updatePager('attackdb-mit', _attackMitPage, _attackMitPageSize, _attackMitTotal);

    if (!data.mitigations.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="padding:12px 8px;color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px;">No mitigations found</td></tr>';
      return;
    }
    tbody.innerHTML = data.mitigations.map(m => `
      <tr style="border-bottom:1px solid var(--border);">
        <td style="padding:5px 8px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-size:11px">${m.mitigation_id}</td>
        <td style="padding:5px 8px;color:var(--text-bright);font-family:'IBM Plex Mono',monospace;font-size:11px" title="${_esc(m.description||'')}">${_esc(m.name)}</td>
        <td style="padding:5px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px">${_domainBadges(m.domains)}</td>
      </tr>`).join('');
  } catch {
    loading.style.display = 'none';
    tbody.innerHTML = `<tr><td colspan="3" style="padding:12px 8px;color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:11px;">Error loading mitigations</td></tr>`;
  }
}

function attackdbMitPage(dir) {
  const maxPage = Math.ceil(_attackMitTotal / _attackMitPageSize);
  _attackMitPage = Math.max(1, Math.min(maxPage, _attackMitPage + dir));
  _fetchMitigations();
}

// ── Detail modals ──────────────────────────────────────────────

async function showTechniqueDetail(attackId) {
  _openModal('<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim)">Loading…</div>');
  try {
    const t = await fetch(`/api/attack/techniques/${attackId}`, { headers: _authHeader() }).then(r => r.json());
    const domains = _domainBadges(t.domains);
    const subTechs = (t.sub_techniques||[]).map(s =>
      `<span style="cursor:pointer;color:var(--accent)" onclick="showTechniqueDetail('${s.attack_id}')">${s.attack_id} ${_esc(s.name)}</span>`
    ).join('<br>');
    const mits = (t.mitigations||[]).map(m =>
      `<div style="margin-bottom:6px"><span style="color:var(--accent)">${m.mitigation_id}</span> ${_esc(m.name)}<br><span style="color:var(--text-dim);font-size:10px">${_esc((m.description||'').slice(0,200))}${m.description&&m.description.length>200?'…':''}</span></div>`
    ).join('') || '<span style="color:var(--text-dim)">None</span>';
    const groups = (t.groups||[]).map(g =>
      `<span style="cursor:pointer;color:var(--accent);margin-right:8px" onclick="showGroupDetail('${g.group_id}')">${g.group_id} ${_esc(g.name)}</span>`
    ).join('') || '<span style="color:var(--text-dim)">None</span>';
    const sw = (t.software||[]).map(s =>
      `<span style="cursor:pointer;color:var(--accent);margin-right:8px" onclick="showSoftwareDetail('${s.software_id}')">${s.software_id} ${_esc(s.name)}</span>`
    ).join('') || '<span style="color:var(--text-dim)">None</span>';

    _openModal(`
      <div style="font-family:'IBM Plex Mono',monospace">
        <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:14px;flex-wrap:wrap">
          <div>
            <div style="font-size:11px;color:var(--accent)">${t.attack_id}</div>
            <div style="font-size:16px;font-weight:700;color:var(--text-bright);margin-top:2px">${_esc(t.name)}</div>
            <div style="font-size:10px;color:var(--text-dim);margin-top:4px">${(t.tactics||[]).join(' · ')} ${domains}</div>
          </div>
          <a href="${t.url||'#'}" target="_blank" style="margin-left:auto;font-size:10px;color:var(--accent)">MITRE ↗</a>
        </div>
        <div style="font-size:11px;color:var(--text);line-height:1.6;margin-bottom:14px;max-height:180px;overflow-y:auto">${_esc(t.description||'')}</div>
        ${t.platforms&&t.platforms.length ? `<div style="font-size:10px;color:var(--text-dim);margin-bottom:10px">Platforms: ${t.platforms.join(', ')}</div>` : ''}
        ${subTechs ? `<div style="margin-bottom:12px"><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Sub-techniques (${t.sub_techniques.length})</div>${subTechs}</div>` : ''}
        <div style="margin-bottom:12px"><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Mitigations (${(t.mitigations||[]).length})</div>${mits}</div>
        <div style="margin-bottom:12px"><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Groups using this (${(t.groups||[]).length})</div>${groups}</div>
        <div><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Software (${(t.software||[]).length})</div>${sw}</div>
      </div>`);
  } catch {
    _openModal('<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Failed to load technique</div>');
  }
}

async function showGroupDetail(groupId) {
  _openModal('<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim)">Loading…</div>');
  try {
    const g = await fetch(`/api/attack/groups/${groupId}`, { headers: _authHeader() }).then(r => r.json());
    const techs = (g.techniques||[]).map(t =>
      `<span style="cursor:pointer;color:var(--accent);margin-right:6px;display:inline-block;margin-bottom:3px" onclick="showTechniqueDetail('${t.attack_id}')">${t.attack_id}</span>`
    ).join('') || '<span style="color:var(--text-dim)">None</span>';
    const sw = (g.software||[]).map(s =>
      `<span style="cursor:pointer;color:var(--accent);margin-right:8px" onclick="showSoftwareDetail('${s.software_id}')">${s.software_id} ${_esc(s.name)}</span>`
    ).join('') || '<span style="color:var(--text-dim)">None</span>';

    _openModal(`
      <div style="font-family:'IBM Plex Mono',monospace">
        <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:14px">
          <div>
            <div style="font-size:11px;color:var(--accent)">${g.group_id}</div>
            <div style="font-size:16px;font-weight:700;color:var(--text-bright);margin-top:2px">${_esc(g.name)}</div>
            ${g.aliases&&g.aliases.length ? `<div style="font-size:10px;color:var(--text-dim);margin-top:3px">aka ${g.aliases.slice(0,5).map(_esc).join(', ')}</div>` : ''}
            <div style="margin-top:4px">${_domainBadges(g.domains)}</div>
          </div>
          <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
            <button class="btn-apply" style="font-size:10px;padding:3px 10px" onclick="openAttackDBNavigator('${g.group_id}')" title="Open this group's techniques in Navigator">⧉ Navigator</button>
            <a href="${g.url||'#'}" target="_blank" style="font-size:10px;color:var(--accent)">MITRE ↗</a>
          </div>
        </div>
        <div style="font-size:11px;color:var(--text);line-height:1.6;margin-bottom:14px;max-height:160px;overflow-y:auto">${_esc(g.description||'')}</div>
        <div style="margin-bottom:12px"><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Techniques used (${(g.techniques||[]).length})</div><div style="max-height:140px;overflow-y:auto">${techs}</div></div>
        <div><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Software (${(g.software||[]).length})</div>${sw}</div>
      </div>`);
  } catch {
    _openModal('<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Failed to load group</div>');
  }
}

async function showSoftwareDetail(softwareId) {
  _openModal('<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--text-dim)">Loading…</div>');
  try {
    const s = await fetch(`/api/attack/software/${softwareId}`, { headers: _authHeader() }).then(r => r.json());
    const groups = (s.groups||[]).map(g =>
      `<span style="cursor:pointer;color:var(--accent);margin-right:8px" onclick="showGroupDetail('${g.group_id}')">${g.group_id} ${_esc(g.name)}</span>`
    ).join('') || '<span style="color:var(--text-dim)">None</span>';
    const techs = (s.techniques||[]).map(t =>
      `<span style="cursor:pointer;color:var(--accent);margin-right:6px;display:inline-block;margin-bottom:3px" onclick="showTechniqueDetail('${t.attack_id}')">${t.attack_id}</span>`
    ).join('') || '<span style="color:var(--text-dim)">None</span>';

    _openModal(`
      <div style="font-family:'IBM Plex Mono',monospace">
        <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:14px">
          <div>
            <div style="font-size:11px;color:var(--accent)">${s.software_id}</div>
            <div style="font-size:16px;font-weight:700;color:var(--text-bright);margin-top:2px">${_esc(s.name)}</div>
            <div style="font-size:10px;margin-top:4px"><span style="background:${s.software_type==='malware'?'rgba(218,54,51,0.1)':'rgba(47,129,247,0.1)'};padding:1px 5px;border-radius:3px;color:${s.software_type==='malware'?'var(--red)':'var(--accent)'}">${s.software_type}</span> ${_domainBadges(s.domains)}</div>
          </div>
          <a href="${s.url||'#'}" target="_blank" style="margin-left:auto;font-size:10px;color:var(--accent)">MITRE ↗</a>
        </div>
        <div style="font-size:11px;color:var(--text);line-height:1.6;margin-bottom:14px;max-height:160px;overflow-y:auto">${_esc(s.description||'')}</div>
        <div style="margin-bottom:12px"><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Used by groups (${(s.groups||[]).length})</div>${groups}</div>
        <div><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Techniques (${(s.techniques||[]).length})</div><div style="max-height:120px;overflow-y:auto">${techs}</div></div>
      </div>`);
  } catch {
    _openModal('<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Failed to load software</div>');
  }
}

// ── Navigator export ───────────────────────────────────────────

function openAttackDBNavigator(groupId) {
  const params = new URLSearchParams();
  if (groupId) {
    params.set('group_id', groupId);
  } else {
    const search = document.getElementById('attackdb-tech-search')?.value.trim();
    const domain = document.getElementById('attackdb-tech-domain')?.value;
    const tactic = document.getElementById('attackdb-tech-tactic')?.value;
    const subs   = document.getElementById('attackdb-tech-subs')?.value;
    if (search) params.set('search', search);
    if (domain) params.set('domain', domain);
    if (tactic) params.set('tactic', tactic);
    if (subs)   params.set('is_subtechnique', subs);
  }
  const layerUrl = encodeURIComponent(`${window.location.origin}/api/attack/navigator-layer?${params}`);
  window.open(`https://mitre-attack.github.io/attack-navigator/#layerURL=${layerUrl}`, '_blank');
}

// ── Helpers ────────────────────────────────────────────────────

function _openModal(html) {
  document.getElementById('attackdb-modal-content').innerHTML = html;
  document.getElementById('attackdb-modal').style.display = '';
}

function _esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function _domainBadges(domains) {
  return (domains||[]).map(d => {
    const label = _DOMAIN_LABELS[d] || d;
    const color = d === 'enterprise-attack' ? 'rgba(47,129,247,0.15)' : d === 'ics-attack' ? 'rgba(255,160,0,0.15)' : 'rgba(180,100,255,0.15)';
    const textColor = d === 'enterprise-attack' ? 'var(--accent)' : d === 'ics-attack' ? '#ffa000' : '#b464ff';
    return `<span style="background:${color};color:${textColor};padding:1px 5px;border-radius:3px;font-size:9px;margin-right:3px">${label}</span>`;
  }).join('');
}

function _updatePager(prefix, page, pageSize, total) {
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const info    = document.getElementById(`${prefix}-pageinfo`);
  const prev    = document.getElementById(`${prefix}-prev`);
  const next    = document.getElementById(`${prefix}-next`);
  if (info) info.textContent = `Page ${page}/${maxPage} · ${total} total`;
  if (prev) prev.disabled = page <= 1;
  if (next) next.disabled = page >= maxPage;
}
