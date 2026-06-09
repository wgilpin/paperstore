const BACKEND = "https://papers.teleosis.ai";

const statusEl = document.getElementById("status");
const addBtn   = document.getElementById("addBtn");
const viewBtn  = document.getElementById("viewBtn");
const openBtn  = document.getElementById("openBtn");
const viewLink = document.getElementById("viewLink");
const viewLinkA = viewLink.querySelector("a");

openBtn.addEventListener("click", () => {
  chrome.tabs.create({ url: BACKEND });
});

viewBtn.addEventListener("click", () => {
  chrome.tabs.create({ url: BACKEND });
});

viewLinkA.addEventListener("click", (e) => {
  e.preventDefault();
  if (viewLinkA.href && viewLinkA.href !== "#" && !viewLinkA.href.startsWith("javascript:")) {
    chrome.tabs.create({ url: viewLinkA.href });
  }
});

function setStatus(cls, text) {
  statusEl.className = cls;
  statusEl.textContent = text;
}

const tagSection   = document.getElementById("tagSection");
const tagContainer = document.getElementById("tagContainer");
const tagInput     = document.getElementById("tagInput");
const autocompleteContainer = document.getElementById("autocompleteContainer");

let allTags = [];
let currentPaperId = null;
let currentPaperTags = [];
let activeSuggestionIndex = -1;

async function fetchAllTags() {
  try {
    const resp = await fetch(`${BACKEND}/tags`, { credentials: "include" });
    if (resp.ok) {
      const data = await resp.json();
      allTags = data.tags || [];
    }
  } catch (e) {
    console.error("Failed to fetch tags for autocomplete:", e);
  }
}

async function loadPaperTags(paperId) {
  try {
    const resp = await fetch(`${BACKEND}/papers/${paperId}`, { credentials: "include" });
    if (resp.ok) {
      const data = await resp.json();
      return data.paper?.tags || [];
    }
  } catch (e) {
    console.error("Failed to load paper tags:", e);
  }
  return [];
}

async function showTagSection(paperId, initialTags = []) {
  currentPaperId = paperId;
  currentPaperTags = initialTags;
  tagSection.style.display = "block";
  renderTags();
}

function renderTags() {
  tagContainer.innerHTML = "";
  currentPaperTags.forEach(tag => {
    const pill = document.createElement("span");
    pill.className = "tag-pill";
    pill.textContent = tag;
    
    const removeBtn = document.createElement("span");
    removeBtn.className = "remove-tag";
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => removeTag(tag));
    
    pill.appendChild(removeBtn);
    tagContainer.appendChild(pill);
  });
}

async function addTag(tag) {
  tag = tag.trim().toLowerCase();
  if (!tag) return;
  if (currentPaperTags.includes(tag)) {
    tagInput.value = "";
    closeAutocomplete();
    return;
  }
  
  currentPaperTags.push(tag);
  tagInput.value = "";
  closeAutocomplete();
  renderTags();
  await syncTags();
}

async function removeTag(tag) {
  currentPaperTags = currentPaperTags.filter(t => t !== tag);
  renderTags();
  await syncTags();
}

async function syncTags() {
  if (!currentPaperId) return;
  try {
    const resp = await fetch(`${BACKEND}/papers/${currentPaperId}/tags`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags: currentPaperTags }),
      credentials: "include"
    });
    if (!resp.ok) {
      console.error("Failed to sync tags to server:", resp.status);
    } else {
      await fetchAllTags();
    }
  } catch (e) {
    console.error("Failed to sync tags:", e);
  }
}

tagInput.addEventListener("input", () => {
  const query = tagInput.value.trim().toLowerCase();
  if (!query) {
    closeAutocomplete();
    return;
  }
  
  const matches = allTags.filter(t => t.toLowerCase().includes(query) && !currentPaperTags.includes(t));
  if (matches.length === 0) {
    closeAutocomplete();
    return;
  }
  
  renderAutocomplete(matches);
});

tagInput.addEventListener("keydown", (e) => {
  const items = autocompleteContainer.querySelectorAll(".autocomplete-suggestion");
  if (e.key === "ArrowDown") {
    e.preventDefault();
    activeSuggestionIndex = (activeSuggestionIndex + 1) % items.length;
    updateActiveSuggestion(items);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    activeSuggestionIndex = (activeSuggestionIndex - 1 + items.length) % items.length;
    updateActiveSuggestion(items);
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (activeSuggestionIndex >= 0 && activeSuggestionIndex < items.length) {
      addTag(items[activeSuggestionIndex].textContent);
    } else {
      addTag(tagInput.value);
    }
  } else if (e.key === "Escape") {
    closeAutocomplete();
  }
});

