// ── AUTO-REFRESH ──────────────────────────────────────────
let _refreshTimer    = null;
let _refreshCountdown = 0;
let _refreshInterval  = 0;

function setAutoRefresh() {
  clearInterval(_refreshTimer);
  _refreshTimer = null;
  const val = parseInt(document.getElementById('refresh-interval').value, 10);
  _refreshInterval  = val;
  _refreshCountdown = val;
  _updateCountdown();
  if (val > 0) {
    _refreshTimer = setInterval(() => {
      _refreshCountdown--;
      if (_refreshCountdown <= 0) {
        _refreshCountdown = _refreshInterval;
        const modalOpen = document.getElementById('modal-overlay').classList.contains('open');
        if (!modalOpen) {
          const activeTab = document.querySelector('.tab-panel.active')?.id;
          if (activeTab === 'tab-dashboard') {
            loadDashboard();
          } else {
            loadAllPanels();
          }
        }
      }
      _updateCountdown();
    }, 1000);
  }
}

function _updateCountdown() {
  const el = document.getElementById('refresh-countdown');
  if (_refreshInterval > 0 && _refreshCountdown > 0) {
    const m = Math.floor(_refreshCountdown / 60);
    const s = _refreshCountdown % 60;
    el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
  } else {
    el.textContent = '';
  }
}

// ── INIT ──────────────────────────────────────────────────
document.getElementById('footer-year').textContent = new Date().getFullYear();

(async () => {
  try {
    // Fetch country groups, filters, and current user's client countries in parallel
    const authHeaders = _jwtToken ? { 'Authorization': 'Bearer ' + _jwtToken } : {};
    const [cgResp, filtersResp, meResp] = await Promise.all([
      fetch('/api/country-groups'),
      fetch('/api/filters'),
      _jwtToken ? fetch('/api/auth/me', { headers: authHeaders }) : Promise.resolve(null),
    ]);

    if (meResp && meResp.ok) {
      const me = await meResp.json();
      if (me.clients_map && typeof me.clients_map === 'object') {
        window._clientsCountriesMap = me.clients_map;
      }
      const activeId = typeof getActiveClientId === 'function' ? getActiveClientId() : null;
      const countries = (activeId && window._clientsCountriesMap?.[activeId])
        || me.client_countries || [];
      localStorage.setItem('cti_client_countries', JSON.stringify(countries));
    }

    // Build country lookup maps from API (single source of truth)
    if (cgResp.ok) {
      const groups = await cgResp.json();
      groups.forEach(({ canonical, variants }) => {
        canonicalToVariants[canonical] = variants;
        variants.forEach(v => { variantToCanonical[v] = canonical; });
      });
    }

    if (filtersResp.ok) {
      const fd = await filtersResp.json();

      const cSel = document.getElementById('filter-country');
      const iSel = document.getElementById('filter-industry');

      normalizeCountryList(fd.countries || []).forEach(c => {
        const o = document.createElement('option');
        o.value = o.textContent = c;
        cSel.appendChild(o);
      });

      (fd.industries || []).forEach(i => {
        const o = document.createElement('option');
        o.value = o.textContent = i;
        iSel.appendChild(o);
      });

      const aSel = document.getElementById('filter-actor');
      (fd.threat_actors || []).forEach(t => {
        const o = document.createElement('option');
        o.value = o.textContent = t;
        aSel.appendChild(o);
      });

      // Default news room date range: last 7 days
      const _todayD = new Date(); const _d7 = new Date(_todayD); _d7.setDate(_todayD.getDate() - 7);
      const _ds = _d7.toISOString().split('T')[0]; const _de = _todayD.toISOString().split('T')[0];
      document.getElementById('filter-date-start').value = _ds; window._defaultDateStart = _ds;
      document.getElementById('filter-date-end').value   = _de; window._defaultDateEnd   = _de;

    }
  } catch (e) { console.error('Init load error:', e); }

  // Dashboard is the default active tab — load both in parallel
  await Promise.all([loadDashboard(), loadAllPanels(), loadSRScoreMap(), loadScraperHealth()]);
})();

