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

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. Service: `search_again` (items without a paper back to `new`, outcome and candidate cleared), `unlink` (clears `paper` and `paper_id`, status `done`; the paper and its `read_at` stay), `retry_import` (`import_failed` with a candidate back to `importing`). Each refuses the wrong kind of item with `ValueError`.
2. Routes `POST /lists/{id}/items/{item_id}/search`, `/unlink`, `/retry`. Each returns the item row plus the status block and progress line out of band (shared `_item_and_status` helper), so lookup and import progress poll, and the progress count updates after an unlink.
3. `_item.html` action row: Unlink (with confirmation) on paper items, Retry import on failed imports, Search again on items without a paper.

### Tests added

- `tests/unit/test_reading_lists.py` — `test_search_again_resets_item_for_lookup`, `test_search_again_refused_for_linked_item`, `test_unlink_clears_paper`, `test_unlink_refused_without_paper`, `test_retry_sets_importing_again`, `test_retry_refused_unless_import_failed`.

All six observed red (missing methods) before green.

Manual walkthrough (dev stack, "Memory" list; `window.confirm` stubbed):

- **M-3, retry (AC-4)** — pass for the control. "Add link" with `https://arxiv.org/abs/2507.06211` on "Modern methods in associative memory" failed: the PDF download stopped at 3,145,728 of 16,402,634 bytes ("peer closed connection"). The item showed "Import failed" with Retry import, Search again and Change link. Retry import set it back to "Importing…" and ran the import again, which failed the same way. The failure is in the existing ingestion's download of this 16 MB PDF, not in the retry (new issue).
- **M-3, unlink (AC-3)** — pass. Unlinked Titans: the item became text with Search again and Add link; `GET /papers/0fe4e4a8…` still returns 200; progress went from 2 to 1 of 15, because the tick belonged to the paper.
- **M-3, search again (AC-1)** — pass. Search again on "Hopfield Networks is All You Need" showed "Looking up papers… 0 of 1", then "Review matches (1)" with a pre-selected free-PDF match.

### Suite result

`cd backend && uv run pytest` — 139 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 44 source files.

### Deviations from the plan

- Added `test_unlink_refused_without_paper` beyond the plan.
- To test a restart mid-import, `backend/src/main.py` was touched to force a dev reload; the import had already failed on its own, so the restart path was not exercised again (it is unit-tested in phase 02).

### Follow-ups

- The existing ingestion cannot download some large arXiv PDFs: arXiv closed the connection at 3 MB of a 16 MB file, twice. The library's own submit uses the same download.

---

## Review — 2026-09-23

**Verdict:** pass with follow-ups

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_search_again_resets_item_for_lookup`; M-3 |
| AC-2 | yes | `test_search_again_refused_for_linked_item` |
| AC-3 | yes | `test_unlink_clears_paper`; M-3 |
| AC-4 | yes | `test_retry_sets_importing_again`; M-3 (the retry ran; the download itself failed) |
| AC-5 | yes | `test_retry_refused_unless_import_failed` |

Suite re-run by the reviewer: 139 passed; ruff and mypy clean.

### Drift

None.

### Findings

1. Medium, outside this epic — the existing ingestion failed twice to download a 16 MB arXiv PDF (connection closed at 3 MB). Any large arXiv paper can fail the same way, from a list or from the library's own submit.
2. Low — `unlink` clears both `paper` and `paper_id`, which the unit test checks; without clearing the relationship the flush would restore the link. Correct as written.

The deep pass ran inline, not through `/code-review`.

### Follow-ups

- Make large PDF downloads in ingestion survive a dropped connection (retry, or a streamed download).
