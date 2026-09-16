// ── PACKAGE VULNERABILITY MONITORING ─────────────────────────
const _pvPkgState  = { page: 1, pageSize: 50, total: 0 };
const _pvVulnState = { page: 1, pageSize: 50, total: 0 };
let   _pvSubview   = 'vulns';
let   _pvPkgMap    = {};  // _id → package doc

const _PV_SEV_COLOR = {
  CRITICAL: { bg: 'rgba(218,54,51,0.2)',    fg: '#DA3633',          border: 'rgba(218,54,51,0.5)' },
  HIGH:     { bg: 'rgba(227,179,65,0.2)',   fg: 'var(--orange)',    border: 'rgba(227,179,65,0.5)' },
  MEDIUM:   { bg: 'rgba(88,166,255,0.15)', fg: 'var(--accent3)',   border: 'rgba(88,166,255,0.4)' },
  LOW:      { bg: 'rgba(47,129,247,0.12)',  fg: 'var(--accent)',    border: 'rgba(47,129,247,0.4)' },
  UNKNOWN:  { bg: 'rgba(120,120,120,0.12)', fg: 'var(--text-dim)',  border: 'rgba(120,120,120,0.3)' },
  NONE:     { bg: 'rgba(120,120,120,0.08)', fg: 'var(--text-dim)',  border: 'rgba(120,120,120,0.2)' },
};

const _ECO_COLOR = {
  npm:         { bg: 'rgba(203,56,55,0.15)',    fg: '#cb3837' },
  PyPI:        { bg: 'rgba(55,118,171,0.15)',   fg: '#3776ab' },
  Go:          { bg: 'rgba(0,173,216,0.15)',    fg: '#00add8' },
  Maven:       { bg: 'rgba(194,25,25,0.15)',    fg: '#c21919' },
  'crates.io': { bg: 'rgba(222,165,132,0.2)',   fg: '#ce422b' },
  NuGet:       { bg: 'rgba(8,124,176,0.15)',    fg: '#087ab0' },
  RubyGems:    { bg: 'rgba(204,52,45,0.15)',    fg: '#cc342d' },
  Packagist:   { bg: 'rgba(242,96,50,0.15)',    fg: '#f26032' },
  Hex:         { bg: 'rgba(100,0,212,0.15)',    fg: '#6400d4' },
};


function _pvSevBadge(sev) {
  const s = (sev || 'UNKNOWN').toUpperCase();
  const c = _PV_SEV_COLOR[s] || _PV_SEV_COLOR.UNKNOWN;
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:2px 7px;border-radius:3px;background:${c.bg};color:${c.fg};border:1px solid ${c.border}">${s}</span>`;
}

function _pvEcoBadge(eco) {
  const c = _ECO_COLOR[eco] || { bg: 'rgba(120,120,120,0.1)', fg: 'var(--text-dim)' };
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:2px 7px;border-radius:3px;background:${c.bg};color:${c.fg}">${esc(eco)}</span>`;
}

