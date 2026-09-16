// ── DASHBOARD ─────────────────────────────────────────────

Chart.defaults.font.family = "'IBM Plex Mono', monospace";
Chart.defaults.font.size   = 10;
Chart.defaults.color       = '#8B949E';

const CHART_COLORS = ['#2F81F7','#58A6FF','#DA3633','#3DC9AF','#E3B341','#21262D','#fd79a8','#30363D','#55efc4','#21262D'];

function makeBarChart(id, labels, data, color) {
  if (_charts[id]) _charts[id].destroy();
  const ctx = document.getElementById(id);
  if (!ctx) return;
  _charts[id] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: color || 'rgba(47,129,247,0.25)',
        borderColor:     color || '#2F81F7',
        borderWidth: 1,
        borderRadius: 2,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.x} articles` } } },
      scales: {
        x: { grid: { color: '#30363D' }, ticks: { color: '#8B949E' } },
        y: { grid: { display: false }, ticks: { color: '#E6EDF3', font: { size: 10 } } },
      }
    }
  });
}

function makeDoughnutChart(id, labels, data) {
  if (_charts[id]) _charts[id].destroy();
  const ctx = document.getElementById(id);
  if (!ctx) return;
  _charts[id] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: CHART_COLORS,
        borderColor:     '#161B22',
        borderWidth: 2,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: '#E6EDF3', padding: 12, font: { size: 10 } } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed} articles` } },
      },
      cutout: '60%',
    }
  });
}

function makeLineChart(id, labels, data) {
  if (_charts[id]) _charts[id].destroy();
  const ctx = document.getElementById(id);
  if (!ctx) return;
  _charts[id] = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data,
        borderColor: '#2F81F7',
        backgroundColor: 'rgba(47,129,247,0.06)',
        borderWidth: 1.5,
        pointRadius: 2,
        pointBackgroundColor: '#2F81F7',
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y} articles` } } },
      scales: {
        x: { grid: { color: '#30363D' }, ticks: { color: '#8B949E', maxTicksLimit: 12 } },
        y: { grid: { color: '#30363D' }, ticks: { color: '#8B949E' }, beginAtZero: true },
      }
    }
  });
}

function toTitleCase(str) {
  return str.replace(/\w\S*/g, w => w.charAt(0).toUpperCase() + w.slice(1));
}

async function loadDashboard() {
  try {
    const f = getFilters();
    const params = new URLSearchParams();
    if (f.dateStart) params.set('posted_on_start', f.dateStart);
    if (f.dateEnd)   params.set('posted_on_end',   f.dateEnd);

    // Fetch news stats and TA stats in parallel
    const [dashResp, taResp] = await Promise.all([
      fetch(`/api/dashboard?${params}`),
      fetch('/api/ta/stats'),
    ]);

    if (!dashResp.ok) throw new Error(dashResp.statusText);
    const d = await dashResp.json();

    // ── News Intelligence stat boxes ──
    document.getElementById('ds-total').textContent     = d.total_articles;
    document.getElementById('ds-countries').textContent = d.total_countries;
    document.getElementById('ds-actors').textContent    = d.total_threat_actors;

    // Top Countries (horizontal bar)
    makeBarChart('chart-countries',
      d.top_countries.map(x => toTitleCase(x.name)),
      d.top_countries.map(x => x.count),
      'rgba(47,129,247,0.4)'
    );

    // News Type (doughnut)
    makeDoughnutChart('chart-newstype',
      d.by_news_type.map(x => toTitleCase(x.name)),
      d.by_news_type.map(x => x.count)
    );

    // Timeline (line)
    makeLineChart('chart-timeline',
      d.timeline.map(x => x.date),
      d.timeline.map(x => x.count)
    );

    // Threat Actors (horizontal bar)
    makeBarChart('chart-actors',
      d.top_threat_actors.map(x => toTitleCase(x.name)),
      d.top_threat_actors.map(x => x.count),
      'rgba(218,54,51,0.4)'
    );

    // Industries (horizontal bar)
    makeBarChart('chart-industries',
      d.top_industries.map(x => toTitleCase(x.name)),
      d.top_industries.map(x => x.count),
      'rgba(227,179,65,0.4)'
    );

    // TTPs (horizontal bar)
    makeBarChart('chart-ttps',
      d.top_ttps.map(x => toTitleCase(x.name)),
      d.top_ttps.map(x => x.count),
      'rgba(61,201,175,0.4)'
    );

    // ── Threat Actor Intelligence stat boxes + charts ──
    if (taResp.ok) {
      const ta = await taResp.json();

      document.getElementById('ds-ta-total').textContent   = ta.total_groups;
      document.getElementById('ds-ta-wl').textContent      = ta.total_whitelisted;
      document.getElementById('ds-ta-manual').textContent  = ta.manual_count;
      document.getElementById('ds-ta-innews').textContent  = ta.in_news_count;

      // APT Groups by Source (doughnut)
      makeDoughnutChart('chart-ta-source',
        ta.by_source.map(x => toTitleCase(x.name)),
        ta.by_source.map(x => x.count)
      );

      // Tracked groups appearing in news (horizontal bar)
      if (ta.top_in_news.length) {
        makeBarChart('chart-ta-innews',
          ta.top_in_news.map(x => toTitleCase(x.name)),
          ta.top_in_news.map(x => x.count),
          'rgba(61,201,175,0.4)'
        );
      }
    }

  } catch (e) {
    console.error('Dashboard load error:', e);
  }
}

