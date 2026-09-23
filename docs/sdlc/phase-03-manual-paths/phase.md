# Phase 03 — The manual paths

**Goal:** Let every item on a list reach a final state.

## Scope

- List page actions per item: upload PDF, add link, search again, unlink, retry.
- `services/reading_lists.py` gains the action rules; the upload uses the existing `IngestionService.ingest_local`, and paper links reuse phase 02's import thread.
- Item URLs are limited to `http` and `https` (ISS-8).
- The library page gets a Read filter: `SearchService.search` and `GET /papers` take a `read` parameter; `frontend/index.html` and `frontend/static/index.js` get one select.
- Ingestion is called, not changed.

## Done criteria

- **DC-1** — A record-only item offers "Upload PDF". A PDF upload is ingested, linked to the item, and given the item's DOI. A file that is not a PDF is refused with a message, and the item does not change. An upload of a paper already in the library links that paper.
- **DC-2** — An item without a paper offers "Add link". An arXiv, alphaXiv or bioRxiv URL, or a URL that serves a PDF, is imported in the background and linked. Any other `http` or `https` URL becomes the item's plain link. Any other scheme is refused.
- **DC-3** — "Search again" on an item without a paper runs lookup for that item alone and puts it back in review.
- **DC-4** — "Unlink" on a paper item removes the link. The item becomes a text item; the paper stays in the library.
- **DC-5** — "Retry" on an "import failed" item runs its import again.
- **DC-6** — The library page has a Read filter (All, Unread, Read) based on `papers.read_at`. It works together with search, tags, sort and paging.
- **DC-7** — An item link is shown as a link only when its URL is `http` or `https`.

## Not in this phase

Non-paper entries in the library, pasted text, non-paper PDF uploads, editing an item's title or citation, add item, reorder.

## Epics

1. `epic-01-upload-pdf.md` — tracer: upload a PDF for a record-only item, link it.
2. `epic-02-add-link.md` — add a URL to an item: import a paper URL, or keep a plain link; `http(s)` only.
3. `epic-03-item-actions.md` — search again, unlink, retry.
4. `epic-04-read-filter.md` — the library Read filter.

Epics 02 and 03 need epic 01 (the item action row). Epic 04 is independent of the others.

## Risks

- **Upload runs in the request.** Drive upload and PDF metadata take several seconds, as they do for the library's own upload. The form shows an indicator.
- **The library page is vanilla JS.** The Read filter adds one parameter to the existing fetch in `index.js`. Converting the page to HTMX is out of scope.
- **SQL filters are proved by compiling the expression**, not against a database; the walkthrough checks the real result.
