// Daily Recap tab
'use strict';

function _recapStatus(msg, kind) {
  const el = document.getElementById('recap-status');
  if (!el) return;
  const colors = { info: 'var(--text-dim)', ok: 'var(--accent)', err: 'var(--red)', warn: 'var(--orange)' };
  el.textContent = msg || '';
  el.style.color = colors[kind] || colors.info;
}

function _recapEsc(s) {
  return (s == null ? '' : String(s))
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function _recapConfBadge(c) {
  const t = (c || '').toLowerCase();
  const map = {
    high: ['#2ecc71', 'rgba(46,204,113,0.12)'],
    med:  ['#f39c12', 'rgba(243,156,18,0.12)'],
    low:  ['#95a5a6', 'rgba(149,165,166,0.12)'],
  };
  const [fg, bg] = map[t] || map.low;
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:9px;background:${bg};color:${fg};border:1px solid ${fg}55;padding:1px 6px;border-radius:2px;text-transform:uppercase;letter-spacing:.08em">${_recapEsc(c || 'low')}</span>`;
}

function _recapSection(title) {
  return `<div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.12em;margin:18px 0 8px;padding-bottom:5px;border-bottom:1px solid var(--border)">${_recapEsc(title)}</div>`;
}

function _recapList(items, mapFn) {
  if (!items || !items.length) {
    return `<div style="color:var(--text-dim);font-size:11px;font-style:italic">(none)</div>`;
  }
  return `<ul style="margin:0;padding:0 0 0 18px;font-size:13px;line-height:1.55">${
    items.map(mapFn).join('')
  }</ul>`;
}

function _recapChips(items) {
  if (!items || !items.length) return '<span style="color:var(--text-dim);font-size:11px;font-style:italic">(none)</span>';
  return items.map(v => `<span style="display:inline-block;background:rgba(47,129,247,0.10);border:1px solid var(--border-bright);color:var(--accent);padding:2px 8px;font-size:11px;font-family:'IBM Plex Mono',monospace;border-radius:2px;margin:2px 4px 2px 0">${_recapEsc(v)}</span>`).join('');
}

function _recapRenderEmpty(date, isLatest) {
  const body = document.getElementById('recap-body');
  if (!body) return;
  body.innerHTML = `
    <div style="padding:30px;text-align:center;border:1px dashed var(--border);border-radius:3px">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--text-dim);margin-bottom:10px">
        No recap stored for <b>${_recapEsc(date)}</b>${isLatest ? ' (yesterday)' : ''}.
      </div>
      <button onclick="recapGenerate(false)" class="btn-apply" style="font-size:11px;padding:6px 16px">↻ GENERATE NOW</button>
    </div>`;
}

function _recapRender(doc) {
  const body = document.getElementById('recap-body');
  if (!body) return;
  if (!doc) { _recapRenderEmpty('—', false); return; }

  const recap = doc.yesterday || {};
  const fcast = doc.forecast || {};
  const counts = doc.counts || {};
  const gen = doc.generated_at ? new Date(doc.generated_at).toLocaleString() : '—';
  const tu = doc.token_usage || {};
  const tuStr = tu.total_tokens ? ` · ${tu.total_tokens} tokens` : '';

  let html = '';
  html += `
    <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;padding:14px 16px;border:1px solid var(--border);border-radius:3px;background:linear-gradient(135deg,rgba(47,129,247,0.05),rgba(88,166,255,0.04));margin-bottom:8px">
      <div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.12em;margin-bottom:4px">Daily Recap · ${_recapEsc(doc.date)}</div>
        <div style="font-size:14px;line-height:1.5">${_recapEsc(doc.headline || '(no headline)')}</div>
      </div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-align:right">
        <div>${counts.articles||0} articles · ${counts.tweets||0} tweets</div>
        <div>${counts.cves||0} CVEs · ${counts.iocs||0} IOCs · ${counts.campaigns||0} campaigns</div>
        <div style="margin-top:4px">gen: ${_recapEsc(gen)}${_recapEsc(tuStr)}</div>
      </div>
    </div>`;

  html += _recapSection('Summary');
  html += `<div style="font-size:13px;line-height:1.6">${_recapEsc(recap.summary || '(no summary)')}</div>`;

  html += _recapSection(`Top Stories (${(recap.top_stories||[]).length})`);
  html += _recapList(recap.top_stories, s => `
    <li style="margin-bottom:6px"><b>${_recapEsc(s.title)}</b>
      <span style="color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:10px"> [${_recapEsc(s.source||'?')}]</span>
      <div style="color:var(--text-dim);font-size:12px;margin-top:2px">${_recapEsc(s.why_it_matters||'')}</div>
    </li>`);

  html += _recapSection(`Top Tweets (${(recap.top_tweets||[]).length})`);
  html += _recapList(recap.top_tweets, t => `
    <li style="margin-bottom:6px"><b>@${_recapEsc(t.author||'?')}</b>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;background:rgba(88,166,255,0.12);color:#58A6FF;border:1px solid rgba(88,166,255,0.3);padding:1px 5px;border-radius:2px;margin-left:4px">${_recapEsc(t.signal||'other')}</span>
      <div style="font-size:12px;margin-top:2px">${_recapEsc(t.summary||'')}</div>
    </li>`);

  html += _recapSection('Active Threat Actors');
  html += `<div>${_recapChips(recap.active_threat_actors)}</div>`;

  html += _recapSection('Notable CVEs');
  html += `<div>${_recapChips(recap.notable_cves)}</div>`;

  html += _recapSection(`Active Campaigns (${(recap.active_campaigns||[]).length})`);
  html += _recapList(recap.active_campaigns, c => `
    <li style="margin-bottom:6px"><b>${_recapEsc(c.theme||'(unlabeled)')}</b>
      <span style="color:var(--text-dim);font-family:'IBM Plex Mono',monospace;font-size:10px"> · ${c.article_count||0} articles</span>
      <div style="color:var(--text-dim);font-size:12px;margin-top:2px">${_recapEsc(c.why_it_matters||'')}</div>
    </li>`);

  if ((recap.apac_signals || []).length) {
    html += _recapSection('APAC Signals');
    html += _recapList(recap.apac_signals, s => `<li>${_recapEsc(s)}</li>`);
  }

  // ── Forecast ──
  html += `<div style="margin-top:24px;padding:14px 16px;border:1px solid var(--border-bright);border-radius:3px;background:rgba(243,156,18,0.04)">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--orange);text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px">▲ Forecast · Next 1-3 Days</div>
    <div style="font-size:13px;line-height:1.6;margin-bottom:8px">${_recapEsc(fcast.summary || '(no forecast)')}</div>`;

  html += _recapSection(`Likely Events (${(fcast.likely_events||[]).length})`);
  html += _recapList(fcast.likely_events, e => `
    <li style="margin-bottom:8px"><b>${_recapEsc(e.event||'')}</b> ${_recapConfBadge(e.confidence)}
      <div style="color:var(--text-dim);font-size:12px;margin-top:2px"><span style="font-family:'IBM Plex Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:.08em">Basis:</span> ${_recapEsc(e.basis||'')}</div>
    </li>`);

  if ((fcast.watch_items || []).length) {
    html += _recapSection('Watch Items');
    html += _recapList(fcast.watch_items, w => `<li>${_recapEsc(w)}</li>`);
  }
  html += `</div>`;

  if (doc.raw_llm) {
    html += `<details style="margin-top:18px"><summary style="cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.1em">Raw LLM output (parse fallback)</summary><pre style="font-size:11px;color:var(--text-dim);white-space:pre-wrap;padding:10px;border:1px solid var(--border);border-radius:3px;margin-top:6px">${_recapEsc(doc.raw_llm)}</pre></details>`;
  }

  body.innerHTML = html;
}

async function recapLoadHistory() {
  const list = document.getElementById('recap-history-list');
  if (!list) return;
  try {
    const r = await fetch('/api/recap/list?limit=60', { headers: { ..._authHeader() } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    const items = j.recaps || [];
    if (!items.length) {
      list.innerHTML = '<div style="color:var(--text-dim);padding:6px;font-size:11px">No recaps yet.</div>';
      return;
    }
    list.innerHTML = items.map(it => {
      const c = it.counts || {};
      return `<button onclick="recapLoad('${_recapEsc(it.date)}')"
        style="text-align:left;background:transparent;border:1px solid var(--border);color:var(--text);padding:6px 8px;font-family:'IBM Plex Mono',monospace;font-size:11px;border-radius:2px;cursor:pointer">
        <div style="color:var(--accent)">${_recapEsc(it.date)}</div>
        <div style="color:var(--text-dim);font-size:10px;margin-top:2px">${c.articles||0}a · ${c.tweets||0}t · ${c.cves||0}c</div>
      </button>`;
    }).join('');
  } catch (e) {
    list.innerHTML = `<div style="color:var(--red);font-size:11px;padding:6px">${_recapEsc(e.message)}</div>`;
  }
}

async function recapLoad(date) {
  const input = document.getElementById('recap-date');
  if (date && input) input.value = date;
  const d = date || (input ? input.value : '');
  _recapStatus('Loading…', 'info');
  try {
    const url = d ? `/api/recap/${encodeURIComponent(d)}` : '/api/recap/latest';
    const r = await fetch(url, { headers: { ..._authHeader() } });
    if (r.status === 404) {
      _recapRenderEmpty(d || 'yesterday', !d);
      _recapStatus('No recap stored for that date', 'warn');
      return;
    }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    _recapRender(j.recap);
    _recapStatus('Loaded', 'ok');
  } catch (e) {
    _recapStatus(e.message, 'err');
  }
}

function recapConfirmClose() {
  const ov = document.getElementById('recap-confirm-overlay');
  if (ov) ov.classList.remove('open');
}

function recapGenerate(force) {
  const input = document.getElementById('recap-date');
  const d = (input ? input.value : '') || '';
  const dateLabel = d || 'yesterday';
  const ov = document.getElementById('recap-confirm-overlay');
  const msg = document.getElementById('recap-confirm-msg');
  const warn = document.getElementById('recap-confirm-warn');
  const ok = document.getElementById('recap-confirm-ok');
  if (!ov || !msg || !ok) {
    _recapRunGenerate(d, force);
    return;
  }
  msg.textContent = `Generate recap for ${dateLabel}?`;
  if (warn) warn.style.display = force ? 'block' : 'none';
  ok.textContent = force ? 'FORCE REGEN' : 'GENERATE';
  ok.onclick = () => {
    recapConfirmClose();
    _recapRunGenerate(d, force);
  };
  ov.classList.add('open');
}

async function _recapRunGenerate(d, force) {
  _recapStatus('Generating… this can take 10-30s', 'info');
  try {
    const qs = new URLSearchParams();
    if (d) qs.set('date', d);
    if (force) qs.set('force', 'true');
    const r = await fetch(`/api/recap/generate?${qs.toString()}`, {
      method: 'POST',
      headers: { ..._authHeader() },
    });
    if (!r.ok) {
      const txt = await r.text();
      throw new Error('HTTP ' + r.status + ': ' + txt.slice(0, 200));
    }
    const j = await r.json();
    _recapRender(j.recap);
    _recapStatus('Generated · saved', 'ok');
    recapLoadHistory();
  } catch (e) {
    _recapStatus(e.message, 'err');
  }
}

function loadRecap() {
  const input = document.getElementById('recap-date');
  if (input && !input.value) {
    const y = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    input.value = y;
  }
  recapLoadHistory();
  recapLoad(input ? input.value : '');
}
