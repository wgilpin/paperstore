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
  if (!resp.ok) throw new Error(`Server error ${resp.status}`);
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
  if (!resp.ok) throw new Error(`Server error ${resp.status}`);
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

  if (isArxivHost(url)) {
    setStatus("", "Ready to add this arXiv paper.");
    addBtn.disabled = false;
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

        setStatus(status, status === "success" ? "Paper added to your library!" : "Already in your library.");
        if (status === "success" || status === "duplicate") {
          if (paperId) {
            viewLinkA.href = `${BACKEND}/paper.html?id=${paperId}`;
            viewLink.style.display = "block";
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

        setStatus(status, status === "success" ? "PDF added!" : "Already in your library.");
        if (status === "success" || status === "duplicate") {
          if (paperId) {
            viewLinkA.href = `${BACKEND}/paper.html?id=${paperId}`;
            viewLink.style.display = "block";
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
