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

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. Fixed a test-order bug from epic 02: `tests/conftest.py` now imports every model, so SQLAlchemy can configure mappers when `test_reading_lists.py` runs alone. Before the fix, the file failed on its own (`paper_tags` not defined) and passed only in the full suite.
2. `ReadingListService.toggle_tick(list_id, item_id, db)` — sets or clears `read_at`; raises `NotFoundError` for an unknown item or an item of another list.
3. `ReadingListService.progress(reading_list)` returning `ListProgress(read, total)`.
4. `POST /lists/{list_id}/items/{item_id}/tick` returns the item fragment and the progress line out of band (`hx-swap-oob`).
5. Templates: checkbox in `lists/_item.html`, new `lists/_progress.html` and `lists/_tick.html`, progress line in `lists/detail.html`. Styles for the tick and progress in `frontend/static/lists.css`.

### Tests added

- `tests/unit/test_reading_lists.py` — `test_toggle_tick_sets_read_at`, `test_toggle_tick_clears_read_at`, `test_toggle_tick_unknown_item_raises_not_found`, `test_toggle_tick_item_of_another_list_raises_not_found`, `test_progress_counts_ticked_items`.

All five observed red (missing methods) before green.

Manual walkthrough (dev stack, built-in browser):

- **M-4 (AC-5, and AC-1 to AC-3 against a real database)** — pass. On "Memory", ticked items 1 and 3: "2 of 16 read". Reloaded: items 1 and 3 still ticked, "2 of 16 read". Unticked item 3: "1 of 16 read". Ticked items show struck through.

### Suite result

`cd backend && uv run pytest` — 81 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 42 source files.

### Deviations from the plan

- `toggle_tick` takes the list ID as well as the item ID, so a tick cannot reach an item through another list's URL. Added a test for it.
- The `conftest.py` fix touches a shared test file outside the epic's file list. It fixes a defect epic 02 introduced.

### Follow-ups

None.

---

## Review — 2026-09-23

**Verdict:** pass

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_toggle_tick_sets_read_at` |
| AC-2 | yes | `test_toggle_tick_clears_read_at` |
| AC-3 | yes | `test_progress_counts_ticked_items` |
| AC-4 | yes | `test_toggle_tick_unknown_item_raises_not_found` |
| AC-5 | yes | M-4, recorded in the build note |

Suite re-run by the reviewer: 81 passed; `test_reading_lists.py` also passes on its own (8 passed), which confirms the `conftest.py` fix.

### Drift

None. Paper items and `papers.read_at` were left for phase 02, as the epic states.

### Findings

None that change behaviour. The tick endpoint loads the list a second time to compute progress; at 10 to 40 items this costs nothing. The deep pass ran inline, not through `/code-review`.

### Follow-ups

None.
