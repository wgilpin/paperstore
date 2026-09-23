# Epic 04 — Manage lists

**Phase:** 01 Paste and tick
**Goal:** Find every list from the library, and drop items or delete lists.
**Done criteria covered:** DC-6, DC-7, DC-8

## Behaviour

The library menu gets a "Reading lists" link to `/lists`, which shows every list, newest first, with its name, created date and progress. On a list page, Will can drop an item. On the index or list page, he can delete a list after a confirmation.

## Acceptance criteria

- **AC-1** — Given two lists created on different days, when the summaries are read, then the newer list comes first and each has its name, created date and progress.
- **AC-2** — Given a list with three items, when the second is dropped, then only that item is deleted, and the first and third keep their positions.
- **AC-3** — Given an unknown item ID, when it is dropped, then the service raises `NotFoundError`.
- **AC-4** — Given a list, when it is deleted, then the list is deleted and its items go with it (cascade).
- **AC-5** — Given an unknown list ID, when it is deleted, then the service raises `NotFoundError`.
- **AC-6** — Given the library page, when the menu is opened, then a "Reading lists" link leads to `/lists`.

## Tests

- `tests/unit/test_reading_lists.py::test_list_summaries_newest_first_with_progress` — AC-1.
- `tests/unit/test_reading_lists.py::test_drop_item_deletes_only_that_item` — AC-2.
- `tests/unit/test_reading_lists.py::test_drop_item_unknown_raises_not_found` — AC-3.
- `tests/unit/test_reading_lists.py::test_delete_list_deletes_list` — AC-4.
- `tests/unit/test_reading_lists.py::test_delete_list_unknown_raises_not_found` — AC-5.
- M-5, M-6, M-7 (manual) — AC-1, AC-2, AC-4 against a real database, and AC-6.

## Files

- `backend/src/services/reading_lists.py` — `list_summaries`, `drop_item`, `delete_list`.
- `backend/src/api/reading_lists.py` — `GET /lists`, `DELETE /lists/{id}/items/{item_id}`, `DELETE /lists/{id}`.
- `backend/src/templates/lists/index.html`, `lists/detail.html`.
- `frontend/index.html` — menu link.

## Out of scope

Add item, reorder, archive, rename.

## Notes

Use `hx-confirm` for delete. After deleting from the list page, respond with `HX-Redirect: /lists`. The cascade is a database `ON DELETE CASCADE`; the mock test checks the service call, and M-7 checks the cascade.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `ReadingListService.list_summaries` (newest first, sorted in Python, with progress), `drop_item`, `delete_list`, and a shared `_get_item` lookup that `toggle_tick` now uses too.
2. `ListSummary` schema.
3. Routes: `GET /lists` (index), `DELETE /lists/{list_id}/items/{item_id}` (empty body removes the item; progress updates out of band), `DELETE /lists/{list_id}` (`HX-Redirect: /lists`).
4. Templates: `lists/index.html`, `lists/_drop.html`, a Drop button in `lists/_item.html`, a Delete list button in `lists/detail.html`. Styles in `frontend/static/lists.css`.
5. "Reading lists" link in the library menu (`frontend/index.html`).

### Tests added

- `tests/unit/test_reading_lists.py` — `test_list_summaries_newest_first_with_progress`, `test_drop_item_deletes_only_that_item`, `test_drop_item_unknown_raises_not_found`, `test_drop_item_of_another_list_raises_not_found`, `test_delete_list_deletes_list`, `test_delete_list_unknown_raises_not_found`.

All six observed red (missing methods) before green.

Manual walkthrough (dev stack, built-in browser). `window.confirm` was stubbed to return true, because the pane cannot click a native confirm dialog; the `hx-confirm` attributes are in the templates.

- **M-5 (AC-1, AC-6)** — pass. The library menu shows "Reading lists", which opens `/lists`. After creating a second list, "Motivation sample" (0 of 3 read) shows above "Memory" (1 of 16 read), each with its created date.
- **M-6 (AC-2)** — pass. Dropped item 2 of "Memory". Items 1, 3 and 4 keep their order; 15 items remain; "1 of 15 read". Same after a reload.
- **M-7 (AC-4)** — pass. Deleted "Motivation sample" from the index. The browser returned to `/lists` with only "Memory" left. The library still reports 631 papers. The items were deleted by the database cascade: the ORM relationship uses `passive_deletes`, so without the `ON DELETE CASCADE` foreign key the delete would have failed.

### Suite result

`cd backend && uv run pytest` — 87 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 42 source files.

### Deviations from the plan

- Drop item asks for a confirmation too (`hx-confirm`). The spec asked for it on delete list only. Reason: a drop cannot be undone either.
- `list_summaries` sorts in Python, not in SQL, so the unit test proves the order without a database. A few lists make this free.
- The cascade was not checked with a direct database query.

### Follow-ups

None.

---

## Review — 2026-09-23

**Verdict:** pass

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_list_summaries_newest_first_with_progress`; M-5 |
| AC-2 | yes | `test_drop_item_deletes_only_that_item`; M-6 |
| AC-3 | yes | `test_drop_item_unknown_raises_not_found` |
| AC-4 | yes | `test_delete_list_deletes_list`; M-7 for the cascade |
| AC-5 | yes | `test_delete_list_unknown_raises_not_found` |
| AC-6 | yes | M-5, recorded in the build note |

Suite re-run by the reviewer: 87 passed; ruff and mypy clean.

### Drift

None. Add item, reorder, archive and rename were not built, as `concept.md` and the epic state.

### Findings

None that change behaviour. List names go into `hx-confirm` attributes through Jinja2 autoescape, so a quote in a name cannot break the markup. The menu link is plain HTML in `frontend/index.html`, with no new JavaScript. The deep pass ran inline, not through `/code-review`.

### Follow-ups

None.
