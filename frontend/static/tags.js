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
        <button class="delete-btn" aria-label="Delete tag ${escapeHtml(tag.name)}" title="Delete tag">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
        </button>
      `;
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

  sortSelect.addEventListener('change', render);

  loadTags();
}

initTagsPage();
