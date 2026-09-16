// ── API ───────────────────────────────────────────────────
function getFilters() {
  return {
    search:    document.getElementById('filter-search').value.trim(),
    dateStart: document.getElementById('filter-date-start').value,
    dateEnd:   document.getElementById('filter-date-end').value,
    country:   document.getElementById('filter-country').value,
    industry:  document.getElementById('filter-industry').value,
    actor:     document.getElementById('filter-actor').value,
  };
}

function buildParams({ newsType, forceCountries, page, pageSize } = {}) {
  const f = getFilters();
  const params = new URLSearchParams({ page: page || 1, page_size: pageSize || PAGE_SIZE });
  if (newsType) {
    const types = Array.isArray(newsType) ? newsType : [newsType];
    types.forEach(t => params.append('news_type', t));
  }
  if (f.dateStart) params.set('posted_on_start', f.dateStart);
  if (f.dateEnd)   params.set('posted_on_end',   f.dateEnd);

  // Expand canonical country → all DB variants
  const countries = forceCountries !== undefined
    ? forceCountries
    : f.country ? expandCountry(f.country) : [];
  countries.forEach(c => params.append('country', c));

  if (f.industry) params.append('industry', f.industry);
  if (f.actor)    params.append('threat_actor', f.actor);
  if (f.search)   params.set('search', f.search);
  return params;
}

async function fetchArticles(opts) {
  try {
    const resp = await fetch(`/api/articles?${buildParams(opts)}`);
    if (!resp.ok) throw new Error(resp.statusText);
    return await resp.json();
  } catch (e) {
    console.error('fetchArticles:', e);
    return { articles: [], total: 0 };
  }
}

