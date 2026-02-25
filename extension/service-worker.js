/**
 * Background service worker.
 * Listens for SUBMIT_PAPER messages from the popup, POSTs the arXiv URL to
 * the PaperStore backend, and relays the result back to the popup.
 */

const DEFAULT_BACKEND_URL = "http://localhost:8000";

async function submitPaper(arxivId) {
  const { backendUrl = DEFAULT_BACKEND_URL } =
    await chrome.storage.local.get("backendUrl");

  const url = `https://arxiv.org/abs/${arxivId}`;
  const response = await fetch(`${backendUrl}/papers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (response.status === 409) {
    return { status: "duplicate" };
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Backend error ${response.status}: ${text}`);
  }

  return { status: "success" };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "SUBMIT_PAPER") {
    submitPaper(message.arxivId)
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ status: "error", message: err.message }));
    return true; // keep the message channel open for async response
  }
});
