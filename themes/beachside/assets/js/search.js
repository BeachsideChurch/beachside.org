const page = document.querySelector('[data-search-page]');
const form = page.querySelector('form');
const input = form.elements.q;
const typeFilter = form.elements.type;
const sortOrder = form.elements.sort;
const categories = ['all', 'messages', 'guides', 'ministries', 'events', 'other'];
const status = page.querySelector('[role="status"]');
const results = page.querySelector('[data-search-results]');
const more = page.querySelector('[data-search-more]');
const pageSize = 10;
let library;
let matches = [];
let shown = 0;
let generation = 0;
let timer;

const resultTypes = {
  message: { label: 'Message', icon: 'play', tone: 'message' },
  series: { label: 'Message Series', icon: 'play', tone: 'message' },
  messages: { label: 'Messages', icon: 'play', tone: 'message' },
  guide: { label: 'Discipleship Guide', icon: 'book', tone: 'guide' },
  guides: { label: 'Discipleship Guides', icon: 'book', tone: 'guide' },
  ministry: { label: 'Ministry', icon: 'people', tone: 'ministry' },
  events: { label: 'Events', icon: 'calendar', tone: 'events' },
  engage: { label: 'Next Steps', icon: 'people', tone: 'ministry' },
  about: { label: 'About Beachside', icon: 'home', tone: 'page' },
  home: { label: 'Home', icon: 'home', tone: 'page' },
  page: { label: 'Page', icon: 'page', tone: 'page' },
};
const iconPaths = {
  play: 'M8 5v14l11-7Z',
  book: 'M12 5v15M12 5C9 3 5 3 2 4v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Z',
  people: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  calendar: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z',
  home: 'm3 10 9-7 9 7v11h-6v-7H9v7H3Z',
  page: 'M14 2H4v20h16V8ZM14 2v6h6M8 12h8M8 16h8',
};

function resultBadges(meta) {
  const type = Object.hasOwn(resultTypes, meta.type) ? resultTypes[meta.type] : resultTypes.page;
  const badges = document.createElement('div');
  badges.className = 'site-search-badges';
  const badge = document.createElement('span');
  badge.className = `site-search-badge site-search-badge--${type.tone}`;
  const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  icon.setAttribute('viewBox', '0 0 24 24');
  icon.setAttribute('aria-hidden', 'true');
  icon.setAttribute('focusable', 'false');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', iconPaths[type.icon]);
  icon.append(path);
  badge.append(icon, type.label);
  badges.append(badge);
  if (meta.series && ['message', 'series', 'guide'].includes(meta.type)) {
    const series = document.createElement('span');
    series.className = 'site-search-badge site-search-badge--series';
    series.textContent = meta.series;
    series.title = `Series: ${meta.series}`;
    badges.append(series);
  }
  return badges;
}

function excerptNode(excerpt) {
  // Keep Pagefind's highlights, but never insert indexed HTML into the page.
  const parsed = new DOMParser().parseFromString(excerpt, 'text/html');
  const paragraph = document.createElement('p');
  function append(source, target) {
    for (const child of source.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) target.append(child.textContent);
      else if (child.nodeName === 'MARK') {
        const mark = document.createElement('mark');
        mark.textContent = child.textContent;
        target.append(mark);
      } else append(child, target);
    }
  }
  append(parsed.body, paragraph);
  return paragraph;
}

async function loadMore(id) {
  more.disabled = true;
  try {
    const batch = await Promise.all(matches.slice(shown, shown + pageSize).map(result => result.data()));
    if (id !== generation) return;
    for (const result of batch) {
      const url = new URL(result.url, location.href);
      if (url.origin !== location.origin) continue;
      const item = document.createElement('li');
      const heading = document.createElement('h2');
      const link = document.createElement('a');
      link.href = url.href;
      link.textContent = result.meta.title || url.pathname;
      heading.append(link);
      item.append(resultBadges(result.meta), heading);
      if (/^\d{4}-\d{2}-\d{2}$/.test(result.meta.date || '')) {
        const date = document.createElement('time');
        date.className = 'site-search-date';
        date.dateTime = result.meta.date;
        date.textContent = new Date(`${result.meta.date}T00:00:00Z`).toLocaleDateString('en-US', {
          year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC',
        });
        item.append(date);
      }
      item.append(excerptNode(result.excerpt || ''));
      results.append(item);
    }
    shown += batch.length;
    more.hidden = shown >= matches.length;
    const query = input.value.trim();
    status.textContent = `${matches.length} ${matches.length === 1 ? 'result' : 'results'}${query ? ` for “${query}”` : ''}. Showing ${shown}.`;
  } finally {
    if (id === generation) more.disabled = false;
  }
}

function showError(id) {
  if (id !== generation) return;
  status.textContent = 'Search is temporarily unavailable. Please try again or browse the links below.';
  more.hidden = true;
  results.removeAttribute('aria-busy');
}

async function search(id) {
  const query = input.value.trim();
  const category = typeFilter.value;
  const newest = sortOrder.value === 'newest';
  if (!query && category === 'all' && !newest) return;
  try {
    // Load the search engine only when someone searches, and allow retries.
    if (!library) library = import(page.dataset.pagefindUrl).catch(error => { library = null; throw error; });
    const pagefind = await library;
    if (id !== generation) return;
    const options = {};
    if (category !== 'all') options.filters = { category };
    if (newest) options.sort = { date: 'desc' };
    const response = await pagefind.search(query || null, options);
    if (id !== generation) return;
    matches = response.results;
    if (!matches.length) status.textContent = query
      ? `No results for “${query}” with these filters. Try another word or content type.`
      : 'No results in this content type. Try another content type.';
    else await loadMore(id);
  } catch (error) {
    showError(id);
  } finally {
    if (id === generation) results.removeAttribute('aria-busy');
  }
}

function schedule(delay = 200) {
  clearTimeout(timer);
  const id = ++generation;
  const query = input.value.trim();
  const active = Boolean(query || typeFilter.value !== 'all' || sortOrder.value === 'newest');
  const url = new URL(location.href);
  if (query) url.searchParams.set('q', query);
  else url.searchParams.delete('q');
  if (typeFilter.value !== 'all') url.searchParams.set('type', typeFilter.value);
  else url.searchParams.delete('type');
  if (sortOrder.value === 'newest') url.searchParams.set('sort', 'newest');
  else url.searchParams.delete('sort');
  history.replaceState(null, '', url);
  matches = [];
  shown = 0;
  results.replaceChildren();
  more.hidden = true;
  more.disabled = false;
  results.setAttribute('aria-busy', String(active));
  status.textContent = active ? 'Searching…' : 'Enter a word or phrase to search Beachside.';
  if (active) timer = setTimeout(() => search(id), delay);
}

input.addEventListener('input', () => schedule());
form.addEventListener('change', event => {
  if (event.target.name === 'type' || event.target.name === 'sort') schedule(0);
});
form.addEventListener('submit', event => { event.preventDefault(); schedule(0); });
more.addEventListener('click', () => {
  const id = generation;
  loadMore(id).catch(() => showError(id));
});
function restoreControls() {
  const params = new URL(location.href).searchParams;
  input.value = params.get('q') || '';
  typeFilter.value = categories.includes(params.get('type')) ? params.get('type') : 'all';
  sortOrder.value = params.get('sort') === 'newest' ? 'newest' : 'relevance';
}
window.addEventListener('popstate', () => { restoreControls(); schedule(0); });
restoreControls();
schedule(0);
