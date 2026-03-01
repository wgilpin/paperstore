/* PaperStore — index page */

function initIndexPage() {
  const addForm = document.getElementById('add-form');
  if (!addForm) return;

  const addToggle = document.getElementById('add-toggle');
  const urlInput = document.getElementById('url-input');
  const addBtn = document.getElementById('add-btn');
  const addStatus = document.getElementById('add-status');
  const searchInput = document.getElementById('search-input');
  const sortSelect = document.getElementById('sort-select');
  const paperList = document.getElementById('paper-list');
  const paperCount = document.getElementById('paper-count');
  const pagination = document.getElementById('pagination');
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const pageInfo = document.getElementById('page-info');
  const tagFilter = document.getElementById('tag-filter');
  const tagPillsRow = document.getElementById('tag-pills-row');
  const tagAutocomplete = document.getElementById('tag-autocomplete');
  const tagDropdown = document.getElementById('tag-dropdown');
  const enrichBtn = document.getElementById('enrich-btn');
  const enrichStatus = document.getElementById('enrich-status');

  const PAGE_SIZE = 20;
  const TOP_TAGS = 6;  // number of most-common tags shown as pills
  let currentPage = 1;
  let totalPages = 1;
  let activeTag = null;
  let allTags = [];

  addToggle.addEventListener('click', () => {
    addForm.hidden = !addForm.hidden;
    if (!addForm.hidden) urlInput.focus();
  });

  // Restore state from URL on load
  const initParams = new URLSearchParams(location.search);
  if (initParams.get('page')) currentPage = Math.max(1, parseInt(initParams.get('page'), 10) || 1);
  if (initParams.get('q')) searchInput.value = initParams.get('q');
  if (initParams.get('sort')) sortSelect.value = initParams.get('sort');
  if (initParams.get('tag')) activeTag = initParams.get('tag');

  // Load tags for filter bar, then load papers; also check batch job status on load
  loadTags().then(() => loadPapers());
  checkBatchStatus();

  // ── Batch metadata enrichment ────────────────────────────────────────────

  function setEnrichUI(running, papersDone) {
    if (running) {
      enrichBtn.textContent = 'Stop metadata search';
      enrichBtn.classList.add('active');
      enrichStatus.textContent = papersDone > 0 ? `${papersDone} applied so far…` : 'Running…';
      enrichStatus.className = 'running';
    } else {
      enrichBtn.textContent = 'Find missing metadata';
      enrichBtn.classList.remove('active');
      enrichStatus.textContent = papersDone > 0 ? `Done — ${papersDone} applied.` : '';
      enrichStatus.className = '';
    }
  }

  async function checkBatchStatus() {
    try {
      const res = await fetch(`${API}/batch/metadata/status`);
      if (!res.ok) return;
      const data = await res.json();
      const s = data.status;
      if (s) setEnrichUI(s.running, s.papers_done);
    } catch {
      // Non-fatal — button stays in default state
    }
  }

  enrichBtn?.addEventListener('click', async () => {
    const isRunning = enrichBtn.classList.contains('active');
    const endpoint = isRunning ? '/batch/metadata/stop' : '/batch/metadata/start';
    try {
      const res = await fetch(`${API}${endpoint}`, { method: 'POST' });
      if (!res.ok) return;
      const data = await res.json();
      const s = data.status;
      if (s) setEnrichUI(s.running, s.papers_done);
    } catch {
      enrichStatus.textContent = 'Network error — is the server running?';
      enrichStatus.className = 'error';
    }
  });

  async function loadTags() {
    try {
      const res = await fetch(`${API}/tags`);
      const data = await res.json();
      allTags = data.tags || [];
      renderTagFilter(allTags);
    } catch {
      // Non-fatal — tag filter just stays hidden
    }
  }

  function renderTagFilter(tags) {
    if (!tags.length) { tagFilter.hidden = true; return; }
    tagFilter.hidden = false;

    // Top pills: "All" + first TOP_TAGS by frequency
    const topTags = tags.slice(0, TOP_TAGS);
    const allPill = `<button class="tag-pill${activeTag === null ? ' active' : ''}" data-tag="">All</button>`;
    const pills = topTags.map((t) =>
      `<button class="tag-pill${activeTag === t ? ' active' : ''}" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</button>`
    ).join('');
    tagPillsRow.innerHTML = allPill + pills;
    tagPillsRow.querySelectorAll('.tag-pill').forEach((btn) => {
      btn.addEventListener('click', () => {
        selectTag(btn.dataset.tag || null);
      });
    });

    // Autocomplete input state
    const isActiveTagInTop = activeTag === null || topTags.includes(activeTag);
    if (activeTag && !isActiveTagInTop) {
      tagAutocomplete.value = activeTag;
      tagAutocomplete.classList.add('active');
    } else {
      tagAutocomplete.value = '';
      tagAutocomplete.classList.remove('active');
    }
  }

  function selectTag(tag) {
    activeTag = tag || null;
    currentPage = 1;
    tagDropdown.hidden = true;
    tagAutocomplete.blur();
    loadTags();
    loadPapers();
  }

  // Autocomplete behaviour
  tagAutocomplete.addEventListener('focus', () => { tagAutocomplete.select(); showTagDropdown(tagAutocomplete.value); });
  tagAutocomplete.addEventListener('input', () => showTagDropdown(tagAutocomplete.value));
  tagAutocomplete.addEventListener('keydown', (e) => {
    const items = [...tagDropdown.querySelectorAll('div')];
    const hi = tagDropdown.querySelector('.highlighted');
    let idx = items.indexOf(hi);
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (idx < items.length - 1) { hi && hi.classList.remove('highlighted'); items[idx + 1].classList.add('highlighted'); items[idx + 1].scrollIntoView({ block: 'nearest' }); }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (idx > 0) { hi && hi.classList.remove('highlighted'); items[idx - 1].classList.add('highlighted'); items[idx - 1].scrollIntoView({ block: 'nearest' }); }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (hi) selectTag(hi.dataset.tag);
    } else if (e.key === 'Escape') {
      tagDropdown.hidden = true;
    }
  });
  document.addEventListener('click', (e) => {
    if (!tagFilter.contains(e.target)) tagDropdown.hidden = true;
  });

  function showTagDropdown(query) {
    const q = query.toLowerCase();
    const topTags = allTags.slice(0, TOP_TAGS);
    // With a query: search all tags. Without: show only tags beyond the top pills.
    const filtered = q
      ? allTags.filter((t) => t.toLowerCase().includes(q))
      : allTags.filter((t) => !topTags.includes(t));
    if (!filtered.length) { tagDropdown.hidden = true; return; }
    tagDropdown.innerHTML = filtered.map((t) =>
      `<div data-tag="${escapeHtml(t)}" class="${activeTag === t ? 'active' : ''}">${escapeHtml(t)}</div>`
    ).join('');
    tagDropdown.querySelectorAll('div').forEach((el) => {
      el.addEventListener('mousedown', (e) => { e.preventDefault(); selectTag(el.dataset.tag); });
    });
    tagDropdown.hidden = false;
  }

  // Add paper form
  addForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    addBtn.disabled = true;
    addStatus.className = '';
    addStatus.textContent = 'Adding paper…';

    try {
      const res = await fetch(`${API}/papers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (res.ok) {
        addStatus.className = 'success';
        addStatus.textContent = `Added: "${data.paper.title}"`;
        urlInput.value = '';
        addForm.hidden = true;
        currentPage = 1;
        loadTags();
        loadPapers();
      } else if (res.status === 409) {
        addStatus.className = 'error';
        addStatus.textContent = 'This paper is already in your library.';
      } else {
        addStatus.className = 'error';
        addStatus.textContent = data.detail || 'Failed to add paper.';
      }
    } catch {
      addStatus.className = 'error';
      addStatus.textContent = 'Network error — is the server running?';
    } finally {
      addBtn.disabled = false;
    }
  });

  // Search — reset to page 1 on new query
  searchInput.addEventListener('input', debounce(() => {
    currentPage = 1;
    loadPapers();
  }, 300));

  // Sort — reset to page 1
  sortSelect.addEventListener('change', () => {
    currentPage = 1;
    loadPapers();
  });

  prevBtn.addEventListener('click', () => {
    if (currentPage > 1) { currentPage--; loadPapers(); }
  });

  nextBtn.addEventListener('click', () => {
    if (currentPage < totalPages) { currentPage++; loadPapers(); }
  });

  function syncUrl() {
    const query = searchInput.value.trim();
    const sort = sortSelect.value;
    const p = new URLSearchParams();
    if (currentPage > 1) p.set('page', String(currentPage));
    if (query) p.set('q', query);
    if (sort && sort !== sortSelect.options[0].value) p.set('sort', sort);
    if (activeTag) p.set('tag', activeTag);
    const qs = p.toString();
    history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
  }

  async function loadPapers() {
    const query = searchInput.value.trim();
    const sort = sortSelect.value;
    syncUrl();
    const params = new URLSearchParams({ sort, page: String(currentPage) });
    if (query) params.set('q', query);
    if (activeTag) params.set('tag', activeTag);

    try {
      const res = await fetch(`${API}/papers?${params}`);
      const data = await res.json();
      renderPapers(data.papers, data.total, query);
    } catch {
      paperList.innerHTML = '<li class="no-results">Could not load papers.</li>';
    }
  }

  function renderPapers(papers, total, query) {
    paperCount.textContent = query
      ? `${total} result${total !== 1 ? 's' : ''} for "${query}"`
      : `${total} paper${total !== 1 ? 's' : ''} in library`;

    totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    if (!papers || papers.length === 0) {
      paperList.innerHTML = '<li class="no-results">No papers found.</li>';
      pagination.hidden = true;
      return;
    }

    paperList.innerHTML = papers.map((p) => {
      const tagsHtml = p.tags && p.tags.length
        ? `<div class="paper-tags">${p.tags.map((t) => `<span class="tag-chip" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</span>`).join('')}</div>`
        : '';
      return `
        <li class="paper-item" data-id="${p.id}">
          <div class="paper-title">${escapeHtml(p.title)}</div>
          <div class="paper-meta">${escapeHtml(formatAuthors(p.authors))}${p.published_date ? ' · ' + formatDate(p.published_date) : ''}</div>
          ${tagsHtml}
        </li>
      `;
    }).join('');

    paperList.onclick = (e) => {
      const chip = e.target.closest('.tag-chip');
      if (chip) { selectTag(chip.dataset.tag); return; }
      const item = e.target.closest('.paper-item');
      if (item) location.href = `paper.html?id=${item.dataset.id}`;
    };

    pagination.hidden = totalPages <= 1;
    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
  }
}

initIndexPage();
