document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('menuToggle');
  const backdrop = document.getElementById('sidebarBackdrop');

  const closeNavigation = () => {
    if (!sidebar || !toggle) return;
    sidebar.classList.remove('open');
    document.body.classList.remove('nav-open');
    toggle.setAttribute('aria-expanded', 'false');
  };
  const openNavigation = () => {
    if (!sidebar || !toggle) return;
    sidebar.classList.add('open');
    document.body.classList.add('nav-open');
    toggle.setAttribute('aria-expanded', 'true');
  };

  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      sidebar.classList.contains('open') ? closeNavigation() : openNavigation();
    });
    sidebar.querySelectorAll('a').forEach(link => link.addEventListener('click', closeNavigation));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeNavigation();
    });
  }
  if (backdrop) backdrop.addEventListener('click', closeNavigation);

  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (form.dataset.confirmedOnce === 'true') {
        delete form.dataset.confirmedOnce;
        return;
      }
      event.preventDefault();
      const dialog = document.getElementById('confirmDialog');
      if (!dialog || typeof dialog.showModal !== 'function') {
        if (window.confirm(form.dataset.confirm)) form.requestSubmit();
        return;
      }
      const message = document.getElementById('confirmMessage');
      if (message) message.textContent = form.dataset.confirm;
      dialog.addEventListener('close', function resumeSubmit() {
        dialog.removeEventListener('close', resumeSubmit);
        if (dialog.returnValue === 'confirm') {
          form.dataset.confirmedOnce = 'true';
          form.requestSubmit();
        }
      });
      dialog.showModal();
    });
  });

  const root = document.documentElement;
  const preferenceKey = 'campus-library-prefs-' + (document.body.dataset.userId || 'guest');
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem(preferenceKey) || '{}'); } catch (_) { preferences = {}; }
  const themeSelect = document.getElementById('themePreference');
  const fontSelect = document.getElementById('fontPreference');
  const contrastToggle = document.getElementById('contrastPreference');
  if (themeSelect) themeSelect.value = ['forest', 'light', 'dark'].includes(preferences.theme) ? preferences.theme : 'forest';
  if (fontSelect) fontSelect.value = ['normal', 'large', 'larger'].includes(preferences.fontScale) ? preferences.fontScale : 'normal';
  if (contrastToggle) contrastToggle.checked = Boolean(preferences.contrast);
  const savePreferences = () => {
    preferences = {
      theme: themeSelect?.value || 'forest',
      fontScale: fontSelect?.value || 'normal',
      contrast: Boolean(contrastToggle?.checked)
    };
    root.dataset.theme = preferences.theme;
    root.dataset.fontScale = preferences.fontScale;
    root.dataset.contrast = preferences.contrast ? 'high' : 'normal';
    try { localStorage.setItem(preferenceKey, JSON.stringify(preferences)); } catch (_) { /* Preferences remain active for this page. */ }
  };
  [themeSelect, fontSelect, contrastToggle].filter(Boolean).forEach(control => control.addEventListener('change', savePreferences));

  const search = document.getElementById('globalSearch');
  const paletteDialog = document.getElementById('paletteDialog');
  const paletteSearch = document.getElementById('paletteSearch');
  const paletteClose = document.getElementById('paletteClose');
  const paletteList = document.getElementById('paletteList');

  const openPalette = () => {
    if (!paletteDialog || typeof paletteDialog.showModal !== 'function') return;
    if (paletteDialog.open) return;
    paletteDialog.showModal();
    if (paletteSearch) {
      paletteSearch.value = '';
      filterPalette('');
      setTimeout(() => paletteSearch.focus(), 50);
    }
  };

  const closePalette = () => {
    if (paletteDialog && paletteDialog.open) paletteDialog.close();
  };

  if (paletteClose) paletteClose.addEventListener('click', closePalette);
  if (paletteDialog) {
    paletteDialog.addEventListener('click', e => {
      if (e.target === paletteDialog) closePalette();
    });
  }

  const filterPalette = query => {
    if (!paletteList) return;
    const term = query.toLowerCase().trim();
    const items = paletteList.querySelectorAll('.palette-item');
    items.forEach(item => {
      const text = item.textContent.toLowerCase();
      item.style.display = text.includes(term) ? 'flex' : 'none';
    });
  };

  if (paletteSearch) {
    paletteSearch.addEventListener('input', e => filterPalette(e.target.value));
  }
  let shortcutPrefix = false;
  let shortcutTimer;
  document.addEventListener('keydown', event => {
    const target = event.target;
    const typing = target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (paletteDialog) {
        paletteDialog.open ? closePalette() : openPalette();
      } else if (search) {
        search.focus();
        search.select();
      }
      return;
    }
    if (typing || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === '/' && search) { event.preventDefault(); search.focus(); return; }
    if (shortcutPrefix && event.key.toLowerCase() === 'd') window.location.assign('/dashboard');
    if (shortcutPrefix && event.key.toLowerCase() === 'c') window.location.assign('/library/books');
    if (shortcutPrefix && event.key.toLowerCase() === 'l') window.location.assign('/library/loans');
    shortcutPrefix = event.key.toLowerCase() === 'g';
    clearTimeout(shortcutTimer);
    if (shortcutPrefix) shortcutTimer = setTimeout(() => { shortcutPrefix = false; }, 900);
  });

  document.querySelectorAll('.sortable-table thead th').forEach((header, columnIndex) => {
    if (['Action', 'Update', ''].includes(header.textContent.trim())) return;
    header.tabIndex = 0;
    header.setAttribute('role', 'button');
    header.setAttribute('aria-label', 'Sort this page by ' + header.textContent.trim());
    const sort = () => {
      const table = header.closest('table');
      const body = table.querySelector('tbody');
      const ascending = header.dataset.sortDirection !== 'asc';
      [...body.rows].sort((a, b) => {
        const left = a.cells[columnIndex]?.innerText.trim().toLocaleLowerCase() || '';
        const right = b.cells[columnIndex]?.innerText.trim().toLocaleLowerCase() || '';
        return left.localeCompare(right, undefined, { numeric: true }) * (ascending ? 1 : -1);
      }).forEach(row => body.appendChild(row));
      table.querySelectorAll('thead th').forEach(item => {
        delete item.dataset.sortDirection;
        item.removeAttribute('aria-sort');
      });
      header.dataset.sortDirection = ascending ? 'asc' : 'desc';
      header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
    };
    header.addEventListener('click', sort);
    header.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        sort();
      }
    });
  });

  const catalogButtons = document.querySelectorAll('[data-catalog-view]');
  const catalogPanels = document.querySelectorAll('[data-catalog-panel]');
  if (catalogButtons.length && catalogPanels.length) {
    const viewKey = 'campus-library-catalog-view-' + (document.body.dataset.userId || 'guest');
    let activeView = 'grid';
    try {
      const storedView = localStorage.getItem(viewKey);
      if (storedView === 'table') activeView = storedView;
    } catch (_) { /* Keep the default card view if storage is unavailable. */ }
    const setCatalogView = view => {
      activeView = view === 'table' ? 'table' : 'grid';
      catalogPanels.forEach(panel => { panel.hidden = panel.dataset.catalogPanel !== activeView; });
      catalogButtons.forEach(button => {
        const selected = button.dataset.catalogView === activeView;
        button.classList.toggle('is-active', selected);
        button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      });
      try { localStorage.setItem(viewKey, activeView); } catch (_) { /* View selection still works for this page. */ }
    };
    catalogButtons.forEach(button => button.addEventListener('click', () => setCatalogView(button.dataset.catalogView)));
    setCatalogView(activeView);
  }
});
