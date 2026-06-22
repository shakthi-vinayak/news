/* ============================================================
   DevOps & AI Hub — app.js
   Vanilla JS, no build step required.
============================================================ */
'use strict';

// ── Constants ──────────────────────────────────────────────
const PAGE_SIZE     = 20;
const STALE_HOURS   = 6;
const DATA_BASE     = './data/';

// ── State ──────────────────────────────────────────────────
const state = {
  news: {
    all:      [],
    filtered: [],
    page:     1,
  },
  jobs: {
    all:      [],
    filtered: [],
    page:     1,
  },
};

// ── Helpers ────────────────────────────────────────────────
function esc(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('en-US', {
      year:'numeric', month:'short', day:'numeric',
    }).format(new Date(iso));
  } catch { return iso; }
}

function daysSince(iso) {
  if (!iso) return Infinity;
  return (Date.now() - new Date(iso).getTime()) / 864e5;
}

function uniqueSorted(arr) {
  return [...new Set(arr.filter(Boolean))].sort();
}

function populateSelect(sel, values) {
  const current = sel.value;
  while (sel.options.length > 1) sel.remove(1);
  values.forEach(v => {
    const o = document.createElement('option');
    o.value = v; o.textContent = v;
    sel.appendChild(o);
  });
  if (values.includes(current)) sel.value = current;
}

function scoreLabel(score) {
  if (score == null || score === 0) return '';
  return `${(score * 100).toFixed(0)}%`;
}

// ── DOM refs ───────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Theme toggle ───────────────────────────────────────────
(function initTheme() {
  const btn   = $('theme-toggle');
  const html  = document.documentElement;
  const saved = localStorage.getItem('theme');
  if (saved) html.dataset.theme = saved;
  btn.textContent = html.dataset.theme === 'dark' ? '☀️' : '🌙';

  btn.addEventListener('click', () => {
    const next = html.dataset.theme === 'dark' ? 'light' : 'dark';
    html.dataset.theme = next;
    localStorage.setItem('theme', next);
    btn.textContent = next === 'dark' ? '☀️' : '🌙';
  });
})();

// ── Tab switching ──────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false');
    });
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));

    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');
    $(`panel-${btn.dataset.tab}`).classList.remove('hidden');
  });
});

// ── Data loading ───────────────────────────────────────────
async function loadJSON(file) {
  const r = await fetch(`${DATA_BASE}${file}?_=${Date.now()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status} loading ${file}`);
  return r.json();
}

async function bootstrap() {
  try {
    const meta = await loadJSON('meta.json');
    applyMeta(meta);
  } catch (e) {
    $('last-updated').textContent = 'Metadata unavailable';
    $('stale-banner').classList.remove('hidden');
  }

  await Promise.all([loadNews(), loadJobs()]);
}

function applyMeta(meta) {
  if (meta.generated_at) {
    const d    = new Date(meta.generated_at);
    const ageH = (Date.now() - d.getTime()) / 36e5;
    $('last-updated').textContent = `Last updated: ${fmtDate(meta.generated_at)}`;
    if (ageH > STALE_HOURS) {
      $('stale-banner').classList.remove('hidden');
    }
  }
}

// ── NEWS ───────────────────────────────────────────────────
async function loadNews() {
  try {
    const data = await loadJSON('news.json');
    state.news.all = (data.items ?? []).sort(
      (a,b) => new Date(b.published_at) - new Date(a.published_at)
    );
    initNewsFilters();
    applyNewsFilters();
  } catch (e) {
    const el = $('news-error');
    el.textContent = `Failed to load news: ${e.message}`;
    el.classList.remove('hidden');
  }
}

function initNewsFilters() {
  const items = state.news.all;
  const allTags    = items.flatMap(i => i.tags ?? []);
  const allSources = items.map(i => i.source);

  populateSelect($('news-tag-filter'),    uniqueSorted(allTags));
  populateSelect($('news-source-filter'), uniqueSorted(allSources));

  $('news-search')       .addEventListener('input',  debounce(applyNewsFilters, 200));
  $('news-tag-filter')   .addEventListener('change', applyNewsFilters);
  $('news-source-filter').addEventListener('change', applyNewsFilters);
  $('news-date-filter')  .addEventListener('change', applyNewsFilters);
  $('news-reset')        .addEventListener('click',  resetNewsFilters);
}

