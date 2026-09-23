# Epic 01 — Upload PDF

**Phase:** 03 The manual paths
**Goal:** Upload a PDF for a record-only item and link the new paper.
**Done criteria covered:** DC-1

## Behaviour

A record-only item (a link, no paper) shows an "Upload PDF" action on the list page. Will picks a PDF; the app ingests it through `IngestionService.ingest_local`, with the item's link as the source URL, links the paper to the item, and stores the item's DOI on the paper. A file that is not a PDF is refused with a message. A paper that is already in the library is linked instead.

## Acceptance criteria

- **AC-1** — Given a record-only item with a DOI link, when a PDF is uploaded, then ingestion receives the bytes and the DOI URL, the item links to the new paper, and the paper's `doi` is set when no other paper has it.
- **AC-2** — Given bytes that do not start with `%PDF`, when they are uploaded, then the service raises a validation error and the item does not change.
- **AC-3** — Given ingestion raises `DuplicateError` with a paper ID, when a PDF is uploaded, then the item links to that paper.
- **AC-4** — Given an item that already links to a paper, when a PDF is uploaded, then the service refuses it.
- **AC-5** — Given the list page, when a record-only item is shown, then it has an "Upload PDF" control; after an upload it shows as a linked paper.

## Tests

- `tests/unit/test_reading_lists.py::test_upload_pdf_links_item_and_sets_doi` — AC-1.
- `tests/unit/test_reading_lists.py::test_upload_non_pdf_is_refused` — AC-2.
- `tests/unit/test_reading_lists.py::test_upload_duplicate_links_existing_paper` — AC-3.
- `tests/unit/test_reading_lists.py::test_upload_only_for_items_without_paper` — AC-4.
- M-1 — AC-5.

## Files

- `backend/src/services/reading_lists.py` — `upload_pdf`.
- `backend/src/api/reading_lists.py` — `POST /lists/{id}/items/{item_id}/upload`.
- `backend/src/templates/lists/_item.html` — an action row, with the upload form.
- `frontend/static/lists.css`.

## Out of scope

Uploads for text items without a DOI link (they get "Add link" or "Search again"), non-paper uploads.

## Notes

- The action row is shared by epics 02 and 03; keep it small: text links, one line.
- The upload form uses `hx-encoding="multipart/form-data"`. Show errors in the item row.
- The DOI comes from the item's `url` when it is a `https://doi.org/` link.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `ReadingListService.upload_pdf`: refuses a linked item and bytes that are not a PDF (`ValueError`, item unchanged); calls `IngestionService.ingest_local` with the item's link as `source_url`; links the new paper and stores the DOI from a `https://doi.org/` link when no other paper has it; `DuplicateError` links the existing paper. Public `get_item`.
2. `POST /lists/{id}/items/{item_id}/upload` returns the item row, with any error shown in it.
3. `_item.html`: an action row; an item with a link and no paper shows "Upload PDF". The form submits on file choice (`hx-trigger="change"`), with no JavaScript. Styles in `frontend/static/lists.css`.

### Tests added

- `tests/unit/test_reading_lists.py` — `test_upload_pdf_links_item_and_sets_doi`, `test_upload_non_pdf_is_refused`, `test_upload_duplicate_links_existing_paper`, `test_upload_only_for_items_without_paper`.

All four observed red (missing method) before green.

Manual walkthrough (dev stack):

- **M-1 (AC-5, and AC-1, AC-2 for real)** — pass. On "Lookup test", the record-only item "Computational principles of synaptic memory consolidation" showed "Upload PDF". A text file named `notes.pdf` gave "That file is not a PDF." and the DOI link stayed. A one-page PDF built in the browser (title, authors, journal line) became paper `9e500f9d…` with a Drive file and `submission_url` `https://doi.org/10.1038/nn.4401`; the item then linked to `/paper.html?id=9e500f9d…` and the upload control went away. The paper has no authors: the metadata step after ingestion does not run (ISS-10).

### Suite result

`cd backend && uv run pytest` — 127 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 44 source files.

### Deviations from the plan

- "Upload PDF" shows on any item that has a link and no paper, not only on record-only items. A plain link added in epic 02 can then take a PDF too.
- The PDF for the walkthrough was generated in the browser; no real article PDF was uploaded.

### Follow-ups

None new. ISS-10 also applies to uploads from a list.

---

## Review — 2026-09-23

**Verdict:** pass

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_upload_pdf_links_item_and_sets_doi`; M-1 |
| AC-2 | yes | `test_upload_non_pdf_is_refused`; M-1 |
| AC-3 | yes | `test_upload_duplicate_links_existing_paper` |
| AC-4 | yes | `test_upload_only_for_items_without_paper` |
| AC-5 | yes | M-1, recorded in the build note |

Suite re-run by the reviewer: 127 passed; ruff and mypy clean. No inline JavaScript in the templates.

### Drift

None. The upload calls `ingest_local` and changes nothing in ingestion, as `architecture.md` states.

### Findings

1. Low — the upload reads the whole file into memory with no size limit, as the library's own upload route does. One user; acceptable.
2. Low — the missing authors on uploaded papers is ISS-10, already open.

The deep pass ran inline, not through `/code-review`.

### Follow-ups

None.
