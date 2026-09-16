// ── AUTH MODAL (shared) ────────────────────────────────────
// ── JWT Auth ──────────────────────────────────────────────────
// _CTI_AUTH_REQUIRED declared inline in newsroom.html (Jinja2 context)
// Token stored in localStorage; decoded payload cached in _jwtPayload.
let _jwtToken   = localStorage.getItem('cti_jwt') || null;
let _jwtPayload = _jwtToken ? _jwtDecode(_jwtToken) : null;

function _jwtDecode(token) {
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(b64));
  } catch { return null; }
}

function _jwtValid() {
  if (!_jwtToken || !_jwtPayload) return false;
  return (_jwtPayload.exp || 0) * 1000 > Date.now();
}

function _jwtClear() {
  _jwtToken   = null;
  _jwtPayload = null;
  localStorage.removeItem('cti_jwt');
  localStorage.removeItem('active_client_id');
  localStorage.removeItem('cti_client_countries');
}

function _authHeader() {
  return _jwtToken ? { 'Authorization': 'Bearer ' + _jwtToken } : {};
}

function _jwtUsername() {
  return _jwtPayload ? (_jwtPayload.sub || '') : '';
}

function _jwtRole() {
  return _jwtPayload ? (_jwtPayload.role || '') : '';
}

function _jwtClientIds() {
  if (!_jwtPayload) return ['default'];
  // support both old client_id:str and new client_ids:list
  const ids = _jwtPayload.client_ids;
  if (Array.isArray(ids) && ids.length) return ids;
  return [_jwtPayload.client_id || 'default'];
}

function getActiveClientId() {
  const stored = localStorage.getItem('active_client_id');
  if (_jwtRole() === 'superadmin') {
    return stored || _jwtClientIds()[0];
  }
  const ids = _jwtClientIds();
  // validate stored is still in allowed list
  if (stored && ids.includes(stored)) return stored;
  return ids[0];
}

function _clientHeader() {
  return { 'X-Client-ID': getActiveClientId() };
}

function _authAndClientHeaders(extra) {
  return { ..._authHeader(), ..._clientHeader(), ...(extra || {}) };
}

function _updateHeaderAuth() {
  const loggedIn = _jwtValid();
  const username = _jwtUsername();
  const role     = _jwtRole();
  document.getElementById('header-username').textContent = loggedIn ? ('● ' + username) : '';
  document.getElementById('header-user-wrap').style.display = loggedIn ? '' : 'none';
  if (loggedIn) _refreshQueueCount();
  document.getElementById('header-login-btn').style.display  = 'none'; // gate handles login
  document.getElementById('header-logout-btn').style.display = loggedIn ? '' : 'none';
  const umTab = document.getElementById('tab-btn-usermgmt');
  if (umTab) umTab.style.display = (loggedIn && (role === 'admin' || role === 'superadmin')) ? '' : 'none';

  // "Not Related Cyber" sub-tab — admin/superadmin only
  const filteredBtn = document.getElementById('newsroom-filtered-btn');
  if (filteredBtn) {
    filteredBtn.style.display = (loggedIn && ['admin','superadmin'].includes(role)) ? '' : 'none';
  }

  // Client switcher — superadmin always; others when assigned to 2+ clients
  const switcher = document.getElementById('client-switcher-wrap');
  if (switcher) {
    const ids = _jwtClientIds();
    const showSwitcher = loggedIn && (role === 'superadmin' || ids.length > 1);
    switcher.style.display = showSwitcher ? '' : 'none';
    if (showSwitcher) _loadClientSwitcher();
  }
}

async function _loadClientSwitcher() {
  const sel = document.getElementById('client-switcher-select');
  if (!sel) return;
  const active = getActiveClientId();

  if (_jwtRole() === 'superadmin') {
    try {
      const resp = await fetch('/api/clients', { headers: _authHeader() });
      if (!resp.ok) return;
      const clients = await resp.json();
      if (!window._clientsCountriesMap) window._clientsCountriesMap = {};
      clients.forEach(c => { window._clientsCountriesMap[c.client_id] = c.countries || []; });
      sel.innerHTML = clients.map(c =>
        `<option value="${c.client_id}" ${c.client_id === active ? 'selected' : ''}>${c.name} (${c.client_id})</option>`
      ).join('');
    } catch(e) { console.error('client switcher:', e); }
  } else {
    // non-superadmin: only show assigned clients
    const ids = _jwtClientIds();
    sel.innerHTML = ids.map(id =>
      `<option value="${id}" ${id === active ? 'selected' : ''}>${id}</option>`
    ).join('');
  }
}

