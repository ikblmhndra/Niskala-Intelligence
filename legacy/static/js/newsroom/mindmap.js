// ── MERMAID MINDMAP ──────────────────────────────────────────────────────────

(function () {
  function _initMermaid() {
    if (typeof mermaid === 'undefined') return;
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      themeVariables: {
        darkMode: true,
        background: '#0d1117',
        mainBkg: '#161b22',
        nodeBorder: '#30363d',
        titleColor: '#e6edf3',
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '12px',
      },
      mindmap: { padding: 16, useMaxWidth: true },
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initMermaid);
  } else {
    _initMermaid();
  }
})();

// ── Color helpers ─────────────────────────────────────────────────────────────

// Level-based default colors (bright, dark-bg friendly)
const _MM_LEVEL_COLORS = [
  '#e94560', // root — red
  '#f18f01', // level 1 — orange
  '#2e86ab', // level 2 — blue
  '#533483', // level 3 — purple
  '#1b7f5e', // level 4 — teal
  '#7b2d8b', // level 5 — violet
];
const _MM_DEFAULT_FG = '#ffffff';

function _mmCssKey(featureType, docId) {
  return `mm-colors::${featureType}::${docId}`;
}

function _mmLoadColors(featureType, docId) {
  try {
    return JSON.parse(localStorage.getItem(_mmCssKey(featureType, docId))) || {};
  } catch { return {}; }
}

function _mmSaveColors(featureType, docId, nodeBg, nodeFg) {
  localStorage.setItem(_mmCssKey(featureType, docId), JSON.stringify({ nodeBg, nodeFg }));
}

function _mmInjectColors(svgEl, nodeBg, nodeFg) {
  if (!svgEl) return;
  svgEl.querySelector('#mm-color-style')?.remove();

  const fg = nodeFg || _MM_DEFAULT_FG;
  const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  style.id = 'mm-color-style';

  let css = '';
  if (nodeBg) {
    // single color for all nodes
    css += `
      .mindmap-node > rect, .mindmap-node > circle, .mindmap-node > polygon,
      .mindmap-node > path, .mindmap-node > ellipse {
        fill: ${nodeBg} !important;
        stroke: ${nodeBg} !important;
      }`;
  } else {
    // level-based colors — Mermaid mindmap wraps each section in <g class="mindmap-node level-N">
    // fallback: target first 6 mindmap-node groups by index
    css += `
      .mindmap-node:nth-of-type(1) > rect, .mindmap-node:nth-of-type(1) > circle,
      .mindmap-node:nth-of-type(1) > path, .mindmap-node:nth-of-type(1) > ellipse
        { fill: ${_MM_LEVEL_COLORS[0]} !important; stroke: ${_MM_LEVEL_COLORS[0]} !important; }`;
    _MM_LEVEL_COLORS.forEach((color, i) => {
      css += `
      .mindmap-node.level-${i} > rect, .mindmap-node.level-${i} > circle,
      .mindmap-node.level-${i} > path, .mindmap-node.level-${i} > ellipse,
      .mindmap-node.section-${i} > rect, .mindmap-node.section-${i} > circle,
      .mindmap-node.section-${i} > path, .mindmap-node.section-${i} > ellipse
        { fill: ${color} !important; stroke: ${color} !important; }`;
    });
  }

  // White (or user chosen) font for all node text
  css += `
    .mindmap-node text, .mindmap-node tspan,
    .mindmap-node .label, .mindmap-node foreignObject span {
      fill: ${fg} !important;
      color: ${fg} !important;
    }
    .edge, .edge path, .edge line {
      stroke: #5a6a80 !important;
      stroke-opacity: 0.7;
      fill: none !important;
    }`;

  style.textContent = css;
  svgEl.insertBefore(style, svgEl.firstChild);
}

// ── Render ────────────────────────────────────────────────────────────────────

let _mmRenderSeq = 0;

