// ── TTP DRILL-DOWN ────────────────────────────────────────────
let _ttpDrillState = { ttpId: '', ttpName: '', row: '', view: 'ta', days: 90, page: 1, total: 0, pageSize: 20 };

function openTtpDrill(ttpId, ttpName, row, view, days) {
  _ttpDrillState = { ttpId, ttpName, row, view, days, page: 1, total: 0, pageSize: 20 };
  document.getElementById('ttp-drill-title').textContent = `${ttpId} — ${ttpName}`;
  const label = view === 'ta' ? 'Threat Actor' : 'Industry';
  const sub = document.getElementById('ttp-drill-subtitle');
  sub.innerHTML = `<span>${esc(label)}: ${esc(row)}</span><button class="d3fend-btn" onclick="loadD3fendDrill('${ttpId}')">🛡 D3FEND</button>`;
  const d3fPanel = document.getElementById('ttp-drill-d3fend');
  d3fPanel.style.display = 'none';
  d3fPanel.innerHTML = '';
  document.getElementById('ttp-drill-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  _loadTtpDrillPage(1);
}

function closeTtpDrill() {
  document.getElementById('ttp-drill-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

// ── D3FEND COUNTERMEASURES ─────────────────────────────────────
const _d3fCache = {};

async function _fetchD3fend(ttpId) {
  if (Object.prototype.hasOwnProperty.call(_d3fCache, ttpId)) return _d3fCache[ttpId];
  const res = await fetch(`/api/mitre/d3fend/${encodeURIComponent(ttpId)}`, { headers: _authHeader() });
  const d = await res.json();
  _d3fCache[ttpId] = d.countermeasures || [];
  return _d3fCache[ttpId];
}

function _renderD3fend(measures, container) {
  if (!measures.length) {
    container.innerHTML = '<span style="color:var(--text-dim)">No D3FEND countermeasures mapped for this technique.</span>';
    return;
  }
  const header = '<div style="text-transform:uppercase;letter-spacing:0.08em;font-size:9px;color:var(--text-dim);margin-bottom:5px">D3FEND Countermeasures</div>';
  const pills = measures.map(m =>
    `<a class="d3fend-pill" href="${esc(m.url)}" target="_blank" rel="noopener" title="${esc(m.artifact || '')}">${esc(m.name)}</a>`
  ).join('');
  container.innerHTML = header + pills;
}

async function toggleD3fend(ttpId) {
  const row = document.getElementById(`d3frow-${ttpId}`);
  const panel = document.getElementById(`d3fpanel-${ttpId}`);
  if (!row || !panel) return;
  if (row.style.display !== 'none') { row.style.display = 'none'; return; }
  row.style.display = '';
  panel.innerHTML = '<span style="color:var(--text-dim)">Loading…</span>';
  const measures = await _fetchD3fend(ttpId);
  _renderD3fend(measures, panel);
}

async function loadD3fendDrill(ttpId) {
  const panel = document.getElementById('ttp-drill-d3fend');
  if (!panel) return;
  if (panel.style.display !== 'none') { panel.style.display = 'none'; return; }
  panel.style.display = '';
  panel.innerHTML = '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:var(--text-dim)">Loading…</span>';
  const measures = await _fetchD3fend(ttpId);
  panel.classList.add('d3fend-panel');
  _renderD3fend(measures, panel);
}

async function _loadTtpDrillPage(page) {
  const s = _ttpDrillState;
  s.page = page;
  const body = document.getElementById('ttp-drill-body');
  body.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Loading…</div>';

  const params = new URLSearchParams({
    ttp_id: s.ttpId, row: s.row, view: s.view,
    days: s.days, page, page_size: s.pageSize,
  });
  try {
    const resp = await fetch(`/api/mitre/articles?${params}`, { headers: _authHeader() });
    const d = await resp.json();
    s.total = d.total;

    if (!d.articles.length) {
      body.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px">No articles found.</div>';
      document.getElementById('ttp-drill-count').textContent = '';
      return;
    }

    body.innerHTML = d.articles.map(a => `
      <div style="padding:12px 20px;border-bottom:1px solid var(--border);cursor:pointer"
           onmouseenter="this.style.background='var(--surface2)'" onmouseleave="this.style.background=''"
           onclick="window.open('${esc(a.url)}','_blank')">
        <div style="font-size:12px;color:var(--text);line-height:1.5;margin-bottom:4px">${esc(a.title)}</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)">
          ${esc(a.posted_on)} &nbsp;·&nbsp; ${esc(a.source)}
        </div>
      </div>`).join('');

    const totalPages = Math.ceil(d.total / s.pageSize);
    document.getElementById('ttp-drill-count').textContent = `${d.total} article${d.total !== 1 ? 's' : ''}`;

    const foot = document.getElementById('ttp-drill-foot');
    const existing = foot.querySelector('.ttp-page-nav');
    if (existing) existing.remove();
    if (totalPages > 1) {
      const nav = document.createElement('div');
      nav.className = 'ttp-page-nav';
      nav.style.cssText = 'display:flex;gap:6px;align-items:center';
      if (page > 1) {
        const prev = document.createElement('button');
        prev.className = 'btn-close-modal';
        prev.textContent = '← Prev';
        prev.onclick = () => _loadTtpDrillPage(page - 1);
        nav.appendChild(prev);
      }
      const info = document.createElement('span');
      info.style.cssText = "font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim)";
      info.textContent = `${page} / ${totalPages}`;
      nav.appendChild(info);
      if (page < totalPages) {
        const next = document.createElement('button');
        next.className = 'btn-close-modal';
        next.textContent = 'Next →';
        next.onclick = () => _loadTtpDrillPage(page + 1);
        nav.appendChild(next);
      }
      foot.insertBefore(nav, foot.firstChild);
    }
  } catch (e) {
    body.innerHTML = '<div style="padding:24px;text-align:center;color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Failed to load articles.</div>';
    console.error('TTP drill error:', e);
  }
}

