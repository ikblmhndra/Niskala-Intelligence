// ── MODAL ─────────────────────────────────────────────────
const TYPE_COLORS = {
  apac:       '#2F81F7',
  global:     '#58A6FF',
  ransomware: '#DA3633',
  indonesia:  '#3DC9AF',
};

function openModal(key) {
  const a = _cache[key];
  if (!a) return;

  // Dot color
  const color = TYPE_COLORS[a.news_type] || '#8B949E';
  document.getElementById('modal-type-dot').style.background = color;
  document.getElementById('modal-type-dot').style.boxShadow = `0 0 6px ${color}`;

  // Title
  document.getElementById('modal-title').textContent = a.title;

  // Meta bar — inject Admiralty badge if source is scored
  const srEntry = _srScoreMap[a.source?.toLowerCase()];
  const admiraltyBadge = srEntry
    ? `<span class="admiral-grade admiral-${esc(srEntry.reliability_grade)}"
           style="font-size:11px;padding:1px 7px;border-radius:2px;margin-left:6px"
           title="Admiralty ${esc(srEntry.admiralty_code)} — Reliability: ${esc(srEntry.reliability_grade)}, Credibility: ${esc(srEntry.credibility_code)}"
         >${esc(srEntry.admiralty_code)}</span>`
    : '';

  document.getElementById('modal-meta-bar').innerHTML = `
    <div class="modal-meta-item">
      <span class="label">Source</span>
      <span class="value">${esc(a.source)}${admiraltyBadge}</span>
    </div>
    <div class="modal-meta-item"><span class="label">Published</span><span class="value">${esc(a.posted_on)}</span></div>
    <div class="modal-meta-item"><span class="label">Type</span><span class="value">${esc(a.news_type)}</span></div>
  `;

  // Body sections
  let html = '';

  // Industries
  const industries = a.impacted_industries || [];
  html += `<div>
    <div class="modal-section-label">Impacted Industries</div>
    <div class="modal-tags">
      ${industries.length
        ? industries.map(i => `<span class="modal-tag yellow">${esc(i)}</span>`).join('')
        : '<span class="modal-tag">—</span>'}
    </div>
  </div>`;

  // Countries — split by role when available
  const victimCtys  = a.victim_countries || [];
  const actorCtys   = a.actor_countries  || [];
  const mentionCtys = a.mentioned_countries || [];
  const hasRoles = victimCtys.length || actorCtys.length;
  html += `<div>
    <div class="modal-section-label">Countries</div>
    <div class="modal-tags">
      ${hasRoles ? [
          ...victimCtys.map(c => `<span class="modal-tag accent" title="Victim / Targeted">${esc(c)} <span style="font-size:9px;opacity:.7;">VICTIM</span></span>`),
          ...actorCtys.map(c => `<span class="modal-tag red" title="Actor Origin / Attribution">${esc(c)} <span style="font-size:9px;opacity:.7;">ORIGIN</span></span>`),
        ].join('') || '<span class="modal-tag">—</span>'
        : mentionCtys.length
          ? mentionCtys.map(c => `<span class="modal-tag accent">${esc(c)}</span>`).join('')
          : '<span class="modal-tag">—</span>'}
    </div>
  </div>`;

  // Threat Actors
  const actors = a.threat_actors || [];
  html += `<div>
    <div class="modal-section-label">Threat Actors</div>
    <div class="modal-tags">
      ${actors.length
        ? actors.map(t => `<span class="modal-tag red">${esc(t)}</span>`).join('')
        : '<span class="modal-tag">—</span>'}
    </div>
  </div>`;

  // TTPs
  const ttps = a.ttps || [];
  if (ttps.length) {
    html += `<div>
      <div class="modal-section-label">MITRE ATT&amp;CK TTPs</div>
      <table class="ttp-table">
        <thead><tr><th>Technique ID</th><th>Name</th><th style="width:96px">D3FEND</th></tr></thead>
        <tbody>
          ${ttps.map(t => `<tr>
            <td><span class="ttp-id">${esc(t.id)}</span></td>
            <td class="ttp-name">${esc(t.name)}</td>
            <td><button class="d3fend-btn" onclick="toggleD3fend('${esc(t.id)}')">🛡 Defenses</button></td>
          </tr>
          <tr id="d3frow-${esc(t.id)}" style="display:none">
            <td colspan="3" style="padding:2px 10px 8px"><div class="d3fend-panel" id="d3fpanel-${esc(t.id)}"></div></td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
  } else {
    html += `<div>
      <div class="modal-section-label">MITRE ATT&amp;CK TTPs</div>
      <div class="modal-tags"><span class="modal-tag">No TTPs recorded</span></div>
    </div>`;
  }

  // IOCs
  const iocs = a.iocs || {};
  const _iocFieldLabel = { ips:'IP', domains:'Domain', urls:'URL', urls_with_path:'URL+Path', emails:'Email', sha256:'SHA256', sha1:'SHA1', md5:'MD5', cves:'CVE' };
  const iocEntries = Object.entries(iocs).filter(([,v]) => v && v.length);
  if (iocEntries.length) {
    html += `<div>
      <div class="modal-section-label">Indicators of Compromise</div>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${iocEntries.map(([field, vals]) => `
          <div style="display:flex;gap:8px;align-items:flex-start">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 6px;border-radius:2px;background:rgba(227,179,65,0.1);border:1px solid rgba(227,179,65,0.3);color:var(--orange);white-space:nowrap;margin-top:1px">${_iocFieldLabel[field]||field.toUpperCase()}</span>
            <div style="display:flex;flex-wrap:wrap;gap:4px">
              ${vals.map(v => `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-bright);background:rgba(255,255,255,0.04);border:1px solid var(--border);padding:1px 6px;border-radius:2px">${esc(v)}</span>`).join('')}
            </div>
          </div>`).join('')}
      </div>
    </div>`;
  }

  document.getElementById('modal-body').innerHTML = html;
  document.getElementById('modal-article-link').href = a.url;
  document.getElementById('modal-ioc-export-btn').style.display = iocEntries.length ? '' : 'none';
  window._modalArticle = a;

  // Show
  document.getElementById('modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function exportArticleIocsCsv() {
  const a = window._modalArticle;
  if (!a || !a.iocs) return;
  const _fieldToType = { ips:'ip', domains:'domain', urls:'url', urls_with_path:'url_with_path', emails:'email', sha256:'sha256', sha1:'sha1', md5:'md5', cves:'cve' };
  const rows = [['type','value','article_title','article_url','article_source','article_date']];
  for (const [field, vals] of Object.entries(a.iocs)) {
    const type = _fieldToType[field] || field;
    for (const v of (vals || [])) {
      rows.push([type, v, a.title || '', a.url || '', a.source || '', a.posted_on || ''].map(cell => `"${String(cell).replace(/"/g,'""')}"`));
    }
  }
  const csv = rows.map(r => r.join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href     = url;
  link.download = `iocs_${(a.title||'article').slice(0,40).replace(/[^a-z0-9]/gi,'_')}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function queueForNewsletter() {
  const a = window._modalArticle;
  if (!a) return;
  const queue = JSON.parse(localStorage.getItem('newsletter_queue') || '[]');
  const articleId = a._id || a.id || null;
  if (articleId && queue.find(x => (x._id || x.id) === articleId)) {
    // already queued — show feedback
    const btn = document.getElementById('modal-newsletter-btn');
    btn.textContent = '✓ Already queued';
    setTimeout(() => { btn.textContent = '+ Newsletter'; }, 1500);
    return;
  }
  queue.push(a);
  localStorage.setItem('newsletter_queue', JSON.stringify(queue));
  const btn = document.getElementById('modal-newsletter-btn');
  btn.textContent = `✓ Queued (${queue.length})`;
  setTimeout(() => { btn.textContent = '+ Newsletter'; }, 1500);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

function handleOverlayClick(e) {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeModal(); closeConfirmModal(); if (!_authGateMode) closeAuthModal(); closeSRModal(); closeTtpDrill(); closeChangelog(); closePirArticles(); closeExecDrill(); closeScraperArticlesModal(); if (typeof tawCloseArticlesModal === 'function') tawCloseArticlesModal(); } });

// ── SCRAPER ARTICLES MODAL ─────────────────────────────────────────
let _scraperArticlesData = { accepted: [], rejected: [] };
let _scraperActiveTab = 'rejected';

function closeScraperArticlesModal() {
  document.getElementById('scraper-articles-overlay').classList.remove('open');
}

function scraperSwitchTab(tab) {
  _scraperActiveTab = tab;
  const rejBtn = document.getElementById('scraper-tab-rejected');
  const accBtn = document.getElementById('scraper-tab-accepted');
  rejBtn.style.borderBottomColor = tab === 'rejected' ? 'var(--red)' : 'transparent';
  rejBtn.style.color = tab === 'rejected' ? 'var(--red)' : 'var(--text-dim)';
  accBtn.style.borderBottomColor = tab === 'accepted' ? 'var(--green)' : 'transparent';
  accBtn.style.color = tab === 'accepted' ? 'var(--green)' : 'var(--text-dim)';
  renderScraperArticles();
}

function renderScraperArticles() {
  const body = document.getElementById('scraper-articles-body');
  const items = _scraperArticlesData[_scraperActiveTab] || [];
  if (!items.length) {
    body.innerHTML = `<div style="padding:24px;text-align:center;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:11px;">No articles</div>`;
    return;
  }
  const dotColor = _scraperActiveTab === 'accepted' ? 'var(--green)' : 'var(--red)';
  body.innerHTML = items.map(a => {
    const date = a.run_at ? a.run_at.slice(0, 10) : '—';
    const titleHtml = a.url
      ? `<a href="${a.url}" target="_blank" rel="noopener noreferrer" style="color:var(--text);text-decoration:none;" onmouseover="this.style.color='var(--accent)'" onmouseout="this.style.color='var(--text)'">${a.title || '(no title)'} ↗</a>`
      : `<span style="color:var(--text)">${a.title || '(no title)'}</span>`;
    return `<div style="padding:8px 20px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;gap:10px">
      <span style="width:6px;height:6px;border-radius:50%;background:${dotColor};flex-shrink:0;margin-top:5px"></span>
      <div style="flex:1;min-width:0">
        <div style="font-size:12px;line-height:1.4;word-break:break-word">${titleHtml}</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);margin-top:3px">${date}</div>
      </div>
    </div>`;
  }).join('');
}

async function openScraperArticlesModal(script, days) {
  const overlay = document.getElementById('scraper-articles-overlay');
  document.getElementById('scraper-articles-title').textContent = script;
  document.getElementById('scraper-articles-stats').textContent = 'Loading…';
  document.getElementById('scraper-articles-body').innerHTML = `<div style="padding:32px;text-align:center;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:11px;">Loading…</div>`;
  overlay.classList.add('open');
  _scraperActiveTab = 'rejected';
  scraperSwitchTab('rejected');
  try {
    const resp = await fetch(`/api/scraper/articles?script=${encodeURIComponent(script)}&days=${days}`, { headers: _authHeader() });
    const d = await resp.json();
    _scraperArticlesData = d;
    const total = d.accepted.length + d.rejected.length;
    const rate = total ? Math.round(d.accepted.length / total * 100) : 0;
    document.getElementById('scraper-accepted-count').textContent = `(${d.accepted.length})`;
    document.getElementById('scraper-rejected-count').textContent = `(${d.rejected.length})`;
    document.getElementById('scraper-articles-stats').textContent = `${total} articles · ${rate}% accepted · last ${days}d`;
    renderScraperArticles();
  } catch (e) {
    document.getElementById('scraper-articles-body').innerHTML = `<div style="padding:24px;text-align:center;color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:11px;">Failed to load</div>`;
  }
}

// ── CONFIRM MODAL ─────────────────────────────────────────
let _confirmCallback = null;

function showConfirmModal({ title, body, okLabel, okColor, onConfirm }) {
  document.getElementById('confirm-title').textContent = title || 'Confirm Action';
  document.getElementById('confirm-body').innerHTML   = body  || '';
  const okBtn = document.getElementById('confirm-ok-btn');
  okBtn.textContent = okLabel || 'Confirm';
  okBtn.style.background = okColor || '';   // '' falls back to CSS var(--red)
  _confirmCallback = onConfirm || null;
  document.getElementById('confirm-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function _confirmAction() {
  closeConfirmModal();
  if (_confirmCallback) _confirmCallback();
  _confirmCallback = null;
}

function closeConfirmModal() {
  document.getElementById('confirm-overlay').classList.remove('open');
  document.getElementById('confirm-ok-btn').style.background = '';  // reset colour
  document.body.style.overflow = '';
}

function handleConfirmOverlayClick(e) {
  if (e.target === document.getElementById('confirm-overlay')) closeConfirmModal();
}

