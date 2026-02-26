/* PaperStore — paper detail page */

function showError(msg) {
  document.getElementById('loading').hidden = true;
  const err = document.getElementById('error-msg');
  if (err) { err.hidden = false; err.textContent = msg; }
}

function initPaperPage() {
  const loading = document.getElementById('loading');
  if (!loading) return;

  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  if (!id) { showError('No paper ID in URL.'); return; }

  let allTags = [];  // fetched from /tags for autocomplete

  fetch(`${API}/tags`).then((r) => r.json()).then((d) => { allTags = d.tags || []; }).catch(() => {});

  loadPaper(id);

  async function loadPaper(paperId) {
    let data;
    try {
      const res = await fetch(`${API}/papers/${paperId}`);
      if (res.status === 404) { showError('Paper not found.'); return; }
      if (!res.ok) { showError('Failed to load paper.'); return; }
      data = await res.json();
    } catch {
      showError('Network error — is the server running?');
      return;
    }
    renderPaper(data.paper);
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

    document.getElementById('delete-btn').addEventListener('click', () => deletePaper(paper.id, paper.title));
    setupInlineTags(paper);
    setupEditForm(paper);
  }

  function setupInlineTags(paper) {
    const tagInput = document.getElementById('inline-tag-input');
    const tagSuggestions = document.getElementById('inline-tag-suggestions');

    function renderTagChips() {
      const container = document.getElementById('paper-tags');
      if (!container) return;
      const chips = (paper.tags || []).map((t) =>
        `<span class="tag-chip">${escapeHtml(t)}<button type="button" data-tag="${escapeHtml(t)}" aria-label="Remove ${escapeHtml(t)}">×</button></span>`
      ).join('');
      container.innerHTML = chips;
      container.querySelectorAll('button').forEach((btn) => {
        btn.addEventListener('click', () => removeTag(btn.dataset.tag));
      });
    }

    async function saveTags() {
      try {
        const res = await fetch(`${API}/papers/${paper.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: paper.title,
            authors: paper.authors,
            published_date: paper.published_date,
            abstract: paper.abstract,
            tags: paper.tags,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          paper.tags = data.paper.tags || [];
          fetch(`${API}/tags`).then((r) => r.json()).then((d) => { allTags = d.tags || []; }).catch(() => {});
        }
      } catch { /* silent */ }
      renderTagChips();
    }

    function addTag(name) {
      name = name.trim();
      if (!name || (paper.tags || []).includes(name)) return;
      paper.tags = [...(paper.tags || []), name];
      tagInput.value = '';
      tagSuggestions.hidden = true;
      saveTags();
    }

    function removeTag(name) {
      paper.tags = (paper.tags || []).filter((t) => t !== name);
      saveTags();
    }

    function showSuggestions(val) {
      if (!val) { tagSuggestions.hidden = true; return; }
      const matches = allTags.filter((t) => t.toLowerCase().includes(val.toLowerCase()) && !(paper.tags || []).includes(t));
      if (!matches.length) { tagSuggestions.hidden = true; return; }
      tagSuggestions.hidden = false;
      tagSuggestions.innerHTML = matches.map((t) =>
        `<div data-tag="${escapeHtml(t)}">${escapeHtml(t)}</div>`
      ).join('');
      tagSuggestions.querySelectorAll('div').forEach((el) => {
        el.addEventListener('mousedown', (e) => { e.preventDefault(); addTag(el.dataset.tag); });
      });
    }

    tagInput.addEventListener('input', () => showSuggestions(tagInput.value));
    tagInput.addEventListener('blur', () => { setTimeout(() => { tagSuggestions.hidden = true; }, 150); });
    tagInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); addTag(tagInput.value); }
    });

    renderTagChips();
  }

  function setupEditForm(paper) {
    const editBtn = document.getElementById('edit-btn');
    const editForm = document.getElementById('edit-form');
    const cancelBtn = document.getElementById('cancel-btn');
    const saveBtn = document.getElementById('save-btn');
    const editStatus = document.getElementById('edit-status');
    const editError = document.getElementById('edit-error');

    editBtn.addEventListener('click', () => {
      document.getElementById('edit-title').value = paper.title;
      document.getElementById('edit-authors').value = paper.authors.join(', ');
      document.getElementById('edit-date').value = paper.published_date || '';
      document.getElementById('edit-abstract').value = paper.abstract || '';
      editStatus.textContent = '';
      editError.textContent = '';
      editForm.classList.add('visible');
      editBtn.style.display = 'none';
    });

    cancelBtn.addEventListener('click', () => {
      editForm.classList.remove('visible');
      editBtn.style.display = '';
    });

    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      editStatus.textContent = '';
      editError.textContent = '';

      const title = document.getElementById('edit-title').value.trim();
      const authorsRaw = document.getElementById('edit-authors').value;
      const authors = authorsRaw.split(',').map((a) => a.trim()).filter(Boolean);
      const published_date = document.getElementById('edit-date').value || null;
      const abstract = document.getElementById('edit-abstract').value.trim() || null;

      if (!title) { editError.textContent = 'Title is required.'; saveBtn.disabled = false; return; }

      try {
        const res = await fetch(`${API}/papers/${paper.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, authors, published_date, abstract, tags: paper.tags || [] }),
        });
        if (res.ok) {
          const data = await res.json();
          const updated = data.paper;
          paper.title = updated.title;
          paper.authors = updated.authors;
          paper.published_date = updated.published_date;
          paper.abstract = updated.abstract;
          document.title = `${updated.title} — PaperStore`;
          document.getElementById('paper-title').textContent = updated.title;
          document.getElementById('paper-authors').textContent = formatAuthors(updated.authors);
          document.getElementById('paper-date').textContent = updated.published_date ? formatDate(updated.published_date) : '';
          document.getElementById('paper-abstract').textContent = updated.abstract || '';
          editStatus.textContent = 'Saved';
          setTimeout(() => {
            editForm.classList.remove('visible');
            editBtn.style.display = '';
            editStatus.textContent = '';
          }, 800);
        } else {
          const data = await res.json().catch(() => ({}));
          editError.textContent = data.detail || 'Save failed.';
        }
      } catch {
        editError.textContent = 'Network error — is the server running?';
      } finally {
        saveBtn.disabled = false;
      }
    });
  }

  async function deletePaper(paperId, title) {
    if (!confirm(`Delete "${title}" from your library and Drive?`)) return;
    const btn = document.getElementById('delete-btn');
    btn.disabled = true;
    btn.textContent = 'Deleting…';
    try {
      const res = await fetch(`${API}/papers/${paperId}`, { method: 'DELETE' });
      if (res.ok) {
        location.href = '/';
      } else {
        const data = await res.json().catch(() => ({}));
        alert(data.detail || 'Delete failed.');
        btn.disabled = false;
        btn.textContent = 'Delete paper';
      }
    } catch {
      alert('Network error — is the server running?');
      btn.disabled = false;
      btn.textContent = 'Delete paper';
    }
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

initPaperPage();
