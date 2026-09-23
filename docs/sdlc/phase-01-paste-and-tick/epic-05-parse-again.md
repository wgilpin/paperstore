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
