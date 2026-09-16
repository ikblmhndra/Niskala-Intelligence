// ── X INTEL TAB ───────────────────────────────────────────

let _xiBalanceData  = null;
let _xiBalanceTimer = null;

async function xiLoadBalance(showSpinner = true) {
  const chip = document.getElementById('xi-balance-chip');
  if (!chip) return;
  if (showSpinner) { chip.textContent = '…'; _xiChipColor(chip, 'neutral'); }

  try {
    const data = await fetch('/api/tweets/balance', { headers: _authHeader() }).then(r => r.json());
    if (data.detail) {
      chip.textContent = 'Auth err';
      _xiChipColor(chip, 'red');
      chip.title = data.detail;
      return;
    }
    _xiBalanceData = { ...data, _ts: Date.now() };
    const recharge = data.recharge_credits ?? 0;
    const bonus    = data.total_bonus_credits ?? 0;
    const total    = recharge + bonus;
    chip.textContent = total.toLocaleString() + ' cr';
    chip.title = '';
    _xiChipColor(chip, total < 10000 ? 'red' : total < 50000 ? 'amber' : 'green');
    _xiUpdatePopover();
  } catch(e) {
    chip.textContent = 'ERR';
    _xiChipColor(chip, 'neutral');
  }

  // auto-refresh every 5 min while tab open
  clearTimeout(_xiBalanceTimer);
  _xiBalanceTimer = setTimeout(() => xiLoadBalance(false), 5 * 60 * 1000);
}

function _xiChipColor(chip, level) {
  const map = {
    green:   ['#1ed760', 'rgba(30,215,96,0.3)',  'rgba(30,215,96,0.1)'],
    amber:   ['#e3b341', 'rgba(227,179,65,0.4)', 'rgba(227,179,65,0.1)'],
    red:     ['#f85149', 'rgba(248,81,73,0.4)',  'rgba(248,81,73,0.1)'],
    neutral: ['var(--text-dim)', 'var(--border)', 'transparent'],
  };
  const [c, b, bg] = map[level] || map.neutral;
  chip.style.color = c;
  chip.style.borderColor = b;
  chip.style.background = bg;
}

function _xiUpdatePopover() {
  const pop = document.getElementById('xi-balance-popover');
  if (!pop || !_xiBalanceData) return;
  const d = _xiBalanceData;
  const recharge = (d.recharge_credits ?? 0).toLocaleString();
  const bonus    = (d.total_bonus_credits ?? 0).toLocaleString();
  const total    = ((d.recharge_credits ?? 0) + (d.total_bonus_credits ?? 0)).toLocaleString();
  const ts       = new Date(d._ts).toLocaleTimeString();
  pop.innerHTML = `
    <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;min-width:180px">
      <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;border-bottom:1px solid var(--border);padding-bottom:4px">𝕏 API Balance</div>
      <div style="display:grid;grid-template-columns:auto 1fr;gap:3px 12px;align-items:center">
        <span style="color:var(--text-dim)">Recharge</span><span style="text-align:right">${recharge}</span>
        <span style="color:var(--text-dim)">Bonus</span><span style="text-align:right">${bonus}</span>
        <span style="color:var(--text-dim);border-top:1px solid var(--border);padding-top:4px;margin-top:2px">Total</span>
        <span style="text-align:right;border-top:1px solid var(--border);padding-top:4px;margin-top:2px;font-weight:600">${total}</span>
      </div>
      <div style="color:var(--text-dim);font-size:10px;margin-top:8px;text-align:right">updated ${ts}</div>
    </div>`;
}

function xiToggleBalancePopover(e) {
  e.stopPropagation();
  const pop = document.getElementById('xi-balance-popover');
  if (!pop) return;
  const open = pop.style.display !== 'none';
  pop.style.display = open ? 'none' : 'block';
  if (!open) _xiUpdatePopover();
}

// close popover on outside click
document.addEventListener('click', () => {
  const pop = document.getElementById('xi-balance-popover');
  if (pop) pop.style.display = 'none';
});

// sub-tab state
let _xiActiveSubTab = 'tweets';
let _xiAccountsLoaded = false;

