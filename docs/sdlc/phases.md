# Phases — PaperStore reading lists

Phase 01 puts lists in one place with ticks and proves the stack. Phase 02 finds and imports papers, the hard part. Phase 03 closes the manual paths and completes Release 1. Phase 04 is a test gate. Phase 05 is Release 2, and starts only if phase 04 passes.

## Phase 01 — Paste and tick

**Goal:** Paste an LLM reading list and get an ordered, tickable list page.

**Works after this phase:** Will pastes a list and names it. Gemini splits it into ordered items with their notes. The list page shows each item as text with a tick that persists. He can drop an item and delete a list. A lists index shows each list's progress.

**Not in this phase:** Any lookup, library links, imports, `papers` changes, URLs on items.

**Depends on:** nothing. Precondition: a dev database separate from production, and a production dump from the last 24 hours, both before the first schema change.

## Phase 02 — Find and import papers

**Goal:** Match list items to real papers and bring the free ones into the library.

**Works after this phase:** Each item is looked up (library, given arXiv ID, OpenAlex, arXiv search). An auto-match needs the title plus the year or an author. The review page shows each item's outcome (free PDF, record only, not found) and lets Will confirm or reject a match. Confirmed free-PDF items import in the background and link to their paper. Clicking a paper item opens its paper page (`/paper.html?id=…`), as a click on a library search result does. A paper item's tick sets `papers.read_at`, so it is ticked on every list.

**Not in this phase:** PDF upload on items, URLs on items, search again, unlink, retry, the library read filter. A "record only" item shows only its DOI link.

**Depends on:** Phase 01.

## Phase 03 — The manual paths

**Goal:** Let every item on a list reach a final state.

**Works after this phase:** Will uploads a PDF for a "record only" item, and it is ingested and linked with its DOI. He adds a URL to an unfound item: a supported paper URL is ingested and linked, and any other URL stays a plain link. He can search again, unlink a wrong match, and retry a failed import. The library gets a read / unread filter. This completes Release 1.

**Not in this phase:** Non-paper entries in the library, pasted text, non-paper PDF uploads.

**Depends on:** Phase 02.

## Phase 04 — MVP test

**Goal:** Find out whether Release 1 gets lists finished.

**Works after this phase:** Nothing new is built. Will uses Release 1 on real lists. It passes if he finishes most of one list. If it fails, phase 05 does not start and the finding goes back to the concept.

**Not in this phase:** Code changes beyond bug fixes.

**Depends on:** Phase 03. Its time limit is open in `concept.md`.

## Phase 05 — Non-paper material

**Goal:** Books, articles, pasted text and non-paper PDFs become typed library entries.

**Works after this phase:** `papers` gains a `kind` column, and its Drive and submission URL fields become nullable (ADR 0001). Book and article items become library entries, with an uploaded PDF or pasted text. Pasted text takes its metadata from the citation, and search covers it. Ticks on those items move to the entry's `read_at`. The library view, Drive download, summaries and `/api/recent` filter on `kind`.

**Not in this phase:** Renaming `papers`, lists from a chat, a phone checklist.

**Depends on:** Phase 04 passing.
