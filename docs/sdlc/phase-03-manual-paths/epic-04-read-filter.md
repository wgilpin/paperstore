# Epic 04 — Read filter

**Phase:** 03 The manual paths
**Goal:** Filter the library by read state.
**Done criteria covered:** DC-6

## Behaviour

The library page gets a Read select (All, Unread, Read) next to Sort. It adds `read=unread` or `read=read` to the existing `/papers` request. `SearchService.search` filters on `papers.read_at` in both its listing and its full-text path, together with tag, sort and paging.

## Acceptance criteria

- **AC-1** — Given `read="unread"`, when the filter expression is built, then it is `papers.read_at IS NULL`; given `read="read"`, `papers.read_at IS NOT NULL`; given `None`, no filter.
- **AC-2** — Given `read="read"` and no query, when the library is listed, then the read filter is applied to the query.
- **AC-3** — Given the library page, when Unread or Read is chosen, then the list and the count change, and a tag or search term still applies.

## Tests

- `tests/unit/test_search.py::test_read_filter_expressions` — AC-1.
- `tests/unit/test_search.py::test_read_filter_applied_to_listing` — AC-2.
- M-4 — AC-3.

## Files

- `backend/src/services/search.py` — `read` parameter, `read_filter`.
- `backend/src/api/papers.py` — `read` query parameter on `GET /papers`.
- `frontend/index.html` — the select.
- `frontend/static/index.js` — send the parameter; reload on change.

## Out of scope

A read indicator on each library card; ticking from the library page.

## Notes

`src/api/papers.py` fails `ruff format --check` today (ISS-5). Edit it without reformatting the whole file.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `search.py`: `ReadFilter`, `read_filter` (`papers.read_at IS NULL` / `IS NOT NULL` / none), and a `read` parameter on `SearchService.search`, applied in both the listing and the full-text path.
2. `api/papers.py`: `read: Literal["read", "unread"] | None` on `GET /papers` (3 lines changed; the file is not reformatted, ISS-5 stays open).
3. `frontend/index.html`: a "Show: All / Unread / Read" select next to Sort; `index.js` bumped to `?v=5`.
4. `frontend/static/index.js`: restores `read` from the URL, sends it with the existing fetch, keeps it in the URL, and reloads page 1 on change (10 lines, in the page's existing vanilla JS).

### Tests added

- `tests/unit/test_search.py` — `test_read_filter_expressions`, `test_read_filter_applied_to_listing`, `test_no_read_filter_by_default`.

Red observed at collection (missing `read_filter`) before green.

Manual walkthrough (dev library, 635 papers):

- **M-4 (AC-3)** — pass. All 635, Unread 634, Read 1 (Titans, the only paper ticked through a list); the URL keeps `?read=read`. With the search "memory": All 58, Unread 57, Read 1. With the tag "AI": 48, 48 unread, 0 read. `GET /papers?read=maybe` returns 422. The first try showed no change, because the browser held the old `index.js?v=4`; bumping the version fixed it.

### Suite result

`cd backend && uv run pytest` — 142 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 44 source files.

### Deviations from the plan

- Bumped the `index.js` cache-busting version in `index.html`; without it, browsers keep the old script.
- Added `test_no_read_filter_by_default`.

### Follow-ups

None.

---

## Review — 2026-09-23

**Verdict:** pass

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_read_filter_expressions` (compiled SQL) |
| AC-2 | yes | M-4 against the real database; `test_read_filter_applied_to_listing` checks the clause handed to the query |
| AC-3 | yes | M-4, recorded in the build note |

`test_read_filter_applied_to_listing` checks what the service passes to a mocked query, so on its own it asserts a mock. M-4 proves the behaviour on the real database, which is why AC-2 counts as met.

Suite re-run by the reviewer: 142 passed; ruff and mypy clean. The JavaScript lives in the existing static file; nothing inline.

### Drift

- `concept.md` and the phase plan asked for a library read filter; built as planned.
- The existing library page stays vanilla JS, against the HTMX preference. Converting it was out of scope, and the change is 10 lines.

### Findings

None that change behaviour. The deep pass ran inline, not through `/code-review`.

### Follow-ups

None.