function xiSwitchSubTab(tab) {
  _xiActiveSubTab = tab;
  const tabs = ['tweets', 'accounts'];
  tabs.forEach(t => {
    const panel = document.getElementById(`xi-subtab-${t}`);
    const btn   = document.getElementById(`xi-subtab-btn-${t}`);
    if (!panel || !btn) return;
    const active = t === tab;
    panel.style.display = active ? '' : 'none';
    btn.style.background = active ? 'rgba(47,129,247,0.12)' : 'transparent';
    btn.style.borderColor = active ? 'var(--border-bright)' : 'var(--border)';
    btn.style.color = active ? 'var(--accent)' : 'var(--text-dim)';
  });
  if (tab === 'accounts' && !_xiAccountsLoaded) loadMonitoredAccounts();
}


const _XI_PAGE_SIZE = 20;
const _xiState = { page: 1, total: 0 };
let _xiLoaded = false;

// tweet cache for modal (same pattern as article cache in core.js)
let _xiCacheIdx = 0;
const _xiCache = {};

function _xiStore(t) {
  const key = ++_xiCacheIdx;
  _xiCache[key] = t;
  return key;
}

// ── LOAD & LIST ───────────────────────────────────────────

async function loadXIntel(page) {
  _xiState.page = page || 1;
  const listEl  = document.getElementById('xi-list');
  const pagerEl = document.getElementById('xi-pager');
  const statsEl = document.getElementById('xi-stats-row');
  listEl.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Loading…</div></div>';

  const params = new URLSearchParams({
    page:      _xiState.page,
    page_size: _XI_PAGE_SIZE,
  });

  const search = document.getElementById('xi-search')?.value.trim();
  const author = document.getElementById('xi-author')?.value.trim();
  const start  = document.getElementById('xi-date-start')?.value;
  const end    = document.getElementById('xi-date-end')?.value;
  if (search) params.set('search', search);
  if (author) params.set('author', author);
  if (start)  params.set('posted_on_start', start);
  if (end)    params.set('posted_on_end', end);
  if (document.getElementById('xi-apac-only')?.checked)      params.set('apac_only', 'true');
  if (document.getElementById('xi-ot-only')?.checked)        params.set('ot_only', 'true');
  if (document.getElementById('xi-confirmed-only')?.checked) params.set('confirmed_only', 'true');

  try {
    const [data, stats] = await Promise.all([
      fetch('/api/tweets?' + params, { headers: _authHeader() }).then(r => r.json()),
      fetch('/api/tweets/stats?' + params, { headers: _authHeader() }).then(r => r.json()),
    ]);

    _xiState.total = data.total;
    _xiLoaded = true;

    _renderXiStats(statsEl, stats);

    const countEl = document.getElementById('xintel-count');
    if (countEl) countEl.textContent = data.total;

    if (!data.tweets.length) {
      listEl.innerHTML = '<div class="empty-state"><div class="empty-icon">◉</div><div class="empty-text">No tweets found</div></div>';
      pagerEl.innerHTML = '';
      return;
    }

    listEl.innerHTML = data.tweets.map(renderTweetCard).join('');
    _renderXiPager(pagerEl, data.total, _xiState.page);
  } catch(e) {
    listEl.innerHTML = '<div class="empty-state" style="color:var(--red)">Failed to load tweets</div>';
  }
}

function _renderXiStats(el, stats) {
  const topAuthors = (stats.top_authors || []).slice(0, 5)
    .map(a => `<span style="color:var(--accent)">@${esc(a.author)}</span><span style="color:var(--text-dim)">(${a.count})</span>`)
    .join(' · ');
  el.innerHTML = `
    <span>Total: <strong style="color:var(--text-bright)">${stats.total}</strong></span>
    ${topAuthors ? `<span style="color:var(--border)">|</span><span>Top: ${topAuthors}</span>` : ''}
  `;
}

// ── TWEET CARD ────────────────────────────────────────────