function _pvStatus(msg, ok) {
  const el = document.getElementById('pv-status');
  if (!el) return;
  el.textContent = msg;
  el.className = `ta-status show ${ok ? 'ok' : 'err'}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 4000);
}

function pvSwitchSubview(view) {
  _pvSubview = view;
  const isVulns = view === 'vulns';
  document.getElementById('pv-subview-packages').style.display = isVulns ? 'none' : '';
  document.getElementById('pv-subview-vulns').style.display    = isVulns ? '' : 'none';
  document.getElementById('pv-filter-bar').style.display       = isVulns ? '' : 'none';
  document.getElementById('pv-stats-grid').style.display       = isVulns ? '' : 'none';
  document.getElementById('pv-view-pkgs-btn').classList.toggle('active',  !isVulns);
  document.getElementById('pv-view-vulns-btn').classList.toggle('active', isVulns);
  if (isVulns) pvLoadVulns(); else pvLoadPackages();
}

// ── Stats ─────────────────────────────────────────────────────

async function pvLoadStats() {
  try {
    const resp = await fetch('/api/pkgvuln/stats', { headers: _authAndClientHeaders() });
    if (!resp.ok) return;
    const d = await resp.json();
    document.getElementById('pv-stat-packages').textContent = d.packages     ?? '—';
    document.getElementById('pv-stat-critical').textContent = d.critical     ?? '—';
    document.getElementById('pv-stat-high').textContent     = d.high         ?? '—';
    document.getElementById('pv-stat-kev').textContent      = d.kev_count    ?? '—';
    document.getElementById('pv-stat-unacked').textContent  = d.unacknowledged ?? '—';
    document.getElementById('pv-vuln-count-badge').textContent = d.total_vulns ?? '—';
    const _pvSubBtn = document.getElementById('pv-submenu-count');
    if (_pvSubBtn) _pvSubBtn.textContent = d.total_vulns ?? '—';
  } catch(e) { console.error('pv stats error:', e); }
}

// ── Package list ──────────────────────────────────────────────

async function pvLoadPackages() {
  const tbody = document.getElementById('pv-pkg-tbody');
  tbody.innerHTML = `<tr><td colspan="9" class="ta-td">${loadingHTML()}</td></tr>`;

  try {
    const params = new URLSearchParams({ page: _pvPkgState.page, page_size: _pvPkgState.pageSize });
    const resp = await fetch(`/api/pkgvuln/packages?${params}`, { headers: _authAndClientHeaders() });
    if (!resp.ok) throw new Error(resp.statusText);
    const d = await resp.json();

    _pvPkgState.total = d.total;
    document.getElementById('pv-pkg-count-badge').textContent = d.total;
    document.getElementById('pv-pkg-total').textContent =
      `${d.total} package${d.total !== 1 ? 's' : ''} monitored`;

    _pvPkgMap = {};
    const pkgSel  = document.getElementById('pv-pkg-filter');
    const prevPkg = pkgSel.value;
    pkgSel.innerHTML = '<option value="">All Packages</option>';

    if (!d.items.length) {
      tbody.innerHTML = `<tr><td colspan="10" class="ta-td">${emptyHTML('No packages monitored — add one or import a lockfile')}</td></tr>`;
    } else {
      const offset = (_pvPkgState.page - 1) * _pvPkgState.pageSize;
      tbody.innerHTML = d.items.map((p, i) => {
        _pvPkgMap[p._id] = p;
        pkgSel.innerHTML += `<option value="${esc(p.name)}" ${p.name === prevPkg ? 'selected' : ''}>${esc(p.name)} (${esc(p.ecosystem)})</option>`;

        const vulnBadges = _pvVulnCountBadges(p);
        const lastScan   = p.last_scan ? p.last_scan.slice(0, 16).replace('T', ' ') : '—';
        const verStr     = p.version
          ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright)">${esc(p.version)}</span>`
          : `<span style="font-size:10px;color:var(--text-dim)">—</span>`;
        const latestStr  = p.latest_version
          ? `<span style="font-size:10px;color:var(--text-dim)"> / ${esc(p.latest_version)}</span>` : '';
        const srcBadge   = p.source === 'lockfile'
          ? `<span style="font-size:10px;font-family:'IBM Plex Mono',monospace;color:#6E7CFF">lockfile</span>`
          : `<span style="font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--text-dim)">manual</span>`;
        const depsCell   = _pvDepsCell(p);

        return `<tr>
          <td class="ta-td ta-num">${offset + i + 1}</td>
          <td class="ta-td ta-name" style="font-weight:600">${esc(p.name)}</td>
          <td class="ta-td">${_pvEcoBadge(p.ecosystem)}</td>
          <td class="ta-td">${verStr}${latestStr}</td>
          <td class="ta-td">${vulnBadges}</td>
          <td class="ta-td">${_pvSevBadge(p.highest_severity)}</td>
          <td class="ta-td" style="cursor:pointer" onclick="${p.dep_resolved_at ? `pvShowDeps('${esc(p._id)}')` : ''}">${depsCell}</td>
          <td class="ta-td">${srcBadge}</td>
          <td class="ta-td" style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${lastScan}</td>
          <td class="ta-td" style="display:flex;gap:6px;align-items:center">
            <button class="btn-reset" data-id="${esc(p._id)}"
                    style="font-size:10px;padding:4px 8px;border-color:rgba(61,201,175,0.4);color:var(--green)"
                    onclick="pvShowEditModal(this.dataset.id)" title="Edit version / ecosystem">✎</button>
            <button class="btn-reset" data-id="${esc(p._id)}" data-name="${esc(p.name)}"
                    style="font-size:10px;padding:4px 8px;border-color:rgba(47,129,247,0.4);color:var(--accent)"
                    onclick="pvScanOne(this.dataset.id, this.dataset.name, this)" title="Scan now">⟳</button>
            <button class="btn-reset" data-id="${esc(p._id)}"
                    style="font-size:10px;padding:4px 8px;border-color:rgba(110,124,255,0.4);color:#6E7CFF"
                    onclick="pvResolveDeps(this.dataset.id, this)" title="Resolve dependency graph + scorecard">⛓</button>
            <button class="ta-delete-btn" data-id="${esc(p._id)}"
                    onclick="pvDeletePackage(this.dataset.id)">✕</button>
          </td>
        </tr>`;
      }).join('');
    }
    _pvRenderPkgPager();
    pvLoadStats();
  } catch(e) {
    console.error('pv load packages error:', e);
    tbody.innerHTML = `<tr><td colspan="9" class="ta-td">${emptyHTML('Failed to load packages')}</td></tr>`;
  }
}

function _pvDepsCell(p) {
  if (!p.dep_resolved_at) {
    return `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">—</span>`;
  }
  const total = p.dep_total_count || 0;
  const direct = p.dep_direct_count || 0;
  const indirect = p.dep_indirect_count || 0;
  const depBadge = `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent3)"
    title="${direct} direct, ${indirect} indirect">${direct}+${indirect}</span>`;
  let scoreBadge = '';
  if (p.scorecard_score != null) {
    const sc = p.scorecard_score;
    const scColor = sc >= 7 ? 'var(--green)' : sc >= 4 ? 'var(--orange)' : '#DA3633';
    scoreBadge = ` <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${scColor}"
      title="OSSF Scorecard: ${sc}/10">⬡${sc}</span>`;
  }
  return `<span style="display:flex;gap:4px;align-items:center">${depBadge}${scoreBadge}</span>`;
}

function _pvVulnCountBadges(p) {
  const parts = [];
  if ((p.critical_count||0) > 0)
    parts.push(`<span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(218,54,51,0.2);color:#DA3633;font-family:'IBM Plex Mono',monospace">C:${p.critical_count}</span>`);
  if ((p.high_count||0) > 0)
    parts.push(`<span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(227,179,65,0.2);color:var(--orange);font-family:'IBM Plex Mono',monospace">H:${p.high_count}</span>`);
  if ((p.medium_count||0) > 0)
    parts.push(`<span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(88,166,255,0.15);color:var(--accent3);font-family:'IBM Plex Mono',monospace">M:${p.medium_count}</span>`);
  if ((p.low_count||0) > 0)
    parts.push(`<span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(47,129,247,0.12);color:var(--accent);font-family:'IBM Plex Mono',monospace">L:${p.low_count}</span>`);
  return parts.length
    ? `<span style="display:flex;gap:3px;flex-wrap:wrap">${parts.join('')}</span>`
    : `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">0</span>`;
}

