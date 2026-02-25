/* PaperStore frontend — single JS file for all pages */

const API = '';  // same origin

/* ── Utilities ─────────────────────────────────────────────── */

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function formatAuthors(authors) {
  if (!authors || authors.length === 0) return 'Unknown authors';
  if (authors.length <= 3) return authors.join(', ');
  return authors.slice(0, 3).join(', ') + ' et al.';
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

/* ── Index page ─────────────────────────────────────────────── */

function initIndexPage() {
  const addForm = document.getElementById('add-form');
  if (!addForm) return;

  const urlInput = document.getElementById('url-input');
  const addBtn = document.getElementById('add-btn');
  const addStatus = document.getElementById('add-status');
  const searchInput = document.getElementById('search-input');
  const paperList = document.getElementById('paper-list');
  const paperCount = document.getElementById('paper-count');

  // Load initial library
  loadPapers('');

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
        loadPapers(searchInput.value);
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

  // Search
  searchInput.addEventListener('input', debounce((e) => {
    loadPapers(e.target.value);
  }, 300));

  async function loadPapers(query) {
    const qs = query ? `?q=${encodeURIComponent(query)}` : '';
    try {
      const res = await fetch(`${API}/papers${qs}`);
      const data = await res.json();
      renderPapers(data.papers, data.total);
    } catch {
      paperList.innerHTML = '<li class="no-results">Could not load papers.</li>';
    }
  }

  function renderPapers(papers, total) {
    const q = searchInput.value.trim();
    paperCount.textContent = q
      ? `${total} result${total !== 1 ? 's' : ''} for "${q}"`
      : `${total} paper${total !== 1 ? 's' : ''} in library`;

    if (!papers || papers.length === 0) {
      paperList.innerHTML = '<li class="no-results">No papers found.</li>';
      return;
    }

    paperList.innerHTML = papers.map((p) => `
      <li class="paper-item" onclick="location.href='paper.html?id=${p.id}'">
        <div class="paper-title">${escapeHtml(p.title)}</div>
        <div class="paper-meta">${escapeHtml(formatAuthors(p.authors))}${p.published_date ? ' · ' + formatDate(p.published_date) : ''}</div>
      </li>
    `).join('');
  }
}

/* ── Paper detail page ──────────────────────────────────────── */

function initPaperPage() {
  const loading = document.getElementById('loading');
  if (!loading) return;

  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  if (!id) { showError('No paper ID in URL.'); return; }

  loadPaper(id);

  async function loadPaper(paperId) {
    try {
      const res = await fetch(`${API}/papers/${paperId}`);
      if (res.status === 404) { showError('Paper not found.'); return; }
      if (!res.ok) { showError('Failed to load paper.'); return; }
      const data = await res.json();
      renderPaper(data.paper);
    } catch {
      showError('Network error — is the server running?');
    }
  }

  function renderPaper(paper) {
    document.title = `${paper.title} — PaperStore`;
    document.getElementById('paper-title').textContent = paper.title;
    document.getElementById('paper-authors').textContent = formatAuthors(paper.authors);
    document.getElementById('paper-date').textContent = paper.published_date ? formatDate(paper.published_date) : '';
    document.getElementById('paper-abstract').textContent = paper.abstract || '';
    const embedUrl = paper.drive_view_url.replace(/\/view(\?.*)?$/, '/preview');
    document.getElementById('pdf-frame').src = embedUrl;

    const noteField = document.getElementById('note-field');
    noteField.value = paper.note ? paper.note.content : '';
    noteField.addEventListener('blur', () => saveNote(paper.id, noteField.value));

    document.getElementById('loading').hidden = true;
    document.getElementById('paper-content').hidden = false;
  }

  async function saveNote(paperId, content) {
    const noteStatus = document.getElementById('note-status');
    noteStatus.textContent = '';
    try {
      const res = await fetch(`${API}/papers/${paperId}/note`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (res.ok) {
        noteStatus.textContent = 'Saved';
        setTimeout(() => { noteStatus.textContent = ''; }, 2000);
      }
    } catch {
      // Silently ignore save errors in prototype
    }
  }
}

function showError(msg) {
  document.getElementById('loading').hidden = true;
  const err = document.getElementById('error-msg');
  if (err) { err.hidden = false; err.textContent = msg; }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Bootstrap ──────────────────────────────────────────────── */

if (location.pathname.endsWith('paper.html')) {
  initPaperPage();
} else {
  initIndexPage();
}