function renderTweetCard(t) {
  const key = _xiStore(t);

  const avatar = t.author_avatar
    ? `<img src="${esc(t.author_avatar)}" style="width:36px;height:36px;border-radius:50%;border:1px solid var(--border);flex-shrink:0;object-fit:cover" onerror="this.style.display='none'">`
    : `<div style="width:36px;height:36px;border-radius:50%;border:1px solid var(--border);flex-shrink:0;background:var(--surface2);display:flex;align-items:center;justify-content:center;font-size:14px;color:var(--text-dim)">𝕏</div>`;

  const age = timeAgo(t.posted_on);
  const cleanText = esc(t.text.replace(/https:\/\/t\.co\/\S+/g, '').trim());

  const badges = _buildBadges(t, 2);

  const media = (t.media_urls||[]).slice(0,2).map(url =>
    `<img src="${esc(url)}" style="height:60px;width:auto;border-radius:3px;border:1px solid var(--border);object-fit:cover;cursor:pointer" onclick="event.stopPropagation();window.open('${esc(t.url)}','_blank')">`
  ).join('');

  const industries = (t.industries_impacted||[]).slice(0,2).map(i =>
    `<span style="font-size:9px;color:var(--text-dim)">${esc(i)}</span>`
  ).join(' · ');

  return `<div style="display:flex;gap:10px;padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:4px;transition:border-color .15s;cursor:pointer"
    onclick="openXiModal(${key})"
    onmouseover="this.style.borderColor='var(--border-bright)'"
    onmouseout="this.style.borderColor='var(--border)'">
    ${avatar}
    <div style="flex:1;min-width:0">
      <div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        <span style="color:var(--text-bright);font-weight:600;font-size:13px">${esc(t.author_name)}</span>
        <span style="color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:11px">@${esc(t.author_username)}</span>
        <span style="color:var(--text-dim);font-size:11px;margin-left:auto">${esc(age)}</span>
      </div>
      <div style="font-size:13px;line-height:1.5;color:var(--text);margin-bottom:8px;word-break:break-word;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden">${cleanText}</div>
      ${media ? `<div style="display:flex;gap:6px;margin-bottom:8px">${media}</div>` : ''}
      <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap">
        ${badges.join('')}
        ${industries ? `<span style="margin-left:auto;font-size:9px;color:var(--text-dim)">${industries}</span>` : ''}
        <a href="${esc(t.url)}" target="_blank" rel="noopener"
          onclick="event.stopPropagation()"
          style="margin-left:${industries ? '0' : 'auto'};font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--accent);text-decoration:none;padding:2px 8px;border:1px solid rgba(47,129,247,0.3);border-radius:2px">↗ Open</a>
      </div>
    </div>
  </div>`;
}

function _buildBadges(t, groupLimit) {
  const badges = [];
  if (t.apac_indicator)     badges.push(`<span style="font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(47,129,247,0.12);border:1px solid rgba(47,129,247,0.3);color:var(--accent)">APAC</span>`);
  if (t.ot_status)          badges.push(`<span style="font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(227,179,65,0.12);border:1px solid rgba(227,179,65,0.3);color:var(--orange)">OT</span>`);
  if (t.confirmed_incident) badges.push(`<span style="font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(218,54,51,0.12);border:1px solid rgba(218,54,51,0.3);color:var(--red)">CONFIRMED</span>`);
  if (t.report_status)      badges.push(`<span style="font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(88,166,255,0.1);border:1px solid rgba(88,166,255,0.2);color:var(--accent3)">REPORT</span>`);
  if ((t.zero_day_list||[]).length) badges.push(`<span style="font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(218,54,51,0.15);border:1px solid rgba(218,54,51,0.4);color:var(--red);font-weight:700">0-DAY</span>`);
  (t.cve_list||[]).slice(0, groupLimit).forEach(cve =>
    badges.push(`<span style="font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(218,54,51,0.08);border:1px solid rgba(218,54,51,0.2);color:#ff9aa5;font-family:'IBM Plex Mono',monospace">${esc(cve.toUpperCase())}</span>`)
  );
  (t.mentioned_group||[]).slice(0, groupLimit).forEach(g =>
    badges.push(`<span style="font-size:9px;padding:1px 5px;border-radius:2px;background:rgba(10,64,64,0.6);border:1px solid var(--border);color:var(--text-dim)">${esc(g)}</span>`)
  );
  return badges;
}

// ── TWEET MODAL ───────────────────────────────────────────