function _pvRenderPkgPager() {
  const totalPages = Math.max(1, Math.ceil(_pvPkgState.total / _pvPkgState.pageSize));
  const el = document.getElementById('pv-pkg-pager');
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="pvPkgGoPage(-1)" ${_pvPkgState.page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${_pvPkgState.page}</strong> / ${totalPages}</span>
    <button class="pager-btn" onclick="pvPkgGoPage(1)" ${_pvPkgState.page >= totalPages ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

async function pvPkgGoPage(delta) {
  const totalPages = Math.ceil(_pvPkgState.total / _pvPkgState.pageSize);
  _pvPkgState.page = Math.min(Math.max(1, _pvPkgState.page + delta), totalPages);
  await pvLoadPackages();
}

// ── Vuln list ─────────────────────────────────────────────────

async function pvLoadVulns() {
  const tbody = document.getElementById('pv-vuln-tbody');
  tbody.innerHTML = `<tr><td colspan="10" class="ta-td">${loadingHTML()}</td></tr>`;

  try {
    const params = new URLSearchParams({
      page: _pvVulnState.page, page_size: _pvVulnState.pageSize,
      sort_by: 'adjusted_score', sort_dir: 'desc',
    });
    const search  = document.getElementById('pv-search').value.trim();
    const sev     = document.getElementById('pv-severity-filter').value;
    const pkg     = document.getElementById('pv-pkg-filter').value;
    const kevOnly    = document.getElementById('pv-kev-filter')?.checked;
    const unackedOnly = document.getElementById('pv-unacked-filter')?.checked;
    if (search)      params.set('search', search);
    if (sev)         params.set('severity', sev);
    if (pkg)         params.set('package_name', pkg);
    if (unackedOnly) params.set('acknowledged', 'false');
    if (kevOnly)     params.set('kev_only', 'true');

    const resp = await fetch(`/api/pkgvuln/vulns?${params}`, { headers: _authAndClientHeaders() });
    if (!resp.ok) throw new Error(resp.statusText);
    const d = await resp.json();

    _pvVulnState.total = d.total;
    document.getElementById('pv-vuln-count-badge').textContent = d.total;

    if (!d.items.length) {
      tbody.innerHTML = `<tr><td colspan="10" class="ta-td">${emptyHTML('No vulnerabilities found')}</td></tr>`;
    } else {
      const offset = (_pvVulnState.page - 1) * _pvVulnState.pageSize;
      tbody.innerHTML = d.items.map((v, i) => {
        const adjScore  = v.adjusted_score != null ? v.adjusted_score.toFixed(1) : (v.cvss_score != null ? v.cvss_score.toFixed(1) : '—');
        const adjSev    = v.adjusted_severity || v.severity;
        const epss      = v.epss_score != null ? (v.epss_score * 100).toFixed(1) + '%' : '—';
        const cveList   = (v.aliases || []).filter(a => a.startsWith('CVE-')).slice(0, 3).join(', ') || '';
        const kevBadge  = v.kev ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(218,54,51,0.2);color:#DA3633;border:1px solid rgba(218,54,51,0.4)">KEV</span>` : '';
        const fixedIn   = v.fixed_version
          ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--green)">${esc(v.fixed_version)}</span>`
          : '<span style="color:var(--text-dim);font-size:10px">—</span>';
        const ackBadge  = v.acknowledged
          ? `<span style="font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--green)">✓ acked</span>`
          : `<button class="btn-reset" style="font-size:10px;padding:3px 7px;border-color:rgba(227,179,65,0.4);color:var(--orange)"
                     onclick="event.stopPropagation();pvAckVuln('${esc(v._id)}',this)">Ack</button>`;

        // Score cell shows adjusted score with KEV badge
        const scoreCellColor = _cvssColor(v.adjusted_score ?? v.cvss_score);
        const scoreCell = `<span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:${scoreCellColor}">${adjScore}</span>${kevBadge ? ' ' + kevBadge : ''}`;

        return `<tr style="cursor:pointer" onclick="pvShowVulnDetail('${esc(v._id)}')">
          <td class="ta-td ta-num">${offset + i + 1}</td>
          <td class="ta-td" style="font-family:'IBM Plex Mono',monospace;font-size:11px">
            <div style="color:var(--text-bright)">${esc(v.advisory_id)}</div>
            ${cveList ? `<div style="font-size:10px;color:var(--text-dim)">${esc(cveList)}</div>` : ''}
          </td>
          <td class="ta-td">
            <div style="font-size:12px;font-weight:500">${esc(v.package_name)}</div>
            ${v.pinned_version ? `<div style="font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--text-dim)">@${esc(v.pinned_version)}</div>` : ''}
          </td>
          <td class="ta-td" style="font-size:12px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
              title="${esc(v.summary)}">${esc(v.summary || v.details?.slice(0,100) || '—')}</td>
          <td class="ta-td">${_pvSevBadge(adjSev)}</td>
          <td class="ta-td">${scoreCell}</td>
          <td class="ta-td" style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:${v.epss_score != null ? (v.epss_score >= 0.1 ? 'var(--orange)' : 'var(--text-dim)') : 'var(--text-dim)'}">${epss}</td>
          <td class="ta-td" style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${v.published || '—'}</td>
          <td class="ta-td">${fixedIn}</td>
          <td class="ta-td" onclick="event.stopPropagation()">${ackBadge}</td>
        </tr>`;
      }).join('');
    }
    _pvRenderVulnPager();
  } catch(e) {
    console.error('pv load vulns error:', e);
    tbody.innerHTML = `<tr><td colspan="10" class="ta-td">${emptyHTML('Failed to load vulnerabilities')}</td></tr>`;
  }
}

function _cvssColor(score) {
  if (score == null) return 'var(--text-dim)';
  if (score >= 9.0)  return '#DA3633';
  if (score >= 7.0)  return 'var(--orange)';
  if (score >= 4.0)  return 'var(--accent3)';
  return 'var(--accent)';
}

function _pvRenderVulnPager() {
  const totalPages = Math.max(1, Math.ceil(_pvVulnState.total / _pvVulnState.pageSize));
  const el = document.getElementById('pv-vuln-pager');
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="pvVulnGoPage(-1)" ${_pvVulnState.page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${_pvVulnState.page}</strong> / ${totalPages}</span>
    <button class="pager-btn" onclick="pvVulnGoPage(1)" ${_pvVulnState.page >= totalPages ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

async function pvVulnGoPage(delta) {
  const totalPages = Math.ceil(_pvVulnState.total / _pvVulnState.pageSize);
  _pvVulnState.page = Math.min(Math.max(1, _pvVulnState.page + delta), totalPages);
  await pvLoadVulns();
}

// ── Actions ───────────────────────────────────────────────────

function pvResetFilters() {
  document.getElementById('pv-search').value = '';
  document.getElementById('pv-severity-filter').value = '';
  document.getElementById('pv-pkg-filter').value = '';
  const kev = document.getElementById('pv-kev-filter');
  if (kev) kev.checked = false;
  const unacked = document.getElementById('pv-unacked-filter');
  if (unacked) unacked.checked = false;
  _pvVulnState.page = 1;
  pvLoadVulns();
}

async function pvAddPackage() {
  try {
    const nameEl = document.getElementById('pv-pkg-input');
    const verEl  = document.getElementById('pv-ver-input');
    const ecoEl  = document.getElementById('pv-eco-select');
    if (!nameEl || !verEl || !ecoEl) { console.error('[pvAddPackage] input elements missing'); return; }

    const name = nameEl.value.trim();
    const ver  = verEl.value.trim() || undefined;
    const eco  = ecoEl.value;
    if (!name) { _pvStatus('Enter package name', false); return; }

    _pvStatus('Validating…', true);
    const resp = await fetch('/api/pkgvuln/packages', {
      method: 'POST',
      headers: _authAndClientHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ name, ecosystem: eco, version: ver || null }),
    });
    if (resp.status === 401) { _authFailed(); return; }
    const d = await resp.json();
    if (resp.ok && d.success) {
      nameEl.value = '';
      verEl.value  = '';
      const verLabel = ver ? `@${ver}` : '';
      _pvStatus(`"${name}${verLabel}" added — scanning…`, true);
      _pvPkgState.page = 1;
      pvLoadPackages();
    } else {
      _pvStatus(d.detail || 'Cannot add: already exists', false);
    }
  } catch(e) {
    _pvStatus(`Error: ${e.message}`, false);
    console.error('[pvAddPackage]', e);
  }
}

function pvDeletePackage(pkgId) {
  const p = _pvPkgMap[pkgId];
  if (!p) return;
  showConfirmModal({
    title:   'Remove Package',
    okLabel: '✕ Remove',
    body: `<p style="font-size:13px;color:var(--text);line-height:1.7;margin-bottom:10px">
      Remove <strong style="color:var(--red)">${esc(p.name)}</strong> (${esc(p.ecosystem)}) from monitoring?
    </p>
    <p style="font-size:12px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;line-height:1.7">
      All vulnerability records for this package will be deleted.
    </p>`,
    onConfirm: async () => {
      try {
        const resp = await fetch(`/api/pkgvuln/packages/${encodeURIComponent(pkgId)}`, {
          method: 'DELETE', headers: _authAndClientHeaders(),
        });
        if (resp.status === 401) { _authFailed(); return; }
        const d = await resp.json();
        if (d.success) {
          _pvStatus(`"${p.name}" removed`, true);
          pvLoadPackages();
        }
      } catch(e) {
        _pvStatus('Failed to remove package', false);
      }
    },
  });
}

async function pvScanOne(pkgId, pkgName, btn) {
  btn.disabled = true;
  btn.textContent = '⏳';
  try {
    const resp = await fetch(`/api/pkgvuln/packages/${encodeURIComponent(pkgId)}/scan`, {
      method: 'POST', headers: _authAndClientHeaders(),
    });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) throw new Error(resp.statusText);
    _pvStatus(`Scanning "${pkgName}"…`, true);
    setTimeout(() => { pvLoadPackages(); pvLoadStats(); }, 4000);
  } catch(e) {
    _pvStatus(`Scan failed: ${e.message}`, false);
  } finally {
    btn.disabled = false;
    btn.textContent = '⟳';
  }
}

async function pvScanAll(btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = '⏳ Scanning…';
  try {
    const resp = await fetch('/api/pkgvuln/scan', {
      method: 'POST', headers: _authAndClientHeaders(),
    });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) throw new Error(resp.statusText);
    _pvStatus('Scan started — results update in ~30s', true);
    setTimeout(() => { pvLoadPackages(); pvLoadStats(); pvLoadVulns(); }, 30000);
  } catch(e) {
    _pvStatus(`Scan failed: ${e.message}`, false);
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

async function pvAckVuln(vulnId, btn) {
  btn.disabled = true;
  try {
    const resp = await fetch(`/api/pkgvuln/vulns/${encodeURIComponent(vulnId)}/ack`, {
      method: 'PATCH', headers: _authAndClientHeaders(),
    });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) throw new Error(resp.statusText);
    const d = await resp.json();
    if (d.acknowledged) {
      btn.outerHTML = `<span style="font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--green)">✓ acked</span>`;
    }
    pvLoadStats();
  } catch(e) {
    _pvStatus('Acknowledge failed', false);
    btn.disabled = false;
  }
}

// ── Lockfile import ───────────────────────────────────────────

async function pvImportLockfile(input) {
  const file = input.files[0];
  if (!file) return;
  input.value = '';  // reset so same file can be re-uploaded

  _pvStatus(`Importing ${file.name}…`, true);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch('/api/pkgvuln/import-lockfile', {
      method: 'POST',
      headers: _authAndClientHeaders(),  // no Content-Type — browser sets multipart boundary
      body: formData,
    });
    if (resp.status === 401) { _authFailed(); return; }
    const d = await resp.json();

    if (!resp.ok) {
      _pvStatus(`Import failed: ${d.detail || resp.statusText}`, false);
      return;
    }

    // Show result modal
    const pkgRows = (d.packages || []).slice(0, 20).map(p =>
      `<tr>
        <td style="padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:11px">${esc(p.name)}</td>
        <td style="padding:3px 8px">${_pvEcoBadge(p.ecosystem)}</td>
        <td style="padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${p.version ? esc(p.version) : '—'}</td>
      </tr>`
    ).join('');
    const moreRow = (d.added > 20)
      ? `<tr><td colspan="3" style="padding:4px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">…and ${d.added - 20} more</td></tr>`
      : '';
    const errSection = (d.errors || []).length
      ? `<div style="margin-top:12px"><div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);margin-bottom:4px">ERRORS</div>
         <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--red)">${d.errors.slice(0,5).map(e => esc(e)).join('<br>')}</div></div>` : '';

    document.getElementById('pv-import-modal-body').innerHTML = `
      <div style="font-family:'Share Tech Mono',monospace;font-size:16px;color:var(--text-bright);margin-bottom:14px">
        Import: ${esc(file.name)}
      </div>
      <div style="display:flex;gap:16px;margin-bottom:14px;flex-wrap:wrap">
        <div><div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase">Parsed</div>
          <div style="font-family:'Share Tech Mono',monospace;font-size:22px;color:var(--text-bright)">${d.parsed}</div></div>
        <div><div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase">Added</div>
          <div style="font-family:'Share Tech Mono',monospace;font-size:22px;color:var(--green)">${d.added}</div></div>
        <div><div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase">Skipped</div>
          <div style="font-family:'Share Tech Mono',monospace;font-size:22px;color:var(--text-dim)">${d.skipped}</div></div>
      </div>
      ${d.added > 0 ? `<div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);margin-bottom:6px">Scanning in background…</div>
      <table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Package</th>
          <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Ecosystem</th>
          <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Version</th>
        </tr></thead>
        <tbody>${pkgRows}${moreRow}</tbody>
      </table>` : '<div style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;color:var(--text-dim)">No new packages detected.</div>'}
      ${errSection}
    `;
    document.getElementById('pv-import-modal').classList.add('open');

    if (d.added > 0) {
      _pvPkgState.page = 1;
      pvLoadPackages();
      setTimeout(() => pvLoadStats(), 5000);
    }
  } catch(e) {
    _pvStatus(`Import failed: ${e.message}`, false);
  }
}

