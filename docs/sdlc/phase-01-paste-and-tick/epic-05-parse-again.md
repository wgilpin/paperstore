# Epic 05 — Parse again

**Phase:** 01 Paste and tick
**Goal:** Keep a list whose parse failed, and parse it again.
**Done criteria covered:** DC-9

## Behaviour

If Gemini fails, returns nothing, or returns invalid JSON, the list is still saved with its raw text and no items. The list page says parsing failed, shows the raw text, and offers "parse again". A successful parse again replaces the items.

## Acceptance criteria

- **AC-1** — Given Gemini returns invalid JSON, when the parser runs, then it returns an empty list and does not raise.
- **AC-2** — Given Gemini returns an empty response, when the parser runs, then it returns an empty list.
- **AC-3** — Given the parser returns no items, when a list is created, then the list is saved with its raw text, no items, and a parse-failed flag.
- **AC-4** — Given a list with a parse-failed flag, when parse again succeeds with two items, then the list has those two items and the flag is cleared.
- **AC-5** — Given a list whose parse failed, when its page opens, then it shows a failure message, the raw text, and a "parse again" button.

## Tests

- `tests/unit/test_reading_list_parser.py::test_returns_empty_on_invalid_json` — AC-1.
- `tests/unit/test_reading_list_parser.py::test_returns_empty_on_empty_response` — AC-2.
- `tests/unit/test_reading_lists.py::test_create_list_with_no_items_marks_parse_failed` — AC-3.
- `tests/unit/test_reading_lists.py::test_parse_again_replaces_items` — AC-4.
- M-8 (manual) — AC-5.

## Files

- `backend/src/models/reading_list.py` — `parse_failed` column.
- `backend/src/services/reading_list_parser.py` — failure paths.
- `backend/src/services/reading_lists.py` — `parse_again`.
- `backend/src/api/reading_lists.py` — `POST /lists/{id}/parse`.
- `backend/src/templates/lists/detail.html`.

## Out of scope

Editing the raw text before parsing again.

## Notes

A Gemini network error must also give an empty result, not a 500. Log the error. Parse again on a list that already has items replaces them, so the button shows only when `parse_failed` is set.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `ReadingListParser.parse` returns `[]` when Gemini's output does not match the schema, and when the Gemini call raises (logged). A missing key or model still raises `ValueError`.
2. `ReadingList.parse_failed` column (default false), plus an idempotent `ALTER TABLE reading_lists ADD COLUMN IF NOT EXISTS parse_failed` in `create_tables()` for databases that already have the table. The dev API applied it on reload.
3. `create_list` marks a list with no items as `parse_failed`. New `parse_again` replaces the items and clears the flag when items are found. Shared `_to_rows` helper.
4. `POST /lists/{list_id}/parse` parses the saved raw text again and reloads the page.
5. `lists/detail.html` shows a failure notice, a "Parse again" button, and the raw text when `parse_failed` is set. Styles in `frontend/static/lists.css`.

### Tests added

- `tests/unit/test_reading_list_parser.py` — `test_returns_empty_on_invalid_json`, `test_returns_empty_on_empty_response`, `test_returns_empty_on_gemini_error`.
- `tests/unit/test_reading_lists.py` — `test_create_list_with_no_items_marks_parse_failed`, `test_create_list_with_items_is_not_marked_parse_failed`, `test_parse_again_replaces_items`, `test_parse_again_with_no_items_keeps_parse_failed`.

Six observed red before green. `test_returns_empty_on_empty_response` passed at once: epic 02 already treated a missing response as `[]`.

Manual walkthrough (dev stack, built-in browser):

- **M-8 (AC-5)** — pass, by a changed method. Created "Not a list" from a pasted chat message with no reading list in it. Gemini returned 0 items. The page shows "Parsing failed. No items were found in the pasted text. The text is kept below.", the raw text, and a "Parse again" button. Clicking "Parse again" sent `POST /lists/{id}/parse` (204); Gemini again returned 0 items and the notice stayed.

### Suite result

`cd backend && uv run pytest` — 94 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 42 source files.

### Deviations from the plan

- M-8 used a paste with no reading list instead of an invalid `GEMINI_API_KEY`. Reason: swapping the key needs two dev container restarts. The page state is the same either way. As a result, the successful "parse again" path (items appear, notice goes) is proved by `test_parse_again_replaces_items` only, not in the browser.
- A failed parse of a real list is not distinguished from text with no list in it. Both show the same notice.
- Added two tests beyond the plan: `test_returns_empty_on_gemini_error` and the no-items cases.

### Follow-ups

None.

---

## Review — 2026-09-23

**Verdict:** pass with follow-ups

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_returns_empty_on_invalid_json` |
| AC-2 | yes | `test_returns_empty_on_empty_response` |
| AC-3 | yes | `test_create_list_with_no_items_marks_parse_failed` |
| AC-4 | yes | `test_parse_again_replaces_items` |
| AC-5 | yes | M-8, recorded in the build note |

Suite re-run by the reviewer: 94 passed; ruff and mypy clean.

### Drift

None. Editing the raw text before parsing again was not built, as the epic states.

### Findings

1. Low — `POST /lists/{id}/parse` works on any list, not only a failed one. The button shows only when `parse_failed` is set, but a direct request on a parsed list replaces its items and loses their ticks. One user, no link to it: low risk.
2. Low — When "parse again" fails a second time, the page reloads with the same notice and no sign that a retry happened.

The deep pass ran inline, not through `/code-review`.

### Follow-ups

- Refuse `parse_again` on a list that is not marked `parse_failed`.
