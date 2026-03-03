/* PaperStore — tag management page */

function initTagsPage() {
  const tagList = document.getElementById('tag-list');
  const tagCount = document.getElementById('tag-count');
  const emptyMsg = document.getElementById('empty-msg');
  const sortSelect = document.getElementById('sort-select');

  let tags = []; // [{name, count}]

  async function loadTags() {
    try {
      const res = await fetch(`${API}/tags/with-counts`);
      const data = await res.json();
      tags = data.tags || [];
      render();
    } catch {
      tagList.innerHTML = '<li style="color:#dc2626;font-size:0.9rem">Failed to load tags.</li>';
    }
  }

  function sorted() {
    const order = sortSelect.value;
    return [...tags].sort((a, b) =>
      order === 'count'
        ? b.count - a.count || a.name.localeCompare(b.name)
        : a.name.localeCompare(b.name)
    );
  }

  function render() {
    const list = sorted();
    const max = list.length ? Math.max(...list.map((t) => t.count), 1) : 1;

    tagCount.textContent = `${tags.length} tag${tags.length !== 1 ? 's' : ''}`;
    emptyMsg.hidden = tags.length > 0;
    tagList.innerHTML = '';

    for (const tag of list) {
      const pct = Math.round((tag.count / max) * 100);
      const li = document.createElement('li');
      li.className = 'tag-row';
      li.dataset.name = tag.name;
      li.innerHTML = `
        <span class="tag-name">${escapeHtml(tag.name)}</span>
        <div class="tag-bar-wrap"><div class="tag-bar" style="width:${pct}%"></div></div>
        <span class="tag-count">${tag.count} paper${tag.count !== 1 ? 's' : ''}</span>
        <button class="merge-btn" aria-label="Merge tag ${escapeHtml(tag.name)}" title="Merge into…">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3"/><polyline points="16 3 12 7 8 3"/></svg>
        </button>
        <button class="delete-btn" aria-label="Delete tag ${escapeHtml(tag.name)}" title="Delete tag">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
        </button>
      `;
      li.querySelector('.merge-btn').addEventListener('click', (e) => { e.stopPropagation(); startMerge(tag.name, li); });
      li.querySelector('.delete-btn').addEventListener('click', () => deleteTag(tag.name, li));
      tagList.appendChild(li);
    }
  }

  async function deleteTag(name, li) {
    li.classList.add('deleting');
    try {
      const res = await fetch(`${API}/tags/${encodeURIComponent(name)}`, { method: 'DELETE' });
      if (res.ok || res.status === 404) {
        tags = tags.filter((t) => t.name !== name);
        render();
      } else {
        li.classList.remove('deleting');
      }
    } catch {
      li.classList.remove('deleting');
    }
  }

  function startMerge(name, li) {
    // Replace bar+count with an inline picker input
    const barWrap = li.querySelector('.tag-bar-wrap');
    const countSpan = li.querySelector('.tag-count');
    barWrap.hidden = true;
    countSpan.hidden = true;

    const picker = document.createElement('div');
    picker.className = 'merge-picker';
    picker.innerHTML = `
      <input type="text" placeholder="Merge into…" autocomplete="off" />
      <div class="merge-dropdown" hidden></div>
    `;
    // Insert after tag-name
    li.querySelector('.tag-name').after(picker);

    const input = picker.querySelector('input');
    const dropdown = picker.querySelector('.merge-dropdown');

    function cancel() {
      picker.remove();
      barWrap.hidden = false;
      countSpan.hidden = false;
    }

    function showDropdown(query) {
      const q = query.toLowerCase();
      const filtered = tags.filter((t) => t.name !== name && (!q || t.name.toLowerCase().includes(q)));
      if (!filtered.length) { dropdown.hidden = true; return; }
      dropdown.innerHTML = filtered.map((t) =>
        `<div data-name="${escapeHtml(t.name)}">${escapeHtml(t.name)} <span style="color:#94a3b8;font-size:0.75rem">${t.count}</span></div>`
      ).join('');
      dropdown.querySelectorAll('div').forEach((el) => {
        el.addEventListener('mousedown', (e) => { e.preventDefault(); doMerge(name, el.dataset.name, li, picker, barWrap, countSpan); });
      });
      dropdown.hidden = false;
    }

    input.addEventListener('input', () => showDropdown(input.value));
    input.addEventListener('focus', () => showDropdown(input.value));
    input.addEventListener('keydown', (e) => {
      const items = [...dropdown.querySelectorAll('div')];
      const hi = dropdown.querySelector('.highlighted');
      let idx = items.indexOf(hi);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (idx < items.length - 1) { hi && hi.classList.remove('highlighted'); items[idx + 1].classList.add('highlighted'); }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (idx > 0) { hi && hi.classList.remove('highlighted'); items[idx - 1].classList.add('highlighted'); }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (hi) doMerge(name, hi.dataset.name, li, picker, barWrap, countSpan);
      } else if (e.key === 'Escape') {
        cancel();
      }
    });
    input.addEventListener('blur', () => { setTimeout(cancel, 150); });

    input.focus();
    showDropdown('');
  }

  async function doMerge(source, target, li, picker, barWrap, countSpan) {
    picker.remove();
    li.classList.add('deleting');
    try {
      const res = await fetch(`${API}/tags/${encodeURIComponent(source)}/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ into: target }),
      });
      if (res.ok || res.status === 204) {
        const sourceTag = tags.find((t) => t.name === source);
        const targetTag = tags.find((t) => t.name === target);
        if (sourceTag && targetTag) targetTag.count += sourceTag.count;
        tags = tags.filter((t) => t.name !== source);
        render();
      } else {
        li.classList.remove('deleting');
        barWrap.hidden = false;
        countSpan.hidden = false;
      }
    } catch {
      li.classList.remove('deleting');
      barWrap.hidden = false;
      countSpan.hidden = false;
    }
  }

  sortSelect.addEventListener('change', render);

  loadTags();
}

initTagsPage();
