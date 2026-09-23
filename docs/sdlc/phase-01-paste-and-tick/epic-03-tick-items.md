# Epic 03 — Tick items

**Phase:** 01 Paste and tick
**Goal:** Tick and untick items, and see the list's progress.
**Done criteria covered:** DC-4, DC-5

## Behaviour

Each item on a list page has a checkbox. Clicking it sends an HTMX request that sets or clears the item's `read_at` and swaps the item and the progress line. The list page shows "n of m read".

## Acceptance criteria

- **AC-1** — Given an unticked item, when it is toggled, then its `read_at` is set to the current time.
- **AC-2** — Given a ticked item, when it is toggled, then its `read_at` is cleared.
- **AC-3** — Given a list with four items and two ticked, when its progress is read, then it is 2 read of 4.
- **AC-4** — Given an item ID that does not exist, when it is toggled, then the service raises `NotFoundError`.
- **AC-5** — Given a ticked item, when the page is reloaded, then the item is still ticked.

## Tests

- `tests/unit/test_reading_lists.py::test_toggle_tick_sets_read_at` — AC-1.
- `tests/unit/test_reading_lists.py::test_toggle_tick_clears_read_at` — AC-2.
- `tests/unit/test_reading_lists.py::test_progress_counts_ticked_items` — AC-3.
- `tests/unit/test_reading_lists.py::test_toggle_tick_unknown_item_raises_not_found` — AC-4.
- M-4 (manual) — AC-5.

## Files

- `backend/src/services/reading_lists.py` — `toggle_tick`, `progress`.
- `backend/src/api/reading_lists.py` — `POST /lists/{id}/items/{item_id}/tick`.
- `backend/src/templates/lists/_item.html`, `lists/_progress.html`, `lists/detail.html`.

## Out of scope

Paper items and `papers.read_at` (phase 02).

## Notes

Reuse `NotFoundError` from `services/notes.py`, which the global handler already maps to 404. Use `hx-swap-oob` to update the progress line in the same response.
