/**
 * Content script injected on arxiv.org pages.
 * Extracts the arXiv ID from the current page URL and sends it to the
 * service worker when the extension icon is clicked.
 */

const ARXIV_ID_RE = /\/(abs|pdf)\/([\d]{4}\.[\d]{4,5}|[\w-]+\/[\d]{7})/;

function extractArxivId(url) {
  const match = url.match(ARXIV_ID_RE);
  return match ? match[2] : null;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "GET_ARXIV_ID") {
    const arxivId = extractArxivId(window.location.href);
    sendResponse({ arxivId });
  }
});