function openXiModal(key) {
  const t = _xiCache[key];
  if (!t) return;
  window._xiModalTweet = t;
  const btn = document.getElementById('xi-modal-newsletter-btn');
  if (btn) btn.textContent = '+ Newsletter';

  document.getElementById('xi-modal-title').textContent = `@${t.author_username}`;
  document.getElementById('xi-modal-tweet-link').href = t.url;

  const cleanText = t.text.replace(/https:\/\/t\.co\/\S+/g, '').trim();
  const media = (t.media_urls||[]).map(url =>
    `<img src="${esc(url)}" style="max-width:100%;border-radius:4px;border:1px solid var(--border);cursor:pointer" onclick="window.open('${esc(url)}','_blank')">`
  ).join('');

  // ── Author section
  const avatar = t.author_avatar
    ? `<img src="${esc(t.author_avatar)}" style="width:48px;height:48px;border-radius:50%;border:1px solid var(--border);object-fit:cover" onerror="this.style.display='none'">`
    : `<div style="width:48px;height:48px;border-radius:50%;border:1px solid var(--border);background:var(--surface2);display:flex;align-items:center;justify-content:center;font-size:20px;color:var(--text-dim)">𝕏</div>`;

  let html = `
    <div style="display:flex;gap:12px;align-items:flex-start;padding-bottom:16px;border-bottom:1px solid var(--border)">
      ${avatar}
      <div style="flex:1">
        <div style="font-size:15px;font-weight:700;color:var(--text-bright)">${esc(t.author_name)}</div>
        <div style="font-size:12px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace">@${esc(t.author_username)}</div>
        <div style="font-size:11px;color:var(--text-dim);margin-top:2px">${esc((t.author_followers||0).toLocaleString())} followers</div>
      </div>
      <div style="text-align:right;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dim)">
        <div>${esc(t.posted_on ? t.posted_on.slice(0,16).replace('T',' ') + ' UTC' : '—')}</div>
        <div style="margin-top:2px">lang: ${esc(t.lang||'—')}</div>
      </div>
    </div>

    <!-- Full tweet text -->
    <div style="font-size:14px;line-height:1.6;color:var(--text-bright);word-break:break-word;white-space:pre-wrap;padding:14px 0;border-bottom:1px solid var(--border)">${esc(cleanText)}</div>
  `;

  // ── Media
  if (media) {
    html += `<div style="display:flex;flex-direction:column;gap:8px;padding:12px 0;border-bottom:1px solid var(--border)">${media}</div>`;
  }

  // ── TI Metadata
  html += `<div style="display:flex;flex-direction:column;gap:12px;padding-top:14px">`;

  // Status badges row
  const allBadges = _buildBadges(t, 99);
  if (allBadges.length) {
    html += `<div>
      <div class="modal-section-label">Signals</div>
      <div class="modal-tags" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">${allBadges.join('')}</div>
    </div>`;
  }

  // Threat Groups
  html += _xiMetaRow('Threat Groups', t.mentioned_group, 'red');

  // APAC Countries / People
  if ((t.mentioned_apac_country||[]).length || (t.mentioned_apac_people||[]).length) {
    const items = [
      ...(t.mentioned_apac_country||[]).map(c => `<span class="modal-tag accent">${esc(c)}</span>`),
      ...(t.mentioned_apac_people||[]).map(p => `<span class="modal-tag yellow">${esc(p)}</span>`),
    ];
    html += `<div>
      <div class="modal-section-label">APAC Countries / People</div>
      <div class="modal-tags" style="margin-top:6px">${items.join('') || '<span class="modal-tag">—</span>'}</div>
    </div>`;
  }

  // CVEs
  html += _xiMetaRow('CVEs Mentioned', t.cve_list, 'red', true);

  // Zero Days
  html += _xiMetaRow('Zero-Day Signals', t.zero_day_list, 'red');

  // Data Breach keywords
  html += _xiMetaRow('Data Breach Signals', t.databreach_list, 'accent');

  // Industries Impacted
  html += _xiMetaRow('Industries Impacted', t.industries_impacted, 'yellow');

  // Victim / Actor Countries (LLM)
  if ((t.victim_countries||[]).length || (t.actor_countries||[]).length) {
    const items = [
      ...(t.victim_countries||[]).map(c => `<span class="modal-tag accent" title="Victim">${esc(c)} <span style="font-size:9px;opacity:.7">VICTIM</span></span>`),
      ...(t.actor_countries||[]).map(c => `<span class="modal-tag red" title="Actor">${esc(c)} <span style="font-size:9px;opacity:.7">ORIGIN</span></span>`),
    ];
    html += `<div>
      <div class="modal-section-label">Country Roles (LLM)</div>
      <div class="modal-tags" style="margin-top:6px">${items.join('')}</div>
    </div>`;
  }

  // Incident details
  if (t.confirmed_incident) {
    html += `<div>
      <div class="modal-section-label">Incident</div>
      <div style="margin-top:6px;font-size:12px;display:flex;flex-direction:column;gap:4px">
        ${t.victim_name ? `<div><span style="color:var(--text-dim)">Victim:</span> <span style="color:var(--text-bright)">${esc(t.victim_name)}</span></div>` : ''}
        ${(t.incident_indicators||[]).length ? `<div><span style="color:var(--text-dim)">Indicators:</span> ${t.incident_indicators.map(i => `<span class="modal-tag red" style="font-size:9px">${esc(i)}</span>`).join(' ')}</div>` : ''}
        ${t.incident_confidence != null ? `<div><span style="color:var(--text-dim)">Confidence:</span> <span style="color:var(--text-bright)">${(t.incident_confidence*100).toFixed(0)}%</span></div>` : ''}
      </div>
    </div>`;
  }

  // LLM confidence + reason
  if (t.confidence != null) {
    html += `<div>
      <div class="modal-section-label">LLM Cyber Relevance</div>
      <div style="margin-top:6px;font-size:12px;color:var(--text-dim)">
        Confidence: <span style="color:var(--text-bright)">${(t.confidence*100).toFixed(0)}%</span>
      </div>
    </div>`;
  }

  // Fetched at
  html += `<div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);padding-top:8px;border-top:1px solid var(--border)">
    fetched_at: ${esc(t.fetched_at ? t.fetched_at.slice(0,19).replace('T',' ') + ' UTC' : '—')}
    &nbsp;·&nbsp; tweet_id: ${esc(t.tweet_id||'—')}
  </div>`;

  html += `</div>`;

  document.getElementById('xi-modal-body').innerHTML = html;
  document.getElementById('xi-modal-overlay').classList.add('open');
}