function applyNewsFilters() {
  const q      = $('news-search').value.trim().toLowerCase();
  const tag    = $('news-tag-filter').value;
  const source = $('news-source-filter').value;
  const days   = Number($('news-date-filter').value) || 0;

  state.news.filtered = state.news.all.filter(item => {
    if (q && !(
      item.title?.toLowerCase().includes(q) ||
      item.summary?.toLowerCase().includes(q)
    )) return false;
    if (tag    && !(item.tags ?? []).includes(tag)) return false;
    if (source && item.source !== source) return false;
    if (days   && daysSince(item.published_at) > days) return false;
    return true;
  });

  state.news.page = 1;
  renderNews();
}

function resetNewsFilters() {
  $('news-search').value        = '';
  $('news-tag-filter').value    = '';
  $('news-source-filter').value = '';
  $('news-date-filter').value   = '';
  applyNewsFilters();
}

function renderNews() {
  const { filtered, page } = state.news;
  const start  = (page - 1) * PAGE_SIZE;
  const slice  = filtered.slice(start, start + PAGE_SIZE);
  const list   = $('news-list');
  const empty  = $('news-empty');
  const stats  = $('news-stats');

  stats.textContent = `${filtered.length} article${filtered.length !== 1 ? 's' : ''}`;

  if (filtered.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    $('news-pagination').innerHTML = '';
    return;
  }

  empty.classList.add('hidden');
  list.innerHTML = slice.map(newsCardHTML).join('');
  renderPagination($('news-pagination'), page, Math.ceil(filtered.length / PAGE_SIZE), p => {
    state.news.page = p;
    renderNews();
    $('panel-news').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

function newsCardHTML(item) {
  const score = scoreLabel(item.relevance_score);
  const tags  = (item.tags ?? []).map(t =>
    `<span class="tag" data-tag="${esc(t)}">${esc(t)}</span>`
  ).join('');

  return `
<article class="news-card" role="listitem">
  <div class="news-card__top">
    <a class="news-card__title" href="${esc(item.url)}" target="_blank" rel="noopener">
      ${esc(item.title)}
    </a>
    ${score ? `<span class="news-card__score">${score}</span>` : ''}
  </div>
  ${item.summary ? `<p class="news-card__summary">${esc(item.summary)}</p>` : ''}
  <div class="news-card__meta">
    <span class="source-badge">${esc(item.source)}</span>
    <span>${fmtDate(item.published_at)}</span>
  </div>
  <div class="news-card__tags">${tags}</div>
</article>`;
}

// ── JOBS ───────────────────────────────────────────────────
async function loadJobs() {
  try {
    const data = await loadJSON('jobs.json');
    state.jobs.all = (data.items ?? []).sort(
      (a,b) => new Date(b.posted_at) - new Date(a.posted_at)
    );
    initJobsFilters();
    applyJobsFilters();
  } catch (e) {
    const el = $('jobs-error');
    el.textContent = `Failed to load jobs: ${e.message}`;
    el.classList.remove('hidden');
  }
}

function initJobsFilters() {
  const items       = state.jobs.all;
  const allCats     = items.map(i => i.category);
  const allSources  = items.map(i => i.source);

  populateSelect($('jobs-category-filter'), uniqueSorted(allCats));
  populateSelect($('jobs-source-filter'),   uniqueSorted(allSources));

  $('jobs-search')          .addEventListener('input',  debounce(applyJobsFilters, 200));
  $('jobs-category-filter') .addEventListener('change', applyJobsFilters);
  $('jobs-source-filter')   .addEventListener('change', applyJobsFilters);
  $('jobs-date-filter')     .addEventListener('change', applyJobsFilters);
  $('jobs-reset')           .addEventListener('click',  resetJobsFilters);
}

function applyJobsFilters() {
  const q      = $('jobs-search').value.trim().toLowerCase();
  const cat    = $('jobs-category-filter').value;
  const source = $('jobs-source-filter').value;
  const days   = Number($('jobs-date-filter').value) || 0;

  state.jobs.filtered = state.jobs.all.filter(item => {
    if (q && !(
      item.title?.toLowerCase().includes(q) ||
      item.company?.toLowerCase().includes(q)
    )) return false;
    if (cat    && item.category !== cat)    return false;
    if (source && item.source   !== source) return false;
    if (days   && daysSince(item.posted_at) > days) return false;
    return true;
  });

  state.jobs.page = 1;
  renderJobs();
}

function resetJobsFilters() {
  $('jobs-search').value            = '';
  $('jobs-category-filter').value   = '';
  $('jobs-source-filter').value     = '';
  $('jobs-date-filter').value       = '';
  applyJobsFilters();
}

function renderJobs() {
  const { filtered, page } = state.jobs;
  const start = (page - 1) * PAGE_SIZE;
  const slice = filtered.slice(start, start + PAGE_SIZE);
  const list  = $('jobs-list');
  const empty = $('jobs-empty');
  const stats = $('jobs-stats');

  stats.textContent = `${filtered.length} job${filtered.length !== 1 ? 's' : ''}`;

  if (filtered.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    $('jobs-pagination').innerHTML = '';
    return;
  }

  empty.classList.add('hidden');
  list.innerHTML = slice.map(jobCardHTML).join('');
  renderPagination($('jobs-pagination'), page, Math.ceil(filtered.length / PAGE_SIZE), p => {
    state.jobs.page = p;
    renderJobs();
    $('panel-jobs').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

function jobCardHTML(item) {
  const score = scoreLabel(item.relevance_score);
  return `
<article class="job-card" role="listitem">
  <div class="job-card__header">
    <div class="job-card__title-block">
      <a class="job-card__title" href="${esc(item.url)}" target="_blank" rel="noopener">
        ${esc(item.title)}
      </a>
      <span class="job-card__company">${esc(item.company)}</span>
    </div>
    ${score ? `<span class="job-card__score">${score}</span>` : ''}
  </div>
  <div class="job-card__meta">
    <span class="source-badge">${esc(item.source)}</span>
    ${item.location ? `<span class="location-badge">📍 ${esc(item.location)}</span>` : ''}
    ${item.category ? `<span class="category-badge">${esc(item.category)}</span>` : ''}
    ${item.salary_range ? `<span class="salary-badge">💰 ${esc(item.salary_range)}</span>` : ''}
    <span>${fmtDate(item.posted_at)}</span>
  </div>
</article>`;
}

// ── Pagination renderer ────────────────────────────────────
function renderPagination(container, current, total, onPage) {
  if (total <= 1) { container.innerHTML = ''; return; }

  const MAX_VISIBLE = 7;
  let pages = [];

  if (total <= MAX_VISIBLE) {
    pages = range(1, total);
  } else {
    pages = [1];
    if (current > 3)       pages.push('…');
    const lo = Math.max(2,      current - 1);
    const hi = Math.min(total-1, current + 1);
    for (let i = lo; i <= hi; i++) pages.push(i);
    if (current < total - 2) pages.push('…');
    pages.push(total);
  }

  container.innerHTML = `
    <button class="page-btn" data-p="${current-1}" ${current===1?'disabled':''}>‹ Prev</button>
    ${pages.map(p => p === '…'
      ? `<span class="page-btn" style="cursor:default;border:none">…</span>`
      : `<button class="page-btn ${p===current?'active':''}" data-p="${p}">${p}</button>`
    ).join('')}
    <button class="page-btn" data-p="${current+1}" ${current===total?'disabled':''}>Next ›</button>
  `;

  container.querySelectorAll('.page-btn[data-p]').forEach(btn => {
    if (btn.disabled) return;
    btn.addEventListener('click', () => onPage(Number(btn.dataset.p)));
  });
}

function range(a, b) {
  const r = [];
  for (let i = a; i <= b; i++) r.push(i);
  return r;
}

// ── Tag click filter shortcut ──────────────────────────────
document.getElementById('news-list').addEventListener('click', e => {
  const tag = e.target.closest('.tag');
  if (!tag) return;
  $('news-tag-filter').value = tag.dataset.tag;
  applyNewsFilters();
});

// ── Debounce ───────────────────────────────────────────────
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ── Boot ───────────────────────────────────────────────────
bootstrap();
