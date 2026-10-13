document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('menuToggle');
  if (toggle && sidebar) toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', event => {
    if (sidebar && sidebar.classList.contains('open') && !sidebar.contains(event.target) && !toggle.contains(event.target)) sidebar.classList.remove('open');
  });
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  document.querySelectorAll('.clean-table thead th').forEach((header, columnIndex) => {
    if (header.textContent.trim() === 'Action' || header.textContent.trim() === 'Update' || header.textContent.trim() === '') return;
    header.tabIndex = 0;
    header.setAttribute('role', 'button');
    header.setAttribute('aria-label', `Sort by ${header.textContent.trim()}`);
    const sort = () => {
      const table = header.closest('table');
      const body = table.querySelector('tbody');
      const ascending = header.dataset.sortDirection !== 'asc';
      [...body.rows].sort((a, b) => {
        const left = a.cells[columnIndex]?.innerText.trim().toLocaleLowerCase() || '';
        const right = b.cells[columnIndex]?.innerText.trim().toLocaleLowerCase() || '';
        return left.localeCompare(right, undefined, { numeric: true }) * (ascending ? 1 : -1);
      }).forEach(row => body.appendChild(row));
      table.querySelectorAll('thead th').forEach(item => { delete item.dataset.sortDirection; item.removeAttribute('aria-sort'); });
      header.dataset.sortDirection = ascending ? 'asc' : 'desc';
      header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
    };
    header.addEventListener('click', sort);
    header.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); sort(); } });
  });
});