// ── Detail modal ──────────────────────────────────────────────

async function pvShowVulnDetail(vulnId) {
  // Fetch vuln record to get CVE aliases
  try {
    const params = new URLSearchParams({ search: vulnId, page: 1, page_size: 1 });
    const resp = await fetch(`/api/pkgvuln/vulns?${params}`, { headers: _authAndClientHeaders() });
    const d = resp.ok ? await resp.json() : { items: [] };
    const v = d.items[0];
    if (!v) { _pvStatus('Vulnerability not found', false); return; }

    // Try to open in Tech Stack CVE modal
    const cveAlias = (v.aliases || []).find(a => a.startsWith('CVE-'));
    if (cveAlias) {
      // Check if already in CVE data map
      if (typeof _cveDataMap !== 'undefined' && _cveDataMap[cveAlias]) {
        openCveModal(cveAlias);
        return;
      }
      // Fetch from CVE API
      const cveResp = await fetch(`/api/cve?search=${encodeURIComponent(cveAlias)}&page_size=1`, {
        headers: _authAndClientHeaders(),
      });
      if (cveResp.ok) {
        const cveData = await cveResp.json();
        const matched = (cveData.cves || []).find(c => c.cve_id === cveAlias);
        if (matched) {
          if (typeof _cveDataMap !== 'undefined') _cveDataMap[cveAlias] = matched;
          openCveModal(cveAlias);
          return;
        }
      }
    }

    // Fallback: show in pv-modal (advisory has no matching CVE in Tech Stack)
    _pvShowVulnFallback(v);
  } catch(e) {
    _pvStatus('Failed to load details', false);
  }
}