function closeXiModal() {
  document.getElementById('xi-modal-overlay').classList.remove('open');
}

function queueTweetForNewsletter() {
  const t = window._xiModalTweet;
  if (!t) return;
  const id = t._id || t.tweet_id || null;
  const queue = JSON.parse(localStorage.getItem('newsletter_queue') || '[]');
  const btn = document.getElementById('xi-modal-newsletter-btn');
  if (id && queue.find(x => (x._id || x.id) === id)) {
    if (btn) { btn.textContent = '✓ Already queued'; setTimeout(() => { btn.textContent = '+ Newsletter'; }, 1500); }
    return;
  }
  const item = {
    _id: id,
    title: t.text ? t.text.replace(/https:\/\/t\.co\/\S+/g, '').trim().slice(0, 120) : '(tweet)',
    source: t.author_username ? `@${t.author_username}` : '𝕏 Intel',
    posted_on: t.posted_on || '',
    url: t.url || '',
    _is_tweet: true,
  };
  queue.push(item);
  localStorage.setItem('newsletter_queue', JSON.stringify(queue));
  if (btn) { btn.textContent = `✓ Queued (${queue.length})`; setTimeout(() => { btn.textContent = '+ Newsletter'; }, 1500); }
}

function xiHandleOverlayClick(event) {
  if (event.target === document.getElementById('xi-modal-overlay')) closeXiModal();
}

// helper: render a tagged list section
function _xiMetaRow(label, items, colorClass, mono) {
  if (!(items||[]).length) return '';
  const tags = items.map(v =>
    `<span class="modal-tag ${colorClass}" style="${mono ? "font-family:'IBM Plex Mono',monospace" : ''}">${esc(v)}</span>`
  ).join('');
  return `<div>
    <div class="modal-section-label">${label}</div>
    <div class="modal-tags" style="margin-top:6px">${tags}</div>
  </div>`;
}

// ── PAGER & FILTERS ───────────────────────────────────────