function onClientSwitch() {
  const sel = document.getElementById('client-switcher-select');
  if (!sel) return;
  const newClientId = sel.value;
  localStorage.setItem('active_client_id', newClientId);
  if (window._clientsCountriesMap && Array.isArray(window._clientsCountriesMap[newClientId])) {
    localStorage.setItem('cti_client_countries', JSON.stringify(window._clientsCountriesMap[newClientId]));
  }

  // Reload active tab's client-scoped data
  const activePanel = document.querySelector('.tab-panel.active');
  const tabId = activePanel ? activePanel.id.replace('tab-', '') : '';

  switch (tabId) {
    case 'cvetracker':
      if (typeof loadCvePanel    === 'function') loadCvePanel();
      break;
    case 'intelligence':
      if (typeof loadIntelligence === 'function') loadIntelligence();
      break;
    case 'newsroom':
      if (typeof loadAllPanels   === 'function') loadAllPanels();
      break;
    default:
      break;
  }
  // PIR/RFI/IOC live in intelligence sub-views — always refresh their caches
  if (typeof loadPirs    === 'function') loadPirs();
  if (typeof loadRfis    === 'function') loadRfis();
  if (typeof iocmgmtLoad === 'function') iocmgmtLoad(1);
}

function openLoginModal() {
  _authNeedsAnalyst = false;
  _authNewStyle     = false;
  _authPending      = null;
  document.getElementById('auth-username-input').value = '';
  document.getElementById('auth-password-input').value = '';
  document.getElementById('auth-analyst-input').value  = '';
  document.getElementById('auth-error').style.display  = 'none';
  document.getElementById('auth-analyst-row').style.display = 'none';
  document.getElementById('auth-login-fields').style.display = '';
  document.getElementById('auth-subtitle').textContent = 'Sign in to CTI Nexus.';
  document.getElementById('auth-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  setTimeout(() => document.getElementById('auth-username-input').focus(), 150);
}

function doLogout() {
  fetch('/api/auth/logout', { method: 'POST', headers: _authHeader() }).catch(() => {});
  _jwtClear();
  window.location.href = '/login';
}

// ── Auth Modal ────────────────────────────────────────────────
let _authPending      = null;
let _authNeedsAnalyst = false;
let _authNewStyle     = false;
let _authGateMode     = false;

// Run on page load
_updateHeaderAuth();
if (_CTI_AUTH_REQUIRED && !_jwtValid()) { _showAuthGate(); }
loadPolicy();

function _showAuthGate() {
  _authGateMode     = true;
  _authNeedsAnalyst = false;
  _authNewStyle     = false;
  _authPending      = null;
  document.getElementById('auth-username-input').value = '';
  document.getElementById('auth-password-input').value = '';
  document.getElementById('auth-analyst-input').value  = '';
  document.getElementById('auth-error').style.display  = 'none';
  document.getElementById('auth-analyst-row').style.display   = 'none';
  document.getElementById('auth-login-fields').style.display  = '';
  document.getElementById('auth-subtitle').textContent = 'Sign in to access CTI Nexus.';
  document.getElementById('auth-cancel-btn').style.display = 'none';
  document.getElementById('auth-close-btn').style.display  = 'none';
  const overlay = document.getElementById('auth-overlay');
  overlay.classList.add('open', 'auth-gate');
  document.body.style.overflow = 'hidden';
  setTimeout(() => document.getElementById('auth-username-input').focus(), 150);
}

function _exitAuthGate() {
  _authGateMode = false;
  const overlay = document.getElementById('auth-overlay');
  overlay.classList.remove('open', 'auth-gate');
  document.getElementById('auth-cancel-btn').style.display = '';
  document.getElementById('auth-close-btn').style.display  = '';
  document.body.style.overflow = '';
  _authPending      = null;
  _authNeedsAnalyst = false;
}

function requireTAAuth(fn, opts = {}) {
  const needAnalyst = !!opts.analystName;
  const isNewStyle  = Object.keys(opts).length > 0;
  _authNeedsAnalyst = needAnalyst;
  _authNewStyle     = isNewStyle;

  if (_jwtValid()) {
    // Logged in: never block with modal. If analyst name needed, use logged-in username.
    const analyst = _jwtUsername();
    if (isNewStyle) { fn({ pass: _jwtToken, analyst }); }
    else            { fn(_jwtToken); }
    return;
  }

  // Not authenticated — show bottom-right notification before opening login modal
  _cveToast('Authentication required — please sign in to perform this action.', false);

  _authPending = fn;
  document.getElementById('auth-username-input').value = '';
  document.getElementById('auth-password-input').value = '';
  document.getElementById('auth-analyst-input').value  = '';
  document.getElementById('auth-error').style.display  = 'none';
  document.getElementById('auth-analyst-row').style.display = needAnalyst ? '' : 'none';
  document.getElementById('auth-login-fields').style.display = _jwtValid() ? 'none' : '';
  document.getElementById('auth-subtitle').textContent =
    opts.subtitle || 'Sign in to perform this action.';
  document.getElementById('auth-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  setTimeout(() => {
    document.getElementById(_jwtValid() && needAnalyst ? 'auth-analyst-input' : 'auth-username-input').focus();
  }, 150);
}

