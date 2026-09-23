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

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. Slice 1 — `ReadingListParser.parse()` with Gemini structured output (`response_schema=list[ParsedItem]`), `ParsedItem` schema.
2. Slice 2 — `ReadingList` / `ReadingListItem` models (`read_at` included for epic 03, cascade delete on items), `ReadingListService.create_list` and `get_list`, model import in `create_tables()`.
3. Slice 3 — `jinja2` dependency, `api/reading_lists.py` (`GET /lists/new`, `POST /lists`, `GET /lists/{id}`), templates `base.html`, `lists/new.html`, `lists/detail.html`, `lists/_item.html`, `frontend/static/lists.css`, vendored `frontend/static/htmx.min.js` (htmx.org 2.0.4 from cdn.jsdelivr.net), router registered at `/lists`, `/lists` added to `NoCacheMiddleware`.
4. Rebuilt the dev API image for `jinja2` (asked and approved). `create_tables()` created `reading_lists` and `reading_list_items` in the dev database.

### Tests added

- `tests/unit/test_reading_list_parser.py` — `test_parses_items_in_order_with_notes`, `test_sends_the_raw_text_to_gemini`, `test_raises_when_api_key_missing`.
- `tests/unit/test_reading_lists.py` — `test_create_list_stores_items_with_positions`, `test_get_list_returns_the_list`, `test_get_list_unknown_raises_not_found`.

Manual walkthrough (dev stack, built-in browser, signed in):

- **M-3 (AC-3)** — pass. Pasted list one from the spike as "Memory". The page shows 16 items in the pasted order, each with title, authors, year and note. Gemini took 27 seconds (19:21:33 to 19:22:00).
- **M-9 (AC-4)** — pass. Without a session, `GET /lists/new` and `GET /lists/{id}` return 307 to `/auth/login`.

### Suite result

`cd backend && uv run pytest` — 76 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 42 source files.

### Deviations from the plan

- Slice 2 tests and code were written in one step, so the red run for the service was not observed; the parser slice was observed red (module missing) before green.
- The service takes parsed items, not the parser. The router calls the parser, then the service. Reason: the service tests then need no mock of our own parser.
- Added `test_sends_the_raw_text_to_gemini` and the two `get_list` tests beyond the plan.
- Styles go in a new static file `frontend/static/lists.css`, not inline, to keep templates free of style blocks.

### Follow-ups

- Parsing a 16-item list took 27 seconds inside the request. A 40-item list can pass 60 seconds. Check the cloudflared and Caddy timeouts before relying on it in production, or move parsing to the background.
- `ruff format --check` reports two files this epic does not touch: `src/api/papers.py` and `tests/unit/test_drive.py`.

---

## Review — 2026-09-23

**Verdict:** pass with follow-ups

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_parses_items_in_order_with_notes` |
| AC-2 | yes | `test_create_list_stores_items_with_positions` |
| AC-3 | yes | M-3, recorded in the build note (16 items in order with notes) |
| AC-4 | yes | M-9, recorded in the build note (307 to `/auth/login`) |
| AC-5 | yes | `test_raises_when_api_key_missing` |

Suite re-run by the reviewer: 76 passed; ruff and mypy clean. No inline JavaScript in the templates.

### Drift

None. The router sits at `/lists` behind session auth, the pages use Jinja2 and HTMX, the parser uses Gemini structured output, and ingestion is untouched, as `architecture.md` states. Nothing from `concept.md` Out of scope was built.

### Findings

1. Low — `api/reading_lists.py` `create_list`: if Gemini raises (missing key, network error), the POST returns a JSON 500. HTMX does not swap on a 500, so the form's indicator stops and the user sees no message. Epic 05 turns parse failures into a saved list; a missing key stays a silent 500.
2. Low — `GET /lists/{id}` for an unknown ID returns the global JSON 404, not an HTML page.
3. Low — Parsing runs inside the request (27 s for 16 items). Already recorded as a follow-up and as a phase risk.

The deep pass ran inline, not through `/code-review`.

### Follow-ups

- Check the proxy and tunnel timeouts against a 40-item parse, or parse in the background.
- Show an error message on the new-list form when the POST fails.
