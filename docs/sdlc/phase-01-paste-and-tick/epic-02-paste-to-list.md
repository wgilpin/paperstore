# Epic 02 — Paste to list

**Phase:** 01 Paste and tick
**Goal:** Paste a reading list, parse it with Gemini, and see it as an ordered list page.
**Done criteria covered:** DC-3, DC-10

## Behaviour

Will opens `/lists/new`, pastes the text of a reading list and gives it a name. Gemini splits it into items. The app saves the list and redirects to `/lists/{id}`, which shows each item in order with its title, authors, year and note. This is the tracer: new tables, a Gemini call, a service, a router, Jinja2 and HTMX, end to end.

## Acceptance criteria

- **AC-1** — Given Gemini returns three items as JSON, when the parser runs, then it returns three `ParsedItem`s in the same order, with title, authors, year, note and the raw citation line.
- **AC-2** — Given three parsed items, when the service creates a list, then the list row holds the name and the raw text, and three item rows hold positions 0, 1 and 2.
- **AC-3** — Given a saved list, when `/lists/{id}` is opened, then the items appear in position order with their title, authors, year and note.
- **AC-4** — Given no session, when `/lists/new` or `/lists/{id}` is requested, then the response redirects to `/auth/login`.
- **AC-5** — Given `GEMINI_API_KEY` is not set, when the parser runs, then it raises `ValueError`, matching `GeminiService`.

## Tests

- `tests/unit/test_reading_list_parser.py::test_parses_items_in_order_with_notes` — AC-1.
- `tests/unit/test_reading_list_parser.py::test_raises_when_api_key_missing` — AC-5.
- `tests/unit/test_reading_lists.py::test_create_list_stores_items_with_positions` — AC-2.
- M-3 (manual) — AC-3.
- M-9 (manual) — AC-4.

## Files

- `backend/pyproject.toml`, `backend/uv.lock` — add `jinja2`.
- `backend/src/models/reading_list.py` — `ReadingList`, `ReadingListItem` (`read_at` included now, used in epic 03).
- `backend/src/db.py` — import the new models in `create_tables()`.
- `backend/src/schemas/reading_list.py` — `ParsedItem` and view models.
- `backend/src/services/reading_list_parser.py` — Gemini call with a pydantic response schema.
- `backend/src/services/reading_lists.py` — `create_list`, `get_list`.
- `backend/src/api/reading_lists.py` — `GET /lists/new`, `POST /lists`, `GET /lists/{id}`.
- `backend/src/templates/base.html`, `lists/new.html`, `lists/detail.html`, `lists/_item.html`.
- `backend/src/main.py` — register the router at `/lists`; add `/lists` to `NoCacheMiddleware`.
- `frontend/static/htmx.min.js` — vendored.

## Out of scope

Ticks, the lists index, drop, delete, parse failure handling (epic 05), section headings.

## Notes

- Do not put the router under `/api/`. `AuthMiddleware` exempts `/api/`.
- Templates live under `backend/src/templates/` so the dev volume mount (`./backend/src:/app/src`) and the Dockerfile copy already include them.
- Parser model: `GEMINI_PDF_MODEL`. Mirror the key and model checks in `services/gemini.py`.
- Downloading `htmx.min.js` is a file download. Ask the user before fetching it, and pin the version in a comment.
- The form shows an HTMX loading indicator while Gemini runs.