function renderAutocomplete(matches) {
  autocompleteContainer.innerHTML = "";
  activeSuggestionIndex = -1;
  
  matches.forEach(match => {
    const item = document.createElement("div");
    item.className = "autocomplete-suggestion";
    item.textContent = match;
    item.addEventListener("click", () => {
      addTag(match);
    });
    autocompleteContainer.appendChild(item);
  });
  
  autocompleteContainer.style.display = "block";
}

function updateActiveSuggestion(items) {
  items.forEach((item, idx) => {
    if (idx === activeSuggestionIndex) {
      item.classList.add("active");
      item.scrollIntoView({ block: "nearest" });
    } else {
      item.classList.remove("active");
    }
  });
}

function closeAutocomplete() {
  autocompleteContainer.style.display = "none";
  autocompleteContainer.innerHTML = "";
  activeSuggestionIndex = -1;
}

document.addEventListener("click", (e) => {
  if (e.target !== tagInput && e.target !== autocompleteContainer) {
    closeAutocomplete();
  }
});

function isArxivHost(url) {
  try {
    const host = new URL(url).hostname;
    return ["arxiv.org", "alphaxiv.org"].some(h => host === h || host.endsWith("." + h));
  } catch { return false; }
}

function isPdfUrl(url) {
  try { return new URL(url).pathname.toLowerCase().endsWith(".pdf"); }
  catch { return false; }
}

function isScienceDirect(url) {
  try {
    const host = new URL(url).hostname;
    return ["sciencedirect.com", "sciencedirectassets.com"].some(h => host === h || host.endsWith("." + h));
  } catch { return false; }
}

function normalizeArxivUrl(url) {
  // Rewrite alphaxiv.org → arxiv.org so backend _is_arxiv_url() recognises it
  try {
    const u = new URL(url);
    if (u.hostname === "alphaxiv.org" || u.hostname.endsWith(".alphaxiv.org")) {
      u.hostname = "arxiv.org";
      return u.toString();
    }
  } catch { /* fall through */ }
  return url;
}

function filenameFromUrl(url) {
  try {
    const parts = new URL(url).pathname.split("/").filter(Boolean);
    const last = parts[parts.length - 1] || "upload.pdf";
    return last.toLowerCase().endsWith(".pdf") ? last : last + ".pdf";
  } catch { return "upload.pdf"; }
}

async function getErrorMessage(resp) {
  let errMsg = `Server error ${resp.status}`;
  try {
    const data = await resp.json();
    if (data && data.detail) {
      if (typeof data.detail === "string") {
        errMsg = data.detail;
      } else if (Array.isArray(data.detail) && data.detail.length > 0) {
        errMsg = data.detail[0].msg || JSON.stringify(data.detail);
      } else if (typeof data.detail === "object") {
        errMsg = data.detail.message || JSON.stringify(data.detail);
      }
    }
  } catch { /* ignore */ }
  return errMsg;
}

