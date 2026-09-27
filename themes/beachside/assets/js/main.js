(() => {
  const body = document.body;
  const menuButton = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-menu]');

  const liveButton = document.querySelector('[data-watch-live]');
  if (liveButton) {
    const clock = new Intl.DateTimeFormat('en-US', {
      timeZone: liveButton.dataset.liveTimeZone,
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    });
    const minutes = (time) => {
      const [hour, minute] = time.split(':').map(Number);
      return hour * 60 + minute;
    };
    const windows = JSON.parse(liveButton.dataset.liveWindows).map((window) => ({
      start: minutes(window.start),
      end: minutes(window.end),
    }));
    const updateLiveButton = () => {
      const now = Object.fromEntries(clock.formatToParts(new Date()).map(({ type, value }) => [type, value]));
      const time = Number(now.hour) * 60 + Number(now.minute);
      liveButton.hidden = !(now.weekday === 'Sun' && windows.some(({ start, end }) => time >= start && time < end));
    };
    updateLiveButton();
    // Keep open pages current and recheck immediately when a sleeping tab returns.
    window.setInterval(updateLiveButton, 1000);
    document.addEventListener('visibilitychange', updateLiveButton);
    window.addEventListener('pageshow', updateLiveButton);
  }

  if (menuButton && menu) {
    menuButton.addEventListener('click', () => {
      const open = menuButton.getAttribute('aria-expanded') !== 'true';
      menuButton.setAttribute('aria-expanded', String(open));
      menu.classList.toggle('open', open);
      body.classList.toggle('menu-open', open);
    });
  }

  const announcement = document.querySelector('[data-announcement]');
  const announcementClose = document.querySelector('[data-announcement-close]');
  if (announcement && announcementClose) {
    const announcementDismissalKey = 'beachside-announcement-dismissed';
    if (sessionStorage.getItem(announcementDismissalKey) === 'true') {
      announcement.hidden = true;
      body.classList.remove('has-announcement');
    }

    announcementClose.addEventListener('click', () => {
      sessionStorage.setItem(announcementDismissalKey, 'true');
      announcement.hidden = true;
      body.classList.remove('has-announcement');
    });
  }

  const dialog = document.querySelector('[data-search-dialog]');
  const searchInput = document.querySelector('[data-search-input]');
  const results = document.querySelector('[data-search-results]');
  let searchIndex;

  const closeSearch = () => {
    if (!dialog) return;
    dialog.hidden = true;
    body.classList.remove('dialog-open');
  };

  document.querySelectorAll('[data-search-open]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (!dialog || !searchInput) return;
      if (menu) menu.classList.remove('open');
      if (menuButton) menuButton.setAttribute('aria-expanded', 'false');
      body.classList.remove('menu-open');
      dialog.hidden = false;
      body.classList.add('dialog-open');
      searchInput.focus();
      if (!searchIndex) {
        try {
          const response = await fetch('/index.json');
          searchIndex = await response.json();
        } catch (_) {
          searchIndex = [];
        }
        // A visitor may type before the index finishes loading.
        searchInput.dispatchEvent(new Event('input'));
      }
    });
  });

  document.querySelectorAll('[data-search-close]').forEach((button) => button.addEventListener('click', closeSearch));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeSearch();
      if (menu) menu.classList.remove('open');
      if (menuButton) menuButton.setAttribute('aria-expanded', 'false');
      body.classList.remove('menu-open');
    }
  });

  if (searchInput && results) {
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.trim().toLowerCase();
      results.replaceChildren();
      if (query.length < 2) return;
      const matches = (searchIndex || []).filter((item) => `${item.title} ${item.description}`.toLowerCase().includes(query)).slice(0, 8);
      if (!matches.length) {
        const empty = document.createElement('p');
        empty.className = 'search-empty';
        empty.textContent = 'No matching pages found.';
        results.append(empty);
        return;
      }
      matches.forEach((item) => {
        const link = document.createElement('a');
        const title = document.createElement('strong');
        const description = document.createElement('span');
        link.className = 'search-result';
        link.href = item.url;
        title.textContent = item.title;
        description.textContent = item.description || '';
        link.append(title, description);
        results.append(link);
      });
    });
  }

  document.querySelectorAll('.dg-card--devo').forEach((devotions) => {
    const tabs = [...devotions.querySelectorAll('.dg-devo-tab')];
    const panels = [...devotions.querySelectorAll('.dg-devo-panel')];
    tabs.forEach((tab) => {
      tab.type = 'button';
      tab.setAttribute('role', 'tab');
      const panel = panels.find((item) => item.id === `devo-${tab.dataset.day || ''}`);
      if (panel) {
        tab.setAttribute('aria-controls', panel.id);
        panel.setAttribute('role', 'tabpanel');
      }
      tab.setAttribute('aria-selected', String(tab.classList.contains('active')));
      tab.addEventListener('click', () => {
        tabs.forEach((item) => {
          const active = item === tab;
          item.classList.toggle('active', active);
          item.setAttribute('aria-selected', String(active));
        });
        panels.forEach((item) => item.classList.toggle('active', item.id === `devo-${tab.dataset.day}`));
      });
    });
  });

  const guideFilters = [...document.querySelectorAll('[data-guide-filter]')];
  const guideItems = [...document.querySelectorAll('[data-guide-item]')];
  const guideEmpty = document.querySelector('[data-guide-empty]');
  if (guideFilters.length && guideItems.length) {
    const applyGuideFilter = (series) => {
      let visible = 0;
      guideItems.forEach((item) => {
        const show = !series || item.dataset.guideSeries === series;
        item.hidden = !show;
        if (show) visible += 1;
      });
      guideFilters.forEach((button) => {
        const active = button.dataset.guideFilter === series;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      if (guideEmpty) guideEmpty.hidden = visible !== 0;
    };
    const initialSeries = new URL(window.location.href).searchParams.get('series') || '';
    applyGuideFilter(initialSeries);
    guideFilters.forEach((button) => button.addEventListener('click', () => {
      const series = button.dataset.guideFilter || '';
      const url = new URL(window.location.href);
      if (series) url.searchParams.set('series', series);
      else url.searchParams.delete('series');
      window.history.replaceState({}, '', url);
      applyGuideFilter(series);
    }));
  }
})();
