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

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (menu) menu.classList.remove('open');
      if (menuButton) menuButton.setAttribute('aria-expanded', 'false');
      body.classList.remove('menu-open');
    }
  });

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