async function submitArxiv(tabUrl) {
  const resp = await fetch(`${BACKEND}/papers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: normalizeArxivUrl(tabUrl) }),
    credentials: "include",
  });
  if (resp.url.includes("/auth/login")) throw new Error("Not logged in — open Paperstore and sign in first.");
  if (resp.status === 409) {
    try {
      const data = await resp.json();
      const paperId = typeof data.detail === "object" ? data.detail.paper_id : (data.paper_id || null);
      return { status: "duplicate", paperId };
    } catch {
      return { status: "duplicate", paperId: null };
    }
  }
  if (!resp.ok) {
    throw new Error(await getErrorMessage(resp));
  }
  try {
    const data = await resp.json();
    return { status: "success", paperId: data.paper?.id || null };
  } catch {
    return { status: "success", paperId: null };
  }
}

async function submitPdf(tabUrl) {
  setStatus("submitting", "Downloading PDF\u2026");
  const pdfResp = await fetch(tabUrl, { credentials: "include" });
  if (!pdfResp.ok) throw new Error(`Could not fetch PDF (${pdfResp.status})`);
  const blob = await pdfResp.blob();

  // Validate PDF header bytes (%PDF)
  const buffer = await blob.slice(0, 4).arrayBuffer();
  const arr = new Uint8Array(buffer);
  const header = String.fromCharCode(...arr);
  
  if (header !== "%PDF") {
    console.warn("Downloaded file is not a PDF (header: " + header + "). Falling back to server-side ingestion.");
    setStatus("submitting", "Self-healing: Fetching PDF via server\u2026");
    return await submitArxiv(tabUrl);
  }

  setStatus("submitting", "Uploading to PaperStore\u2026 This may take a minute, please wait.");
  const form = new FormData();
  form.append("file", blob, filenameFromUrl(tabUrl));
  form.append("source_url", tabUrl);

  const resp = await fetch(`${BACKEND}/papers/upload`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (resp.url.includes("/auth/login")) throw new Error("Not logged in — open Paperstore and sign in first.");
  if (resp.status === 409) {
    try {
      const data = await resp.json();
      const paperId = typeof data.detail === "object" ? data.detail.paper_id : (data.paper_id || null);
      return { status: "duplicate", paperId };
    } catch {
      return { status: "duplicate", paperId: null };
    }
  }
  if (!resp.ok) {
    throw new Error(await getErrorMessage(resp));
  }
  try {
    const data = await resp.json();
    return { status: "success", paperId: data.paper?.id || null };
  } catch {
    return { status: "success", paperId: null };
  }
}

(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab.url || "";

  // Pre-fetch all tags for autocomplete
  await fetchAllTags();

  // Check if paper is already saved in Paperstore
  let isSaved = false;
  let savedPaperId = null;
  if (isArxivHost(url) || isPdfUrl(url)) {
    try {
      const checkResp = await fetch(`${BACKEND}/papers/check?url=${encodeURIComponent(url)}`, { credentials: "include" });
      if (checkResp.ok) {
        const checkData = await checkResp.json();
        if (checkData.saved) {
          isSaved = true;
          savedPaperId = checkData.paper_id;
        }
      }
    } catch (e) {
      console.error("Failed to check duplicate paper:", e);
    }
  }

  if (isSaved) {
    setStatus("duplicate", "Paper already saved.");
    if (savedPaperId) {
      viewLinkA.href = `${BACKEND}/paper.html?id=${savedPaperId}`;
      viewLink.style.display = "block";
      
      const tags = await loadPaperTags(savedPaperId);
      await showTagSection(savedPaperId, tags);
    }
    viewBtn.style.display = "";
    addBtn.textContent = "Close";
    addBtn.disabled = false;
    addBtn.addEventListener("click", () => {
      window.close();
    });
    return;
  }

  // Show paywall warning if we detect ScienceDirect or a general non-arXiv PDF
  if (isScienceDirect(url) || (isPdfUrl(url) && !isArxivHost(url))) {
    const warningEl = document.getElementById("paywallWarning");
    if (warningEl) warningEl.style.display = "block";
    
    // Hide the Add button since saving will fail or is restricted
    addBtn.style.display = "none";
  }

  if (isArxivHost(url)) {
    setStatus("", "Ready to add this arXiv paper.");
    addBtn.disabled = false;
    showTagSection(null, []);
    addBtn.addEventListener("click", async () => {
      if (addBtn.textContent === "Close") {
        window.close();
        return;
      }
      addBtn.disabled = true;
      setStatus("submitting", "Submitting to PaperStore\u2026 This may take a minute, please wait.");
      try {
        const result = await submitArxiv(url);
        const status = result.status;
        const paperId = result.paperId;

        setStatus(status, status === "success" ? "Paper added to your library!" : "Paper already saved.");
        if (status === "success" || status === "duplicate") {
          if (paperId) {
            viewLinkA.href = `${BACKEND}/paper.html?id=${paperId}`;
            viewLink.style.display = "block";
            
            const serverTags = await loadPaperTags(paperId);
            currentPaperId = paperId;
            currentPaperTags = Array.from(new Set([...currentPaperTags, ...serverTags]));
            renderTags();
            await syncTags();
          }
          viewBtn.style.display = "";
          addBtn.textContent = "Close";
          addBtn.disabled = false;
        } else {
          addBtn.disabled = false;
        }
      } catch (err) {
        setStatus("error", `Error: ${err.message}`);
        addBtn.disabled = false;
      }
    });
  } else if (isPdfUrl(url)) {
    setStatus("", "Ready to upload this PDF.");
    addBtn.disabled = false;
    showTagSection(null, []);
    addBtn.addEventListener("click", async () => {
      if (addBtn.textContent === "Close") {
        window.close();
        return;
      }
      addBtn.disabled = true;
      try {
        const result = await submitPdf(url);
        const status = result.status;
        const paperId = result.paperId;

        setStatus(status, status === "success" ? "PDF added!" : "Paper already saved.");
        if (status === "success" || status === "duplicate") {
          if (paperId) {
            viewLinkA.href = `${BACKEND}/paper.html?id=${paperId}`;
            viewLink.style.display = "block";
            
            const serverTags = await loadPaperTags(paperId);
            currentPaperId = paperId;
            currentPaperTags = Array.from(new Set([...currentPaperTags, ...serverTags]));
            renderTags();
            await syncTags();
          }
          viewBtn.style.display = "";
          addBtn.textContent = "Close";
          addBtn.disabled = false;
        } else {
          addBtn.disabled = false;
        }
      } catch (err) {
        setStatus("error", `Error: ${err.message}`);
        addBtn.disabled = false;
      }
    });
  } else {
    setStatus("error", "Not an arXiv page or PDF. Cannot add.");
  }
})();
