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
