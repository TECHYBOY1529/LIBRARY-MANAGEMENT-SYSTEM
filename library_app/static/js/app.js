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
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
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
});
