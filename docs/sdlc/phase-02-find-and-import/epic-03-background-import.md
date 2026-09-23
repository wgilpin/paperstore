# Epic 03 — Background import

**Phase:** 02 Find and import papers
**Goal:** Bring accepted free-PDF papers into the library and link them.
**Done criteria covered:** DC-5 (free PDF), DC-6, DC-9, DC-10

## Behaviour

Accepting a free-PDF match sets the item to "importing" and starts a background thread. The thread calls the existing ingestion for each item: an arXiv ID goes in as an arXiv URL, anything else as its PDF URL. A new paper links to the item and gets the DOI from the lookup. A duplicate links the paper that exists. A failure marks the item "import failed" and keeps its URL as a link. After a restart, items left in "importing" become "import failed". In dev, imports upload to the Drive root, or to `DEV_DRIVE_FOLDER_ID` when set, never to the production folder.

## Acceptance criteria

- **AC-1** — Given an accepted free-PDF match, when the review is submitted, then the item's status is `importing`.
- **AC-2** — Given an importing item with an arXiv ID, when the import runs and ingestion returns a new paper, then the item links to it, its status is `done`, and the paper's `doi` is the candidate DOI when no other paper has it.
- **AC-3** — Given an importing item whose paper exists, when ingestion raises `DuplicateError` with a paper ID, then the item links to that paper and its status is `done`.
- **AC-4** — Given an importing item, when ingestion raises any other error, then the status is `import_failed` and `url` holds the candidate URL.
- **AC-5** — Given items in `importing` at startup, when the app starts, then they are `import_failed`.
- **AC-6** — Given the dev stack, when its API container environment is read, then `DRIVE_FOLDER_ID` is empty or equals `DEV_DRIVE_FOLDER_ID`.

## Tests

- `tests/unit/test_reading_lists.py::test_accept_free_pdf_marks_importing` — AC-1.
- `tests/unit/test_reading_lists.py::test_import_links_new_paper_and_sets_doi` — AC-2.
- `tests/unit/test_reading_lists.py::test_import_duplicate_links_existing_paper` — AC-3.
- `tests/unit/test_reading_lists.py::test_import_failure_marks_item_and_keeps_url` — AC-4.
- `tests/unit/test_reading_lists.py::test_reset_stuck_imports_marks_import_failed` — AC-5.
- M-4 — a real import in dev; M-7 — AC-6.

## Files

- `backend/src/services/reading_lists.py` — `run_import`, `reset_stuck_imports`.
- `backend/src/api/reading_lists.py` — start the import after the review submit.
- `backend/src/main.py` — call `reset_stuck_imports` at startup.
- `backend/src/templates/lists/_item.html` — importing and failed states.
- `docker-compose.local.yml` — `DRIVE_FOLDER_ID: ${DEV_DRIVE_FOLDER_ID:-}`.

## Out of scope

Retry of a failed import, PDF upload (phase 03).

## Notes

- Changing `docker-compose.local.yml` needs a dev restart. Ask before the `docker compose` command.
- Ingestion's own duplicate checks run first. Do not copy them into the importer.
- The importer opens its own sessions, as `batch_metadata._loop` does.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `apply_review` returns the IDs of accepted free-PDF items, sets them to `importing`, and keeps their candidate; the interim "free PDF becomes a link" from epic 02 is gone.
2. `import_item`: an arXiv ID goes to `IngestionService.ingest` as `https://arxiv.org/abs/<id>`, otherwise the PDF URL. Success links the paper, stores the candidate DOI when no other paper has it, and clears the candidate. `DuplicateError` with a paper ID links that paper. Any other error rolls back, marks `import_failed`, keeps a link (landing page, else PDF) and the candidate.
3. `start_import` / `_import_thread` run the imports in a daemon thread with one session and one `IngestionService`.
4. `reset_stuck_imports`, called from the startup hook in `main.py`.
5. The status block also polls while items import ("Importing n papers…"); the poll that sees all work finish answers with `HX-Refresh`, so the page reloads with the linked items. "Importing…" and "Import failed" badges in `lists/_item.html`.
6. `docker-compose.local.yml`: `DRIVE_FOLDER_ID: ${DEV_DRIVE_FOLDER_ID:-}`; dev API recreated (asked and approved).

### Tests added

- `tests/unit/test_reading_lists.py` — `test_accept_free_pdf_marks_importing`, `test_import_links_new_paper_and_sets_doi`, `test_import_without_arxiv_id_uses_the_pdf_url`, `test_import_duplicate_links_existing_paper`, `test_import_failure_marks_item_and_keeps_url`, `test_reset_stuck_imports_marks_import_failed`.

All six observed red (missing methods) before green.

Manual walkthrough (dev stack):

- **M-7 (AC-6)** — pass. `DRIVE_FOLDER_ID` in `paperstore-dev-api-1` is empty, so dev uploads go to the Drive root. `.env` has no `DEV_DRIVE_FOLDER_ID`.
- **M-4 (AC-1, AC-2 for a real import)** — pass. New list "Import test": lookup gave two free PDFs (Memorizing Transformers by arXiv ID, Frémaux by a Frontiers PDF) and Titans in the library. Applying the review showed "Importing 2 papers…" with badges, and Titans linked at once. The page reloaded by itself when both imports ended; both items link to new papers (`/paper.html?id=ea66025a…`, `…3cce6427…`) with Drive files. The library went from 631 to 633 papers. The paper API does not return `doi`, so the stored DOI was not checked by hand.

### Suite result

`cd backend && uv run pytest` — 123 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 44 source files.

### Deviations from the plan

- The finished poll sends `HX-Refresh` to reload the page. Not in the spec; without it the items would stay "Importing…" until a manual reload.
- `import_item` takes an injected ingestion object; tests use a small fake instead of patching `IngestionService`.
- AC-3 (duplicate) is proved by the unit test only. The resolver finds library copies first, so the walkthrough could not produce a duplicate at import time.

### Follow-ups

- The library's submit route runs a Gemini metadata step after ingestion (`_enrich_paper_async` in `api/papers.py`); imports from a list do not. A paper imported by PDF URL can have thinner metadata than one submitted by hand.

---

## Review — 2026-09-23

**Verdict:** pass with follow-ups

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_accept_free_pdf_marks_importing`; M-4 |
| AC-2 | yes | `test_import_links_new_paper_and_sets_doi`, `test_import_without_arxiv_id_uses_the_pdf_url`; M-4 for the real import |
| AC-3 | yes | `test_import_duplicate_links_existing_paper` |
| AC-4 | yes | `test_import_failure_marks_item_and_keeps_url` |
| AC-5 | yes | `test_reset_stuck_imports_marks_import_failed` |
| AC-6 | yes | M-7, recorded in the build note |

Suite re-run by the reviewer: 123 passed; ruff and mypy clean.

### Drift

None. The import calls `IngestionService.ingest` and changes nothing in ingestion, as `architecture.md` states. The background thread follows the batch-loop pattern.

### Findings

1. Low — imported papers skip the Gemini metadata step that the library's submit route runs after ingestion. Recorded as a follow-up in the build note.
2. Low — the startup reset also runs on every `--reload` in dev, so an import cut off by a code change shows as failed. That is the correct outcome, and phase 03 adds the retry.
3. Low — the stored DOI was checked by the unit test only; the paper API does not expose `doi`.

The deep pass ran inline, not through `/code-review`.

### Follow-ups

- Run the same post-ingestion metadata step for papers imported from a list.
