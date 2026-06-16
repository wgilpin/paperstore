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

  // Point back link at the referring page (preserves list pagination/filters)
  const backLink = document.getElementById('back-link');
  if (backLink && document.referrer && new URL(document.referrer).origin === location.origin) {
    backLink.href = document.referrer;
  }

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
    const dateParts = [];
    if (paper.published_date) dateParts.push(`Pub: ${formatDate(paper.published_date)}`);
    if (paper.added_at) dateParts.push(`Added: ${formatDate(paper.added_at)}`);
    document.getElementById('paper-date').textContent = dateParts.join(' · ');
    document.getElementById('paper-abstract').textContent = paper.abstract || '';
    const embedUrl = paper.drive_view_url.replace(/\/view(\?.*)?$/, '/preview');
    const pdfFrame = document.getElementById('pdf-frame');
    if (pdfFrame) {
      pdfFrame.dataset.src = embedUrl;
    }

    if (paper.arxiv_id) {
      const btn = document.getElementById('alphaxiv-btn');
      btn.href = `https://www.alphaxiv.org/abs/${paper.arxiv_id}`;
      btn.title = 'Open on alphaXiv';
      btn.hidden = false;
    } else if (paper.submission_url && !paper.submission_url.startsWith('file://')) {
      const btn = document.getElementById('source-btn');
      btn.href = paper.submission_url;
      btn.title = 'Open original source';
      btn.hidden = false;
    }

    if (paper.drive_folder_url) {
      const driveBtn = document.getElementById('drive-btn');
      if (driveBtn) {
        driveBtn.href = paper.drive_folder_url;
        driveBtn.hidden = false;
      }
    }


    const downloadBtn = document.getElementById('download-btn');
    if (downloadBtn) {
      downloadBtn.href = `${API}/papers/${paper.id}/download`;
      downloadBtn.hidden = false;
    }


    const noteField = document.getElementById('note-field');
    noteField.value = paper.note ? paper.note.content : '';
    noteField.addEventListener('blur', () => saveNote(paper.id, noteField.value));

    document.getElementById('loading').hidden = true;
    document.getElementById('paper-content').hidden = false;

    document.getElementById('delete-btn').addEventListener('click', () => deletePaper(paper.id, paper.title));
    setupInlineTags(paper);
    setupEditForm(paper);
    setupExtractButton(paper);
    setupSummary(paper);
    setupTabs();
    setupImageZoom();
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
      ['suggest-title', 'suggest-authors', 'suggest-date', 'suggest-abstract'].forEach((id) => {
        const el = document.getElementById(id);
        el.classList.remove('visible');
        el.innerHTML = '';
      });
      document.getElementById('accept-all-btn').style.display = 'none';
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

  function setupExtractButton(paper) {
    const extractBtn = document.getElementById('extract-btn');
    const extractStatus = document.getElementById('extract-status');
    const extractError = document.getElementById('extract-error');
    const editBtn = document.getElementById('edit-btn');
    const editForm = document.getElementById('edit-form');
    const editStatus = document.getElementById('edit-status');
    const editError = document.getElementById('edit-error');

    extractBtn.addEventListener('click', async () => {
      extractBtn.disabled = true;
      extractBtn.textContent = 'Extracting…';
      extractStatus.textContent = '';
      extractError.textContent = '';

      try {
        const res = await fetch(`${API}/papers/${paper.id}/extract-metadata`, { method: 'POST' });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          extractError.textContent = data.detail || 'Extraction failed.';
          extractBtn.disabled = false;
          extractBtn.textContent = 'Extract metadata';
          return;
        }
        const data = await res.json();
        const m = data.metadata;

        // Open the edit form with conflict-aware filling
        const existingAuthors = paper.authors && paper.authors.length ? paper.authors.join(', ') : '';
        const llmAuthors = m.authors && m.authors.length ? m.authors.join(', ') : '';
        const acceptAllBtn = document.getElementById('accept-all-btn');
        const pendingReverts = [];  // list of () => void for each pending revert

        function applyField(inputId, suggestId, existing, llmValue) {
          const input = document.getElementById(inputId);
          const suggest = document.getElementById(suggestId);
          suggest.classList.remove('visible');
          suggest.innerHTML = '';
          if (llmValue && llmValue !== existing) {
            // Use new value, show old value with revert option
            input.value = llmValue;
            if (existing) {
              const preview = existing.length > 80 ? existing.slice(0, 80) + '…' : existing;
              suggest.innerHTML = `Was: <strong>${escapeHtml(preview)}</strong> — <button type="button">Revert</button>`;
              suggest.classList.add('visible');
              const revert = () => { input.value = existing; suggest.classList.remove('visible'); };
              suggest.querySelector('button').addEventListener('click', revert);
              pendingReverts.push(revert);
            }
          } else {
            // No new value or same — keep existing
            input.value = existing || '';
          }
        }

        applyField('edit-title', 'suggest-title', paper.title || '', m.title || '');
        applyField('edit-authors', 'suggest-authors', existingAuthors, llmAuthors);
        applyField('edit-date', 'suggest-date', paper.published_date || '', m.date || '');
        applyField('edit-abstract', 'suggest-abstract', paper.abstract || '', m.abstract || '');

        if (pendingReverts.length > 0) {
          acceptAllBtn.style.display = '';
          acceptAllBtn.textContent = 'Revert all changes';
          acceptAllBtn.onclick = () => {
            pendingReverts.forEach((fn) => fn());
            acceptAllBtn.style.display = 'none';
          };
        } else {
          acceptAllBtn.style.display = 'none';
        }
        editStatus.textContent = '';
        editError.textContent = '';
        editForm.classList.add('visible');
        editBtn.style.display = 'none';

        extractStatus.textContent = 'Review extracted metadata and save.';
        extractBtn.textContent = 'Extracted';
      } catch {
        extractError.textContent = 'Network error — is the server running?';
        extractBtn.disabled = false;
        extractBtn.textContent = 'Extract metadata';
      }
    });
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

  function setupSummary(paper) {
    console.log("setupSummary initialized for paper:", paper.id);
    const summaryBtn = document.getElementById('summary-btn');
    const summaryRegenWrap = document.getElementById('summary-regen-wrap');
    const summaryInstructions = document.getElementById('summary-instructions');
    const regenSummaryBtn = document.getElementById('regen-summary-btn');
    const summaryStatus = document.getElementById('summary-status');
    const summaryCard = document.getElementById('summary-card');
    const summaryText = document.getElementById('summary-text');
    const summaryImageCard = document.getElementById('summary-image-card');
    const summaryImage = document.getElementById('summary-image');

    if (!summaryBtn) return;

    // Load cached summary on page load
    loadCachedSummary();

    async function loadCachedSummary() {
      summaryStatus.textContent = 'Loading summary cache...';
      try {
        const res = await fetch(`${API}/papers/${paper.id}/summary`);
        if (res.ok) {
          const data = await res.json();
          if (data.summary_text) {
            displaySummary(data.summary_text, data.has_image);
            summaryStatus.textContent = '';
            summaryBtn.textContent = 'Regenerate Summary';
            summaryRegenWrap.style.display = 'flex';
          } else {
            summaryStatus.textContent = 'No summary generated yet.';
            summaryBtn.textContent = 'Generate Summary';
            summaryRegenWrap.style.display = 'none';
          }
        } else {
          summaryStatus.textContent = 'Failed to check summary cache.';
        }
      } catch {
        summaryStatus.textContent = 'Error loading summary cache.';
      }
    }

    function renderMarkdownWithMath(text) {
      const placeholders = [];
      
      // 1. Replace block math $$...$$
      let processedText = text.replace(/\$\$([\s\S]*?)\$\$/g, (match, math) => {
        const placeholder = `@@BLOCKMATH${placeholders.length}@@`;
        placeholders.push({ placeholder, math: `$$${math}$$` });
        return placeholder;
      });
      
      // 2. Replace inline math $...$
      processedText = processedText.replace(/\$([^\$\s][^\$\n]*?[^\$\s]|[^\$\s])\$/g, (match, math) => {
        const placeholder = `@@INLINEMATH${placeholders.length}@@`;
        placeholders.push({ placeholder, math: `$${math}$` });
        return placeholder;
      });
      
      // 3. Parse Markdown
      let html = marked.parse(processedText);
      
      // 4. Restore math placeholders
      for (const item of placeholders) {
        html = html.replace(item.placeholder, item.math);
      }
      
      return html;
    }

    function displaySummary(text, hasImage) {
      summaryCard.hidden = false;
      summaryText.innerHTML = renderMarkdownWithMath(text);
      
      // Render LaTeX equations in the summary text container
      if (window.renderMathInElement) {
        window.renderMathInElement(summaryText, {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\(', right: '\\)', display: false},
            {left: '\\[', right: '\\]', display: true}
          ],
          throwOnError: false
        });
      }

      if (hasImage) {
        summaryImage.src = `${API}/papers/${paper.id}/summary-image?t=${Date.now()}`;
        summaryImageCard.hidden = false;
      } else {
        summaryImageCard.hidden = true;
        summaryImage.src = '';
      }
    }

    async function triggerGeneration(instructions = '') {
      console.log("triggerGeneration called, instructions:", instructions);
      summaryBtn.disabled = true;
      regenSummaryBtn.disabled = true;
      summaryStatus.textContent = 'Generating summary and visual... this may take up to a minute.';
      summaryCard.hidden = true;
      summaryImageCard.hidden = true;

      try {
        const body = instructions ? { instructions } : {};
        const res = await fetch(`${API}/papers/${paper.id}/summary`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });

        if (res.ok) {
          const data = await res.json();
          displaySummary(data.summary_text, data.has_image);
          summaryStatus.textContent = 'Summary generated successfully!';
          summaryBtn.textContent = 'Regenerate Summary';
          summaryRegenWrap.style.display = 'flex';
          summaryInstructions.value = '';
          setTimeout(() => { summaryStatus.textContent = ''; }, 3000);
        } else {
          const data = await res.json().catch(() => ({}));
          summaryStatus.textContent = `Generation failed: ${data.detail || 'unknown error'}`;
        }
      } catch {
        summaryStatus.textContent = 'Network error generating summary.';
      } finally {
        summaryBtn.disabled = false;
        regenSummaryBtn.disabled = false;
      }
    }

    summaryBtn.addEventListener('click', () => {
      triggerGeneration();
    });

    regenSummaryBtn.addEventListener('click', () => {
      const instructions = summaryInstructions.value.trim();
      triggerGeneration(instructions);
    });
  }

  function setupTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    tabLinks.forEach(link => {
      link.addEventListener('click', () => {
        const tabId = link.getAttribute('data-tab');
        
        tabLinks.forEach(l => {
          l.classList.remove('active');
        });
        link.classList.add('active');
        
        document.querySelectorAll('.tab-content').forEach(content => {
          content.style.display = 'none';
        });
        
        const targetContent = document.getElementById(tabId);
        if (targetContent) {
          targetContent.style.display = 'block';
          if (tabId === 'tab-paper') {
            const pdfFrame = document.getElementById('pdf-frame');
            if (pdfFrame && !pdfFrame.src && pdfFrame.dataset.src) {
              pdfFrame.src = pdfFrame.dataset.src;
            }
          }
        }
      });
    });
  }

  function setupImageZoom() {
    const img = document.getElementById('summary-image');
    const overlay = document.getElementById('image-overlay');
    const overlayImg = document.getElementById('overlay-img');

    if (!img || !overlay || !overlayImg) return;

    function openOverlay() {
      overlayImg.src = img.src;
      overlay.style.display = 'flex';
      // Force a browser reflow
      overlay.offsetHeight;
      overlay.style.opacity = '1';
      overlayImg.style.transform = 'scale(1)';
    }

    function closeOverlay() {
      overlay.style.opacity = '0';
      overlayImg.style.transform = 'scale(0.95)';
      setTimeout(() => {
        overlay.style.display = 'none';
        overlayImg.src = '';
      }, 200);
    }

    img.addEventListener('click', openOverlay);
    overlay.addEventListener('click', closeOverlay);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && overlay.style.display === 'flex') {
        closeOverlay();
      }
    });
  }
}

initPaperPage();
