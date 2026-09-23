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