async function _authSubmit() {
  const btn = document.querySelector('#auth-overlay .btn-apply');
  const analyst = document.getElementById('auth-analyst-input').value.trim();
  if (_authNeedsAnalyst && !analyst) { _authShowError('Analyst name required.'); return; }

  // If already have valid token, just proceed (analyst-only prompt)
  if (_jwtValid()) {
    const pending = _authPending;
    if (_authNewStyle) {
      if (pending) pending({ pass: _jwtToken, analyst });
    } else {
      closeAuthModal();
      if (pending) pending(_jwtToken);
    }
    return;
  }

  const username = document.getElementById('auth-username-input').value.trim();
  const password = document.getElementById('auth-password-input').value;
  if (!username) { _authShowError('Username required.'); return; }
  if (!password) { _authShowError('Password required.'); return; }

  if (btn) { btn.textContent = 'Signing in…'; btn.disabled = true; }
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      _authShowError(res.status === 401 ? 'Invalid credentials.' : `Server error ${res.status}`);
      return;
    }
    const data = await res.json();
    _jwtToken   = data.access_token;
    _jwtPayload = _jwtDecode(_jwtToken);
    localStorage.setItem('cti_jwt', _jwtToken);
    localStorage.setItem('cti_client_countries', JSON.stringify(data.client_countries || []));
    _updateHeaderAuth();

    document.getElementById('auth-error').style.display = 'none';
    if (_authGateMode) { _exitAuthGate(); } else { closeAuthModal(); }

    if (data.force_pw_change) {
      document.getElementById('force-pw-input').value = '';
      document.getElementById('force-pw-err').style.display = 'none';
      document.getElementById('force-pw-overlay').classList.add('open');
      document.body.style.overflow = 'hidden';
      setTimeout(() => document.getElementById('force-pw-input').focus(), 150);
      return;
    }

    const pending = _authPending;
    if (pending) pending(_jwtToken);
  } catch(e) {
    _authShowError(`Network error: ${e.message}`);
  } finally {
    if (btn) { btn.textContent = 'Sign In'; btn.disabled = false; }
  }
}

function _authShowError(msg) {
  const el = document.getElementById('auth-error');
  el.textContent   = msg;
  el.style.display = '';
}

function _authFailed() {
  fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
  _jwtClear();
  window.location.href = '/login?error=session_expired';
}

function closeAuthModal() {
  if (_authGateMode) return;
  document.getElementById('auth-overlay').classList.remove('open');
  document.body.style.overflow = '';
  _authPending      = null;
  _authNeedsAnalyst = false;
  _authNewStyle     = false;
}

function handleAuthOverlayClick(e) {
  if (_authGateMode) return;
  if (e.target === document.getElementById('auth-overlay')) closeAuthModal();
}

function _cveToast(msg, ok = true) {
  let t = document.getElementById('cve-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'cve-toast';
    t.style.cssText = 'position:fixed;bottom:28px;right:28px;z-index:9999;font-family:"IBM Plex Mono",monospace;font-size:11px;padding:10px 16px;border-radius:4px;transition:opacity .3s';
    document.body.appendChild(t);
  }
  t.textContent     = msg;
  t.style.background = ok ? 'rgba(61,201,175,0.15)' : 'rgba(218,54,51,0.15)';
  t.style.border     = ok ? '1px solid rgba(61,201,175,0.4)' : '1px solid rgba(218,54,51,0.4)';
  t.style.color      = ok ? 'var(--green)' : 'var(--red)';
  t.style.opacity    = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.opacity = '0'; }, 3000);
}

