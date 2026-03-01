const BACKEND = "https://papers.teleosis.ai";

const statusEl = document.getElementById("status");
const addBtn   = document.getElementById("addBtn");

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
  const resp = await fetch(`${BACKEND}/api/papers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: normalizeArxivUrl(tabUrl) }),
    credentials: "include",
  });
  if (resp.status === 409) return "duplicate";
  if (!resp.ok) throw new Error(`Server error ${resp.status}`);
  return "success";
}

async function submitPdf(tabUrl) {
  setStatus("submitting", "Downloading PDF\u2026");
  const pdfResp = await fetch(tabUrl, { credentials: "include" });
  if (!pdfResp.ok) throw new Error(`Could not fetch PDF (${pdfResp.status})`);
  const blob = await pdfResp.blob();

  setStatus("submitting", "Uploading to PaperStore\u2026");
  const form = new FormData();
  form.append("file", blob, filenameFromUrl(tabUrl));
  form.append("source_url", tabUrl);

  const resp = await fetch(`${BACKEND}/api/papers/upload`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (resp.status === 409) return "duplicate";
  if (!resp.ok) throw new Error(`Server error ${resp.status}`);
  return "success";
}

(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab.url || "";

  if (isArxivHost(url)) {
    setStatus("", "Ready to add this arXiv paper.");
    addBtn.disabled = false;
    addBtn.addEventListener("click", async () => {
      addBtn.disabled = true;
      setStatus("submitting", "Submitting to PaperStore\u2026");
      try {
        const result = await submitArxiv(url);
        setStatus(result, result === "success" ? "Paper added to your library!" : "Already in your library.");
      } catch (err) {
        setStatus("error", `Error: ${err.message}`);
        addBtn.disabled = false;
      }
    });
  } else if (isPdfUrl(url)) {
    setStatus("", "Ready to upload this PDF.");
    addBtn.disabled = false;
    addBtn.addEventListener("click", async () => {
      addBtn.disabled = true;
      try {
        const result = await submitPdf(url);
        setStatus(result, result === "success" ? "PDF added to your library!" : "Already in your library.");
      } catch (err) {
        setStatus("error", `Error: ${err.message}`);
        addBtn.disabled = false;
      }
    });
  } else {
    setStatus("error", "Not an arXiv page or PDF. Cannot add.");
  }
})();
