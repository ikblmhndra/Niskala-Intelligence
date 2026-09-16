const PAGE_SIZE = 15;

// ── ARTICLE CACHE (counter-based, avoids _id vs id alias issue) ──
let   _cacheIdx = 0;
const _cache    = {};

function storeArticle(a) {
  const key = ++_cacheIdx;
  _cache[key] = a;
  return key;
}

// ── COUNTRY GROUPS ────────────────────────────────────────
// Populated at init from /api/country-groups (single source of truth)
let variantToCanonical = {};
let canonicalToVariants = {};

function normalizeCountryList(rawList) {
  const seen = new Set();
  const result = [];
  rawList.forEach(raw => {
    const c = variantToCanonical[raw] || raw;
    if (!seen.has(c)) { seen.add(c); result.push(c); }
  });
  return result.sort();
}

function expandCountry(canonical) {
  // Return all DB-side variant strings for this canonical name
  return canonicalToVariants[canonical] || [canonical];
}

// ── STATE ─────────────────────────────────────────────────
const state = {
  apac:       { page: 1, total: 0 },
  global:     { page: 1, total: 0 },
  rw:         { page: 1, total: 0 },
  indo:       { page: 1, total: 0 },
  watchlist:  { page: 1, total: 0 },
  techstack:  { page: 1, total: 0 },
};

function getClientCountries() {
  try {
    return JSON.parse(localStorage.getItem('cti_client_countries') || '[]');
  } catch { return []; }
}

function localPanelTitle(countries) {
  if (!countries || countries.length === 0) return 'Global';
  if (countries.length === 1) return countries[0];
  return 'Local';
}

// ── UTILS ─────────────────────────────────────────────────
function esc(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  const days = Math.floor((Date.now() - d) / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return '1d ago';
  return `${days}d ago`;
}

function loadingHTML(span) {
  const style = span ? `style="grid-column:1/-1"` : '';
  return `<div class="loading-state" ${style}><div class="loading-spinner"></div><div class="loading-text">Loading...</div></div>`;
}

function emptyHTML(msg, span) {
  const style = span ? `style="grid-column:1/-1"` : '';
  return `<div class="empty-state" ${style}><div class="empty-icon">◉</div><div class="empty-text">${esc(msg)}</div></div>`;
}

