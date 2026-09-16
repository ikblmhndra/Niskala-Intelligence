// ── CHANGELOG ─────────────────────────────────────────────────
function openChangelog() {
  document.getElementById('cl-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  clShowList();
}

function closeChangelog() {
  document.getElementById('cl-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

async function clShowList() {
  document.getElementById('cl-title').textContent = 'Release History';
  document.getElementById('cl-back-btn').style.display = 'none';
  const body = document.getElementById('cl-body');
  body.innerHTML = '<div style="color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Loading…</div>';

  try {
    const resp = await fetch('/api/changelog', { headers: _authHeader() });
    const versions = await resp.json();
    body.innerHTML = `<div class="cl-version-list">${
      versions.map(v => `
        <div class="cl-version-row" onclick="clShowDetail('${esc(v.version)}')">
          <span class="cl-ver">v${esc(v.version)}</span>
          <span class="cl-date">${esc(v.date)}</span>
        </div>`).join('')
    }</div>`;
  } catch (e) {
    body.innerHTML = '<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Failed to load changelog.</div>';
  }
}

async function clShowDetail(version) {
  document.getElementById('cl-title').textContent = `v${version}`;
  document.getElementById('cl-back-btn').style.display = '';
  const body = document.getElementById('cl-body');
  body.innerHTML = '<div style="color:var(--text-dim);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Loading…</div>';

  try {
    const resp = await fetch(`/api/changelog/${encodeURIComponent(version)}`, { headers: _authHeader() });
    const d = await resp.json();
    body.innerHTML = `
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-dim);margin-bottom:14px">${esc(d.date)}</div>
      <div class="cl-content">${_clRenderMd(d.content)}</div>`;
  } catch (e) {
    body.innerHTML = '<div style="color:var(--red);font-family:\'IBM Plex Mono\',monospace;font-size:11px">Failed to load version.</div>';
  }
}

function _clRenderMd(md) {
  const lines = md.split('\n');
  let html = '';
  let inList = false;

  for (let line of lines) {
    // Section headers
    if (line.startsWith('### ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h3>${_clInline(line.slice(4))}</h3>`;
      continue;
    }
    if (line.startsWith('#### ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h4>${_clInline(line.slice(5))}</h4>`;
      continue;
    }
    // Bullet points (support 0-3 spaces of indent)
    const bulletMatch = line.match(/^(\s{0,3})-\s+(.+)/);
    if (bulletMatch) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${_clInline(bulletMatch[2])}</li>`;
      continue;
    }
    // Separators / empty
    if (!line.trim() || line.trim() === '---') {
      if (inList) { html += '</ul>'; inList = false; }
      continue;
    }
    // Plain paragraph line
    if (inList) { html += '</ul>'; inList = false; }
    html += `<p style="margin:4px 0;color:var(--text-dim)">${_clInline(line)}</p>`;
  }
  if (inList) html += '</ul>';
  return html;
}

function _clInline(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