async function _mmRender(container, syntax, nodeBg, nodeFg) {
  if (!syntax || !syntax.trim()) {
    container.innerHTML = '<span style="color:var(--text-dim);font-size:11px;font-family:\'IBM Plex Mono\',monospace">No mind map data.</span>';
    return;
  }
  if (typeof mermaid === 'undefined') {
    container.innerHTML = '<span style="color:var(--red);font-size:10px;font-family:\'IBM Plex Mono\',monospace">Mermaid.js not loaded.</span>';
    return;
  }
  try {
    const id = 'mmr-' + (++_mmRenderSeq);
    const { svg } = await mermaid.render(id, syntax);
    container.innerHTML = svg;
    const svgEl = container.querySelector('svg');
    if (svgEl) {
      svgEl.style.maxWidth = '100%';
      svgEl.style.height = 'auto';
      _mmInjectColors(svgEl, nodeBg || null, nodeFg || null);
    }
  } catch (e) {
    container.innerHTML = `<div style="color:var(--red);font-family:'IBM Plex Mono',monospace;font-size:10px;padding:8px;white-space:pre-wrap">Render error:\n${escHtml(e.message)}</div>`;
  }
}

// ── Inline toggle ─────────────────────────────────────────────────────────────

const _mmInline = {};

async function mmToggleInline(containerId, featureType, docId) {
  const key = `${featureType}:${docId}`;
  const wrap = document.getElementById(containerId);
  if (!wrap) return;

  if (_mmInline[key]?.visible) {
    wrap.style.display = 'none';
    _mmInline[key].visible = false;
    const btn = document.getElementById(`mm-toggle-btn-${containerId}`);
    if (btn) btn.textContent = '⬡ Mind Map';
    return;
  }

  wrap.style.display = 'block';
  _mmInline[key] = _mmInline[key] || {};
  _mmInline[key].visible = true;
  const btn = document.getElementById(`mm-toggle-btn-${containerId}`);
  if (btn) btn.textContent = '⬡ Hide Map';

  if (!_mmInline[key].loaded) {
    const diag = wrap.querySelector('.mm-diagram');
    if (diag) diag.innerHTML = '<div style="padding:8px;color:var(--text-dim);font-size:10px;font-family:\'IBM Plex Mono\',monospace">Loading…</div>';
    try {
      const res = await fetch(
        `/api/mindmap/${encodeURIComponent(featureType)}/${encodeURIComponent(docId)}`,
        { headers: _authAndClientHeaders() }
      );
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      const colors = _mmLoadColors(featureType, docId);
      if (diag) await _mmRender(diag, data.display_syntax || '', colors.nodeBg, colors.nodeFg);
      _mmInline[key].loaded = true;
    } catch (e) {
      const diag = wrap.querySelector('.mm-diagram');
      if (diag) diag.innerHTML = `<div style="color:var(--red);font-size:10px;font-family:'IBM Plex Mono',monospace;padding:8px">Error: ${escHtml(e.message)}</div>`;
    }
  }
}

function mmInlineWidget(containerId, featureType, docId, title) {
  return `
    <div style="margin-bottom:10px">
      <div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;display:flex;align-items:center;gap:8px">
        Mind Map
        <button id="mm-toggle-btn-${escHtml(containerId)}"
          onclick="mmToggleInline('${escHtml(containerId)}','${escHtml(featureType)}','${escHtml(docId)}')"
          style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 8px;border-radius:2px;background:rgba(110,124,255,.08);border:1px solid rgba(110,124,255,.3);color:#6E7CFF;cursor:pointer">⬡ Mind Map</button>
        <button onclick="mmOpenEditor('${escHtml(featureType)}','${escHtml(docId)}','${escHtml(title)}')"
          style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 8px;border-radius:2px;background:transparent;border:1px solid var(--border);color:var(--text-dim);cursor:pointer">✎ Edit Mindmap</button>
      </div>
      <div id="${escHtml(containerId)}" style="display:none">
        <div class="mm-diagram" style="background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px;padding:12px;overflow:auto;max-height:400px"></div>
      </div>
    </div>`;
}

// ── Editor modal ──────────────────────────────────────────────────────────────

let _mmEditorFeatureType = '';
let _mmEditorDocId = '';