function _pvShowVulnFallback(v) {
  const modal = document.getElementById('pv-modal');
  const body  = document.getElementById('pv-modal-body');

  const aliases  = (v.aliases || []).join(', ') || '—';
  const ranges   = (v.affected_version_ranges || []).join('<br>') || '—';
  const refs     = (v.references || []).map(u => `<a href="${esc(u)}" target="_blank" rel="noopener" class="cve-ref-link">${esc(u)}</a>`).join('<br>') || '—';
  const cvss     = v.cvss_score != null ? v.cvss_score.toFixed(1) : '—';
  const adjScore = v.adjusted_score != null ? v.adjusted_score.toFixed(1) : cvss;
  const adjSev   = v.adjusted_severity || v.severity;
  const epss     = v.epss_score != null ? `${(v.epss_score * 100).toFixed(2)}% (${v.epss_percentile != null ? (v.epss_percentile * 100).toFixed(0) + 'th pct' : ''})` : 'Not available';

  body.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <div>
        <div style="font-family:'Share Tech Mono',monospace;font-size:15px;color:var(--text-bright)">${esc(v.advisory_id)}</div>
        <div style="font-size:11px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;margin-top:3px">
          ${esc(v.package_name)} · ${esc(v.ecosystem)}${v.pinned_version ? ` · @${esc(v.pinned_version)}` : ''}
        </div>
      </div>
      <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        ${_pvSevBadge(adjSev)}
        ${v.kev ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(218,54,51,0.2);color:#DA3633;border:1px solid rgba(218,54,51,0.4)">KEV</span>` : ''}
        ${adjScore !== '—' ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:${_cvssColor(v.adjusted_score ?? v.cvss_score)}">${adjScore}</span>` : ''}
      </div>
    </div>
    ${v.acknowledged ? `<div style="padding:6px 10px;background:rgba(61,201,175,0.08);border:1px solid rgba(61,201,175,0.3);border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--green);margin-bottom:10px">✓ Acked${v.ack_by ? ` by ${v.ack_by}` : ''}${v.ack_date ? ` · ${v.ack_date.slice(0,10)}` : ''}</div>` : ''}
    <div class="cve-detail-section">
      <div class="cve-detail-label">Summary</div>
      <div class="cve-detail-value" style="font-size:11px">${esc(v.summary || '—')}</div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">Description</div>
      <div class="cve-detail-value" style="max-height:120px;overflow-y:auto;white-space:pre-wrap;font-size:11px">${esc(v.details || '—')}</div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">Aliases / CVEs</div>
      <div class="cve-detail-value" style="font-size:11px">${esc(aliases)}</div>
    </div>
    <div class="cve-detail-section" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
      <div>
        <div class="cve-detail-label">CVSS</div>
        <div class="cve-detail-value" style="color:${_cvssColor(v.cvss_score)};font-size:11px">${cvss}</div>
      </div>
      <div>
        <div class="cve-detail-label">EPSS</div>
        <div class="cve-detail-value" style="color:${v.epss_score != null && v.epss_score >= 0.1 ? 'var(--orange)' : 'var(--text-dim)'};font-size:11px">${epss}</div>
      </div>
      <div>
        <div class="cve-detail-label">Composite</div>
        <div class="cve-detail-value" style="color:${_cvssColor(v.adjusted_score ?? v.cvss_score)};font-size:11px">${adjScore}${v.kev ? ' (KEV×1.5)' : ''}</div>
      </div>
    </div>
    <div class="cve-detail-section" style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px">
      <div>
        <div class="cve-detail-label">Published</div>
        <div class="cve-detail-value" style="font-size:10px">${v.published || '—'}</div>
      </div>
      <div>
        <div class="cve-detail-label">Modified</div>
        <div class="cve-detail-value" style="font-size:10px">${v.modified || '—'}</div>
      </div>
      <div>
        <div class="cve-detail-label">Fixed In</div>
        <div class="cve-detail-value" style="color:${v.fixed_version ? 'var(--green)' : 'var(--text-dim)'};font-size:10px">${v.fixed_version || 'No fix'}</div>
      </div>
      <div>
        <div class="cve-detail-label">Source</div>
        <div class="cve-detail-value" style="font-size:10px">${esc(v.source || 'osv.dev')}</div>
      </div>
    </div>
    <div class="cve-detail-section">
      <div class="cve-detail-label">Affected Ranges</div>
      <div class="cve-detail-value" style="font-family:'IBM Plex Mono',monospace;font-size:10px">${ranges}</div>
    </div>
    <div class="cve-detail-section" style="border-bottom:none">
      <div class="cve-detail-label">References</div>
      <div class="cve-detail-value" style="font-size:10px;line-height:1.6">${refs}</div>
    </div>
  `;
  modal.classList.add('open');
}

function pvCloseModal() {
  document.getElementById('pv-modal').classList.remove('open');
}

// ── Dependency graph ──────────────────────────────────────────

async function pvResolveDeps(pkgId, btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = '⏳';
  try {
    const resp = await fetch(`/api/pkgvuln/packages/${encodeURIComponent(pkgId)}/resolve-deps`, {
      method: 'POST', headers: _authAndClientHeaders(),
    });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) {
      const d = await resp.json();
      _pvStatus(`Resolve failed: ${d.detail || resp.statusText}`, false);
      return;
    }
    _pvStatus('Resolving deps + scorecard…', true);
    setTimeout(() => pvLoadPackages(), 8000);
  } catch(e) {
    _pvStatus(`Resolve failed: ${e.message}`, false);
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

async function pvShowDeps(pkgId) {
  const modal = document.getElementById('pv-deps-modal');
  const body  = document.getElementById('pv-deps-modal-body');
  body.innerHTML = loadingHTML();
  modal.classList.add('open');

  try {
    const resp = await fetch(`/api/pkgvuln/packages/${encodeURIComponent(pkgId)}/deps`, {
      headers: _authAndClientHeaders(),
    });
    if (!resp.ok) {
      const d = await resp.json();
      body.innerHTML = `<p style="color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:12px">${esc(d.detail || 'Failed to load')}</p>`;
      return;
    }
    const g = await resp.json();
    const pkg = _pvPkgMap[pkgId] || {};

    // Scorecard section
    const scSection = g.scorecard_score != null ? (() => {
      const sc  = g.scorecard_score;
      const scColor = sc >= 7 ? 'var(--green)' : sc >= 4 ? 'var(--orange)' : '#DA3633';
      const checksHtml = (g.scorecard_checks || []).map(c => {
        const chColor = (c.score == null ? 'var(--text-dim)' : c.score >= 7 ? 'var(--green)' : c.score >= 4 ? 'var(--orange)' : '#DA3633');
        return `<tr>
          <td style="padding:4px 8px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text)">${esc(c.name)}</td>
          <td style="padding:4px 8px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:${chColor};text-align:center">${c.score ?? '—'}</td>
          <td style="padding:4px 8px;font-size:11px;color:var(--text-dim)">${esc(c.reason || '')}</td>
        </tr>`;
      }).join('');
      return `
        <div style="margin-bottom:18px;padding:12px;background:rgba(47,129,247,0.06);border:1px solid var(--border);border-radius:4px">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dim);text-transform:uppercase">OSSF Scorecard</span>
            <span style="font-family:'Share Tech Mono',monospace;font-size:22px;color:${scColor}">${sc} / 10</span>
            ${g.scorecard_date ? `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${esc(g.scorecard_date)}</span>` : ''}
            ${g.scorecard_project ? `<a href="https://${esc(g.scorecard_project)}" target="_blank" rel="noopener" style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">${esc(g.scorecard_project)}</a>` : ''}
          </div>
          ${checksHtml ? `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-bottom:6px">LOWEST SCORING CHECKS</div>
          <table style="width:100%;border-collapse:collapse"><thead><tr>
            <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Check</th>
            <th style="text-align:center;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Score</th>
            <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Reason</th>
          </tr></thead><tbody>${checksHtml}</tbody></table>` : ''}
        </div>`;
    })() : '';

    // Dep tabs
    let _pvDepTab = 'direct';
    const directRows = (g.direct_deps || []).map(d =>
      `<tr>
        <td style="padding:4px 8px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright)">${esc(d.name)}</td>
        <td style="padding:4px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${esc(d.version || '—')}</td>
        <td style="padding:4px 8px">${_pvEcoBadge(_DEPSDEV_SYSTEM_TO_ECO[d.system] || d.system || '')}</td>
      </tr>`
    ).join('') || `<tr><td colspan="3" style="padding:8px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dim)">No direct dependencies</td></tr>`;

    const indirectRows = (g.indirect_deps || []).map(d =>
      `<tr>
        <td style="padding:4px 8px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text)">${esc(d.name)}</td>
        <td style="padding:4px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">${esc(d.version || '—')}</td>
        <td style="padding:4px 8px">${_pvEcoBadge(_DEPSDEV_SYSTEM_TO_ECO[d.system] || d.system || '')}</td>
      </tr>`
    ).join('') || `<tr><td colspan="3" style="padding:8px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dim)">No indirect dependencies</td></tr>`;

    const depTableHtml = (rows) => `
      <table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Package</th>
          <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Version</th>
          <th style="text-align:left;padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);border-bottom:1px solid var(--border)">Ecosystem</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;

    const resolvedAt = g.resolved_at ? g.resolved_at.slice(0, 16).replace('T', ' ') : '—';
    const errBanner  = g.error ? `<div style="padding:8px 12px;background:rgba(218,54,51,0.08);border:1px solid rgba(218,54,51,0.3);border-radius:4px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--red);margin-bottom:12px">${esc(g.error)}</div>` : '';

    body.innerHTML = `
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:16px;flex-wrap:wrap">
        <div>
          <div style="font-family:'Share Tech Mono',monospace;font-size:18px;color:var(--text-bright)">${esc(g.package_name)}</div>
          <div style="font-size:12px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;margin-top:4px">
            ${esc(g.ecosystem)}${g.version ? ` · @${esc(g.version)}` : ''} · resolved ${resolvedAt}
          </div>
        </div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <div style="text-align:center">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase">Direct</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:20px;color:var(--accent3)">${g.direct_count}</div>
          </div>
          <div style="text-align:center">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase">Indirect</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:20px;color:var(--text-dim)">${g.indirect_count}</div>
          </div>
          <div style="text-align:center">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);text-transform:uppercase">Total</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:20px;color:var(--text)">${g.total_count}</div>
          </div>
        </div>
      </div>
      ${errBanner}
      ${scSection}
      <div style="display:flex;gap:6px;margin-bottom:10px;align-items:center">
        <button id="pv-dep-tab-direct" class="ta-submenu-btn active" style="font-size:11px;padding:4px 10px"
                onclick="pvDepSwitchTab('direct')">Direct <span style="font-family:'IBM Plex Mono',monospace;font-size:10px">(${g.direct_count})</span></button>
        <button id="pv-dep-tab-indirect" class="ta-submenu-btn" style="font-size:11px;padding:4px 10px"
                onclick="pvDepSwitchTab('indirect')">Indirect <span style="font-family:'IBM Plex Mono',monospace;font-size:10px">(${g.indirect_count}${g.indirect_count >= 200 ? '+' : ''})</span></button>
        <button class="btn-reset" style="margin-left:auto;font-size:10px;padding:4px 10px;border-color:rgba(110,124,255,0.4);color:#6E7CFF"
                onclick="pvResolveDepsFromModal('${esc(pkgId)}', true, this)"
                title="Also scan all transitive dependencies for vulnerabilities">⟳ Re-resolve + Scan Transitive</button>
      </div>
      <div id="pv-dep-view-direct">${depTableHtml(directRows)}</div>
      <div id="pv-dep-view-indirect" style="display:none">${depTableHtml(indirectRows)}</div>
    `;
  } catch(e) {
    body.innerHTML = `<p style="color:var(--text-dim)">Failed to load dependency graph.</p>`;
  }
}

