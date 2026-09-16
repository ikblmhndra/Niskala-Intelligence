const API = "/api";

let currentPage = 1;
const pageSize = 20;

// DOM refs
const grid = document.getElementById("articles-grid");
const articleCount = document.getElementById("article-count");
const pagination = document.getElementById("pagination");
const pageInfo = document.getElementById("page-info");
const btnPrev = document.getElementById("btn-prev");
const btnNext = document.getElementById("btn-next");
const btnClear = document.getElementById("btn-clear");
const emptyState = document.getElementById("empty-state");

const filterDateStart = document.getElementById("filter-date-start");
const filterDateEnd = document.getElementById("filter-date-end");
const filterIndustry = document.getElementById("filter-industry");
const filterCountry = document.getElementById("filter-country");
const filterSource = document.getElementById("filter-source");
const filterNewsType = document.getElementById("filter-news-type");

// Colors for tags
const tagColors = {
  industry: { bg: "bg-blue-900/50", text: "text-blue-300", border: "border-blue-700" },
  country: { bg: "bg-emerald-900/50", text: "text-emerald-300", border: "border-emerald-700" },
  actor: { bg: "bg-red-900/50", text: "text-red-300", border: "border-red-700" },
  ttp: { bg: "bg-purple-900/50", text: "text-purple-300", border: "border-purple-700" },
  source: { bg: "bg-amber-900/50", text: "text-amber-300", border: "border-amber-700" },
  newsType: { bg: "bg-cyan-900/50", text: "text-cyan-300", border: "border-cyan-700" },
};

function makePill(text, colorKey) {
  const c = tagColors[colorKey];
  return `<span class="inline-block px-2 py-0.5 text-xs rounded border ${c.bg} ${c.text} ${c.border}">${escapeHtml(text)}</span>`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function buildQueryString() {
  const params = new URLSearchParams();
  params.set("page", currentPage);
  params.set("page_size", pageSize);

  if (filterDateStart.value) params.set("posted_on_start", filterDateStart.value);
  if (filterDateEnd.value) params.set("posted_on_end", filterDateEnd.value);

  for (const opt of filterIndustry.selectedOptions) {
    params.append("industry", opt.value);
  }
  for (const opt of filterCountry.selectedOptions) {
    params.append("country", opt.value);
  }
  for (const opt of filterSource.selectedOptions) {
    params.append("source", opt.value);
  }
  for (const opt of filterNewsType.selectedOptions) {
    params.append("news_type", opt.value);
  }

  return params.toString();
}

function renderArticles(data) {
  const { articles, total, page, page_size } = data;

  articleCount.textContent = `${total} article${total !== 1 ? "s" : ""}`;

  if (articles.length === 0) {
    grid.innerHTML = "";
    emptyState.classList.remove("hidden");
    pagination.classList.add("hidden");
    return;
  }

  emptyState.classList.add("hidden");

  grid.innerHTML = articles
    .map((a) => {
      const industriesPills = a.impacted_industries
        .filter((i) => i)
        .map((i) => makePill(i, "industry"))
        .join(" ");

      const countriesPills = a.mentioned_countries
        .filter((c) => c)
        .map((c) => makePill(c, "country"))
        .join(" ");

      const actorPills = a.threat_actors
        .filter((t) => t)
        .map((t) => makePill(t, "actor"))
        .join(" ");

      const ttpPills = a.ttps
        .map((t) => makePill(`${t.id} - ${t.name}`, "ttp"))
        .join(" ");

      return `
        <article class="bg-gray-900 border border-gray-800 rounded-lg p-5 hover:border-gray-600 transition">
          <div class="flex flex-wrap items-start justify-between gap-2 mb-2">
            <a href="${escapeHtml(a.url)}" target="_blank" rel="noopener"
               class="text-base font-semibold text-gray-100 hover:text-cyan-400 transition leading-snug flex-1">
              ${escapeHtml(a.title)}
            </a>
            ${makePill(a.news_type, "newsType")}
          </div>

          <div class="flex flex-wrap items-center gap-3 text-xs text-gray-500 mb-3">
            ${makePill(a.source, "source")}
            <span>${escapeHtml(a.posted_on)}</span>
            <span>${escapeHtml(a.week)} &middot; ${escapeHtml(a.month)} ${a.year}</span>
          </div>

          ${industriesPills ? `<div class="flex flex-wrap gap-1.5 mb-2"><span class="text-xs text-gray-600 mr-1">Industries:</span>${industriesPills}</div>` : ""}
          ${countriesPills ? `<div class="flex flex-wrap gap-1.5 mb-2"><span class="text-xs text-gray-600 mr-1">Countries:</span>${countriesPills}</div>` : ""}
          ${actorPills ? `<div class="flex flex-wrap gap-1.5 mb-2"><span class="text-xs text-gray-600 mr-1">Threat Actors:</span>${actorPills}</div>` : ""}
          ${ttpPills ? `<div class="flex flex-wrap gap-1.5"><span class="text-xs text-gray-600 mr-1">TTPs:</span>${ttpPills}</div>` : ""}
        </article>
      `;
    })
    .join("");

  // Pagination
  const totalPages = Math.ceil(total / page_size);
  if (totalPages > 1) {
    pagination.classList.remove("hidden");
    pageInfo.textContent = `Page ${page} of ${totalPages}`;
    btnPrev.disabled = page <= 1;
    btnNext.disabled = page >= totalPages;
  } else {
    pagination.classList.add("hidden");
  }
}

async function fetchArticles() {
  const qs = buildQueryString();
  const res = await fetch(`${API}/articles?${qs}`);
  const data = await res.json();
  renderArticles(data);
}

async function fetchFilters() {
  const res = await fetch(`${API}/filters`);
  const data = await res.json();

  populateSelect(filterIndustry, data.industries);
  populateSelect(filterCountry, data.countries);
  populateSelect(filterSource, data.sources);
  populateSelect(filterNewsType, data.news_types);

  if (data.date_range.min) filterDateStart.min = data.date_range.min;
  if (data.date_range.max) filterDateEnd.max = data.date_range.max;
}

function populateSelect(el, items) {
  el.innerHTML = items
    .map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`)
    .join("");
}

function onFilterChange() {
  currentPage = 1;
  fetchArticles();
}

// Event listeners
filterDateStart.addEventListener("change", onFilterChange);
filterDateEnd.addEventListener("change", onFilterChange);
filterIndustry.addEventListener("change", onFilterChange);
filterCountry.addEventListener("change", onFilterChange);
filterSource.addEventListener("change", onFilterChange);
filterNewsType.addEventListener("change", onFilterChange);

btnPrev.addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage--;
    fetchArticles();
  }
});

btnNext.addEventListener("click", () => {
  currentPage++;
  fetchArticles();
});

btnClear.addEventListener("click", () => {
  filterDateStart.value = "";
  filterDateEnd.value = "";
  filterIndustry.selectedIndex = -1;
  filterCountry.selectedIndex = -1;
  filterSource.selectedIndex = -1;
  filterNewsType.selectedIndex = -1;
  for (const sel of [filterIndustry, filterCountry, filterSource, filterNewsType]) {
    for (const opt of sel.options) opt.selected = false;
  }
  currentPage = 1;
  fetchArticles();
});

// Init
fetchFilters().then(() => fetchArticles());