function mmOpenEditor(featureType, docId, title) {
  _mmEditorFeatureType = featureType;
  _mmEditorDocId = docId;
  document.getElementById('mm-editor-modal')?.remove();

  const saved = _mmLoadColors(featureType, docId);
  const nodeBg = saved.nodeBg || '';
  const nodeFg = saved.nodeFg || _MM_DEFAULT_FG;

  const modal = document.createElement('div');
  modal.id = 'mm-editor-modal';
  modal.style.cssText = 'position:fixed;inset:0;z-index:9800;background:rgba(0,0,0,.92);display:flex;flex-direction:column;padding:16px;gap:8px';
  modal.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;flex-wrap:wrap">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-bright);font-weight:700">${escHtml(title || `${featureType}/${docId}`)}</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);padding:1px 6px;border-radius:2px;background:rgba(255,255,255,0.04);border:1px solid var(--border)">Mind Map Editor</span>

      <div style="display:flex;align-items:center;gap:6px;margin-left:8px" title="Node background color">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">Node</span>
        <input type="color" id="mm-color-bg" value="${nodeBg || '#1f6feb'}"
          style="width:26px;height:22px;border:1px solid var(--border);border-radius:3px;background:none;cursor:pointer;padding:1px"
          oninput="_mmPreviewDebounce()">
        <button onclick="_mmToggleLevelColors()" id="mm-level-btn" title="Use level-based colors instead"
          style="font-family:'IBM Plex Mono',monospace;font-size:8px;padding:1px 6px;border-radius:2px;background:${nodeBg?'transparent':'rgba(47,129,247,0.12)'};border:1px solid ${nodeBg?'var(--border)':'rgba(47,129,247,0.4)'};color:${nodeBg?'var(--text-dim)':'var(--accent)'};cursor:pointer">Auto</button>
      </div>

      <div style="display:flex;align-items:center;gap:6px" title="Font color">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim)">Font</span>
        <input type="color" id="mm-color-fg" value="${nodeFg}"
          style="width:26px;height:22px;border:1px solid var(--border);border-radius:3px;background:none;cursor:pointer;padding:1px"
          oninput="_mmPreviewDebounce()">
      </div>

      <div style="margin-left:auto;display:flex;gap:6px">
        <button onclick="_mmEditorRegenerate('${escHtml(featureType)}','${escHtml(docId)}')"
          style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;background:transparent;border:1px solid var(--border);color:var(--text-dim);border-radius:3px;cursor:pointer">⟳ Regenerate</button>
        <button id="mm-save-btn" onclick="_mmEditorSave('${escHtml(featureType)}','${escHtml(docId)}')"
          style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;background:rgba(47,129,247,0.1);border:1px solid rgba(47,129,247,0.4);color:var(--accent);border-radius:3px;cursor:pointer">💾 Save</button>
        <button onclick="document.getElementById('mm-editor-modal').remove()"
          style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;background:transparent;border:1px solid var(--border);color:var(--text-dim);border-radius:3px;cursor:pointer">✕ Close</button>
      </div>
    </div>
    <div id="mm-editor-status" style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text-dim);height:14px;flex-shrink:0"></div>
    <div style="display:flex;flex:1;gap:10px;min-height:0">
      <div style="display:flex;flex-direction:column;width:340px;flex-shrink:0;gap:4px">
        <div style="font-size:9px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:.05em">Mermaid Syntax</div>
        <textarea id="mm-editor-ta"
          style="flex:1;background:var(--surface);border:1px solid var(--border);color:var(--text-bright);font-family:'IBM Plex Mono',monospace;font-size:11px;padding:10px;resize:none;border-radius:4px;line-height:1.5"
          oninput="_mmPreviewDebounce()"
          spellcheck="false"></textarea>
      </div>
      <div style="flex:1;display:flex;flex-direction:column;gap:4px;min-width:0">
        <div style="font-size:9px;color:var(--text-dim);font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:.05em">Preview</div>
        <div id="mm-editor-preview"
          style="flex:1;overflow:auto;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:4px;padding:16px;display:flex;align-items:flex-start;justify-content:center"></div>
      </div>
    </div>`;

  document.body.appendChild(modal);

  // if no saved nodeBg, hide color picker and rely on level colors
  if (!nodeBg) {
    const bgInput = document.getElementById('mm-color-bg');
    if (bgInput) bgInput.style.opacity = '0.35';
  }

  fetch(`/api/mindmap/${encodeURIComponent(featureType)}/${encodeURIComponent(docId)}`, {
    headers: _authAndClientHeaders(),
  })
    .then(r => r.json())
    .then(async data => {
      const ta = document.getElementById('mm-editor-ta');
      if (ta) {
        ta.value = data.display_syntax || data.mermaid_syntax || '';
        await _mmEditorPreview();
      }
    })
    .catch(e => {
      const st = document.getElementById('mm-editor-status');
      if (st) st.textContent = `Load error: ${e.message}`;
    });
}

// Toggle between single color and auto level colors
function _mmToggleLevelColors() {
  const bgInput = document.getElementById('mm-color-bg');
  const btn = document.getElementById('mm-level-btn');
  if (!bgInput || !btn) return;

  const isAuto = bgInput.style.opacity === '0.35';
  if (isAuto) {
    // switch to single color mode
    bgInput.style.opacity = '1';
    btn.style.background = 'transparent';
    btn.style.borderColor = 'var(--border)';
    btn.style.color = 'var(--text-dim)';
  } else {
    // switch to auto level colors
    bgInput.style.opacity = '0.35';
    btn.style.background = 'rgba(47,129,247,0.12)';
    btn.style.borderColor = 'rgba(47,129,247,0.4)';
    btn.style.color = 'var(--accent)';
  }
  _mmPreviewDebounce();
}

function _mmGetEditorColors() {
  const bgInput = document.getElementById('mm-color-bg');
  const fgInput = document.getElementById('mm-color-fg');
  const isAuto = bgInput?.style.opacity === '0.35';
  return {
    nodeBg: isAuto ? null : (bgInput?.value || null),
    nodeFg: fgInput?.value || _MM_DEFAULT_FG,
  };
}

let _mmPreviewTimer = null;
function _mmPreviewDebounce() {
  clearTimeout(_mmPreviewTimer);
  _mmPreviewTimer = setTimeout(_mmEditorPreview, 400);
}

async function _mmEditorPreview() {
  const ta = document.getElementById('mm-editor-ta');
  const preview = document.getElementById('mm-editor-preview');
  if (!ta || !preview) return;
  const { nodeBg, nodeFg } = _mmGetEditorColors();
  await _mmRender(preview, ta.value, nodeBg, nodeFg);
}

async function _mmEditorSave(featureType, docId) {
  const ta = document.getElementById('mm-editor-ta');
  const btn = document.getElementById('mm-save-btn');
  const st  = document.getElementById('mm-editor-status');
  if (!ta || !btn) return;

  // persist color prefs to localStorage
  const { nodeBg, nodeFg } = _mmGetEditorColors();
  _mmSaveColors(featureType, docId, nodeBg, nodeFg);

  const orig = btn.textContent;
  btn.textContent = 'Saving…';
  btn.disabled = true;
  try {
    const res = await fetch(
      `/api/mindmap/${encodeURIComponent(featureType)}/${encodeURIComponent(docId)}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ..._authAndClientHeaders() },
        body: JSON.stringify({ syntax: ta.value }),
      }
    );
    if (!res.ok) throw new Error(await res.text());
    if (st) st.textContent = '✓ Saved';
    delete _mmInline[`${featureType}:${docId}`];
  } catch (e) {
    if (st) st.textContent = `Save error: ${e.message}`;
  }
  btn.textContent = orig;
  btn.disabled = false;
}

async function _mmEditorRegenerate(featureType, docId) {
  const st = document.getElementById('mm-editor-status');
  if (st) st.textContent = 'Regenerating…';
  try {
    const res = await fetch(
      `/api/mindmap/${encodeURIComponent(featureType)}/${encodeURIComponent(docId)}/regenerate`,
      { method: 'POST', headers: _authAndClientHeaders() }
    );
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const ta = document.getElementById('mm-editor-ta');
    if (ta) ta.value = data.display_syntax || '';
    await _mmEditorPreview();
    if (st) st.textContent = '✓ Regenerated';
    delete _mmInline[`${featureType}:${docId}`];
  } catch (e) {
    if (st) st.textContent = `Regen error: ${e.message}`;
  }
}
