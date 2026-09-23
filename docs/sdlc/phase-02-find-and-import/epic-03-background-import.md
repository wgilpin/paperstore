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
