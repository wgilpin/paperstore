# Epic 03 — Item actions

**Phase:** 03 The manual paths
**Goal:** Search again, unlink a wrong match, and retry a failed import.
**Done criteria covered:** DC-3, DC-4, DC-5

## Behaviour

An item without a paper shows "Search again": it goes back to `new`, lookup runs for it, and it reappears in review. A paper item shows "Unlink": the link goes, the item becomes text, the paper stays. An "import failed" item shows "Retry": it goes back to `importing` and the importer runs it again.

## Acceptance criteria

- **AC-1** — Given a text or link item, when Search again is used, then its status is `new`, its outcome and candidate are cleared, and lookup starts for the list.
- **AC-2** — Given a paper item, when Search again is used, then the service refuses it.
- **AC-3** — Given a paper item, when Unlink is used, then `paper_id` is cleared, the status is `done`, and the paper is not deleted.
- **AC-4** — Given an `import_failed` item with a candidate, when Retry is used, then its status is `importing` and the import starts.
- **AC-5** — Given an item that is not `import_failed`, when Retry is used, then the service refuses it.

## Tests

- `tests/unit/test_reading_lists.py::test_search_again_resets_item_for_lookup` — AC-1.
- `tests/unit/test_reading_lists.py::test_search_again_refused_for_linked_item` — AC-2.
- `tests/unit/test_reading_lists.py::test_unlink_clears_paper` — AC-3.
- `tests/unit/test_reading_lists.py::test_retry_sets_importing_again` — AC-4.
- `tests/unit/test_reading_lists.py::test_retry_refused_unless_import_failed` — AC-5.
- M-3.

## Files

- `backend/src/services/reading_lists.py` — `search_again`, `unlink`, `retry_import`.
- `backend/src/api/reading_lists.py` — three `POST` routes under `/lists/{id}/items/{item_id}/`.
- `backend/src/templates/lists/_item.html`.

## Out of scope

Bulk actions.

## Notes

The paper's `read_at` stays on the paper after Unlink; the item's own tick starts empty.