const _DEPSDEV_SYSTEM_TO_ECO = {
  NPM: 'npm', PYPI: 'PyPI', GO: 'Go', MAVEN: 'Maven',
  CARGO: 'crates.io', NUGET: 'NuGet', RUBYGEMS: 'RubyGems',
};

function pvDepSwitchTab(tab) {
  document.getElementById('pv-dep-view-direct').style.display   = tab === 'direct'   ? '' : 'none';
  document.getElementById('pv-dep-view-indirect').style.display = tab === 'indirect' ? '' : 'none';
  document.getElementById('pv-dep-tab-direct').classList.toggle('active',   tab === 'direct');
  document.getElementById('pv-dep-tab-indirect').classList.toggle('active', tab === 'indirect');
}

async function pvResolveDepsFromModal(pkgId, scanTransitive, btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = '⏳';
  try {
    const url = `/api/pkgvuln/packages/${encodeURIComponent(pkgId)}/resolve-deps${scanTransitive ? '?scan_transitive=true' : ''}`;
    const resp = await fetch(url, { method: 'POST', headers: _authAndClientHeaders() });
    if (resp.status === 401) { _authFailed(); return; }
    if (!resp.ok) {
      const d = await resp.json();
      _pvStatus(`Resolve failed: ${d.detail || resp.statusText}`, false);
      return;
    }
    _pvStatus(scanTransitive ? 'Resolving + scanning transitive deps…' : 'Re-resolving…', true);
    pvCloseDepsModal();
    setTimeout(() => pvLoadPackages(), 10000);
  } catch(e) {
    _pvStatus(`Resolve failed: ${e.message}`, false);
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

function pvCloseDepsModal() {
  document.getElementById('pv-deps-modal').classList.remove('open');
}

// ── Edit package modal ───────────────────────────────────

function pvShowEditModal(pkgId) {
  const p = _pvPkgMap[pkgId];
  if (!p) return;
  const ecoOptions = ['npm','PyPI','Go','Maven','crates.io','NuGet','RubyGems','Packagist','Hex']
    .map(e => `<option value="${e}" ${e === p.ecosystem ? 'selected' : ''}>${e}</option>`).join('');

  document.getElementById('pv-edit-modal-body').innerHTML = `
    <div style="font-family:'Share Tech Mono',monospace;font-size:16px;color:var(--text-bright);margin-bottom:16px">
      Edit: ${esc(p.name)}
    </div>
    <div style="margin-bottom:14px">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;margin-bottom:4px">Version</div>
      <input type="text" class="filter-input" id="pv-edit-version" value="${esc(p.version || '')}"
             placeholder="e.g. 1.2.3 (leave blank for latest)" style="width:100%">
    </div>
    <div style="margin-bottom:18px">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;margin-bottom:4px">Ecosystem</div>
      <select class="filter-select" id="pv-edit-ecosystem" style="width:100%">${ecoOptions}</select>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button class="btn-reset" onclick="pvCloseEditModal()">Cancel</button>
      <button class="btn-apply" onclick="pvSaveEdit('${esc(pkgId)}')">Save</button>
    </div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);margin-top:12px">
      Changing version or ecosystem triggers a re-scan.
    </div>
  `;
  document.getElementById('pv-edit-modal').classList.add('open');
}

function pvCloseEditModal() {
  document.getElementById('pv-edit-modal').classList.remove('open');
}

async function pvSaveEdit(pkgId) {
  const version   = document.getElementById('pv-edit-version').value.trim() || null;
  const ecosystem = document.getElementById('pv-edit-ecosystem').value;
  try {
    const resp = await fetch(`/api/pkgvuln/packages/${encodeURIComponent(pkgId)}`, {
      method: 'PATCH',
      headers: _authAndClientHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ version, ecosystem }),
    });
    if (resp.status === 401) { _authFailed(); return; }
    const d = await resp.json();
    if (resp.ok && d.success) {
      pvCloseEditModal();
      _pvStatus(d.changed ? 'Package updated — re-scanning…' : 'No changes', true);
      if (d.changed) pvLoadPackages();
    } else {
      _pvStatus(d.detail || 'Update failed', false);
    }
  } catch(e) {
    _pvStatus(`Error: ${e.message}`, false);
  }
}

// ── Entry point ───────────────────────────────────────────────

async function loadPkgVulnPanel() {
  await pvLoadStats();
  if (_pvSubview === 'vulns') {
    document.getElementById('pv-stats-grid').style.display = '';
    document.getElementById('pv-filter-bar').style.display = '';
    await pvLoadVulns();
  } else {
    await pvLoadPackages();
  }
}
