# Phase 02 — Find and import papers

**Goal:** Match list items to real papers and bring the free ones into the library.

## Scope

- `papers` gains `read_at` and `doi` (idempotent `ALTER … IF NOT EXISTS`, and a unique index on `doi`).
- `reading_list_items` gains `paper_id`, `url`, `status` and the `candidate_*` fields.
- New `services/citation_resolver.py` (library, arXiv ID in the citation, OpenAlex, arXiv title search) and `services/openalex_client.py`.
- `services/reading_lists.py` gains lookup, review, confirm and import orchestration. Lookup and import run in background threads, the pattern of `batch_metadata.py`.
- New review page and list-page changes under `/lists`. Ingestion is called, not changed.
- Dev `DRIVE_FOLDER_ID` stops pointing at the production folder (resolves ISS-1).

## Done criteria

- **DC-1** — "Find papers" on a list looks up every item not yet linked. An item that matches a library paper by arXiv ID, DOI or a close title shows that paper as its match.
- **DC-2** — Lookup also searches outside the library, in this order: an arXiv ID in the citation, OpenAlex, arXiv title search. Each item ends with one outcome: in library, free PDF, record only, or not found.
- **DC-3** — A match is confident only when the title matches and the year (±1) or an author surname also matches. OpenAlex book reviews and paratext never match. A weak match is flagged and not pre-selected.
- **DC-4** — Lookup runs in the background. The list page shows lookup progress and stays usable. A new list, and a successful parse again, start lookup by themselves.
- **DC-5** — On the review page, Will selects which matches to accept, in one submit. An accepted library match links at once. An accepted record-only match makes the item a DOI link. A rejected match leaves a text item.
- **DC-6** — Accepted free-PDF items import in the background through the existing ingestion and link to their new paper. A duplicate links the existing paper. A failed import marks the item "import failed" and keeps its URL. The DOI from the lookup is stored on the paper.
- **DC-7** — Clicking a linked paper item opens `/paper.html?id=<paper id>`, as a click on a library search result does.
- **DC-8** — Ticking a paper item sets `papers.read_at`. The same paper on another list shows ticked, and both lists' progress counts it.
- **DC-9** — Items left in "importing" when the app restarts show as "import failed".
- **DC-10** — Imports run in dev do not upload into the production Drive folder.

## Not in this phase

PDF upload on items, URLs typed on items, search again for one item, unlink, retry, the library read filter.

## Epics

1. `epic-01-library-match.md` — tracer: find papers in the library, review, link, click to open, shared tick.
2. `epic-02-outside-lookup.md` — arXiv ID, OpenAlex and arXiv search, the confidence rule, outcomes, background lookup with progress.
3. `epic-03-background-import.md` — import accepted free-PDF items, duplicates, failures, DOI, restart recovery, dev Drive folder.

Each epic needs the one before it.

## Risks

- **Lookup is slow.** arXiv asks for 3 seconds between calls. A 16-item list can take a minute or more. Hence the background thread and the progress line.
- **Lookup in a background thread is an addition to `architecture.md`,** which names a thread for import only. It follows the same pattern and contradicts nothing.
- **Title similarity against the library is SQL (`pg_trgm`).** Unit tests mock the session, so it is proved by the manual walkthrough only.
- **Import in dev writes to Drive.** Epic 03 points dev at the Drive root, or at `DEV_DRIVE_FOLDER_ID` when set, before the first import.
- **The import worker mocks `IngestionService`** in unit tests. It is our own class, but it is the seam to Drive and HTTP.