function _renderXiPager(el, total, page) {
  const pages = Math.ceil(total / _XI_PAGE_SIZE);
  if (pages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="pager">
    <button class="pager-btn" onclick="loadXIntel(${page - 1})" ${page <= 1 ? 'disabled' : ''}>◀ Prev</button>
    <span class="pager-info">PAGE <strong>${page}</strong> / ${pages} &nbsp;·&nbsp; ${total} tweets</span>
    <button class="pager-btn" onclick="loadXIntel(${page + 1})" ${page >= pages ? 'disabled' : ''}>Next ▶</button>
  </div>`;
}

function xiResetFilters() {
  document.getElementById('xi-search').value = '';
  document.getElementById('xi-author').value = '';
  document.getElementById('xi-date-start').value = '';
  document.getElementById('xi-date-end').value = '';
  document.getElementById('xi-apac-only').checked = false;
  document.getElementById('xi-ot-only').checked = false;
  document.getElementById('xi-confirmed-only').checked = false;
  loadXIntel(1);
}

// ── MONITORED ACCOUNTS ────────────────────────────────────

async function loadMonitoredAccounts() {
  _xiAccountsLoaded = true;
  const el = document.getElementById('xi-accounts-list');
  el.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><div class="loading-text">Loading…</div></div>';
  try {
    const data = await fetch('/api/monitored-accounts', { headers: _authHeader() }).then(r => r.json());
    _renderAccountsTable(el, data);
  } catch(e) {
    el.innerHTML = '<div class="empty-state" style="color:var(--red)">Failed to load accounts</div>';
  }
}

function _renderAccountsTable(el, accounts) {
  if (!accounts.length) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">◉</div><div class="empty-text">No accounts monitored yet</div></div>';
    return;
  }
  const rows = accounts.map(a => `
    <tr style="border-bottom:1px solid var(--border)">
      <td style="padding:8px 10px;font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent)">@${esc(a.username)}</td>
      <td style="padding:8px 10px;font-size:12px;color:var(--text)">${esc(a.display_name || '—')}</td>
      <td style="padding:8px 10px;font-size:12px;color:var(--text-dim)">${esc(a.notes || '—')}</td>
      <td style="padding:8px 10px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dim)">${esc(a.added_at ? a.added_at.slice(0,10) : '—')}</td>
      <td style="padding:8px 10px">
        <label style="display:flex;align-items:center;gap:5px;cursor:pointer;font-size:11px;color:var(--text-dim)">
          <input type="checkbox" ${a.active ? 'checked' : ''} onchange="xiToggleAccount('${esc(a.username)}', this.checked)" style="accent-color:var(--accent)"> Active
        </label>
      </td>
      <td style="padding:8px 10px">
        <button onclick="xiRemoveAccount('${esc(a.username)}')"
          style="background:rgba(218,54,51,0.08);border:1px solid rgba(218,54,51,0.25);color:var(--red);padding:3px 10px;font-size:10px;font-family:'IBM Plex Mono',monospace;border-radius:2px;cursor:pointer">
          Remove
        </button>
      </td>
    </tr>`).join('');
  el.innerHTML = `
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="border-bottom:1px solid var(--border)">
          <th style="padding:6px 10px;text-align:left;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">Handle</th>
          <th style="padding:6px 10px;text-align:left;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">Display Name</th>
          <th style="padding:6px 10px;text-align:left;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">Notes</th>
          <th style="padding:6px 10px;text-align:left;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">Added</th>
          <th style="padding:6px 10px;text-align:left;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em">Status</th>
          <th style="padding:6px 10px"></th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);margin-top:10px">${accounts.length} account${accounts.length !== 1 ? 's' : ''} monitored</div>
  `;
}

async function xiAddAccount() {
  const username = document.getElementById('xi-acc-username').value.trim();
  const display  = document.getElementById('xi-acc-display').value.trim();
  const notes    = document.getElementById('xi-acc-notes').value.trim();
  const msg      = document.getElementById('xi-acc-msg');
  if (!username) { msg.textContent = 'Handle required'; msg.style.color = 'var(--red)'; return; }
  try {
    const r = await fetch('/api/monitored-accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeader() },
      body: JSON.stringify({username, display_name: display, notes}),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      msg.textContent = err.detail || 'Error adding account';
      msg.style.color = 'var(--red)';
      return;
    }
    document.getElementById('xi-acc-username').value = '';
    document.getElementById('xi-acc-display').value = '';
    document.getElementById('xi-acc-notes').value = '';
    msg.textContent = `@${username.replace(/^@/, '')} added`;
    msg.style.color = 'var(--accent)';
    setTimeout(() => { msg.textContent = ''; }, 2500);
    _xiAccountsLoaded = false;
    loadMonitoredAccounts();
  } catch(e) {
    msg.textContent = 'Network error';
    msg.style.color = 'var(--red)';
  }
}

async function xiRemoveAccount(username) {
  if (!confirm(`Remove @${username} from monitored accounts?`)) return;
  try {
    await fetch(`/api/monitored-accounts/${encodeURIComponent(username)}`, { method: 'DELETE', headers: _authHeader() });
    _xiAccountsLoaded = false;
    loadMonitoredAccounts();
  } catch(e) { /* ignore */ }
}

async function xiToggleAccount(username, active) {
  try {
    await fetch(`/api/monitored-accounts/${encodeURIComponent(username)}/toggle`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ..._authHeader() },
      body: JSON.stringify({active}),
    });
  } catch(e) { /* ignore */ }
}
