# Epic 02 — Outside lookup

**Phase:** 02 Find and import papers
**Goal:** Find papers that are not in the library, judge the matches, and run lookup in the background.
**Done criteria covered:** DC-2, DC-3, DC-4, DC-5 (record only)

## Behaviour

After the library, lookup tries an arXiv ID in the citation, then OpenAlex, then arXiv title search. Each item gets an outcome: in library, free PDF, record only, or not found. Only a confident match is pre-selected on the review page. Lookup runs in a background thread; the list page shows "Looking up n of m" and polls until it ends. A new list, and a successful parse again, start lookup by themselves. Accepting a record-only match makes the item a link to its DOI.

## Acceptance criteria

- **AC-1** — Given a citation with an arXiv ID, when it is looked up, then the arXiv record for that ID is the candidate, checked against the citation title.
- **AC-2** — Given no arXiv ID and an OpenAlex result with a matching title, year and a PDF link that returns a PDF, when it is looked up, then the outcome is free PDF.
- **AC-3** — Given an OpenAlex result with a DOI and no fetchable PDF, when it is looked up, then the outcome is record only.
- **AC-4** — Given OpenAlex finds nothing that matches, when arXiv title search finds a match, then that is the candidate; when neither does, the outcome is not found.
- **AC-5** — Given a candidate whose title matches but whose year is 18 years off and whose authors differ (the Singh 2004 case), when it is judged, then it is weak. Given an OpenAlex `book-review` or `paratext`, then it is rejected.
- **AC-6** — Given a list with two unlinked items and one linked item, when lookup runs, then the two unlinked items get candidates and status `review`, and the linked item is untouched.
- **AC-7** — Given an accepted record-only match, when the review is submitted, then the item's `url` is the DOI URL and its status is `done`.

## Tests

- `tests/unit/test_citation_resolver.py::test_arxiv_id_in_citation_is_used_first` — AC-1.
- `tests/unit/test_citation_resolver.py::test_openalex_used_when_no_arxiv_id`, `::test_outcome_free_pdf` — AC-2.
- `tests/unit/test_citation_resolver.py::test_outcome_record_only` — AC-3.
- `tests/unit/test_citation_resolver.py::test_arxiv_search_used_when_openalex_misses`, `::test_outcome_not_found` — AC-4.
- `tests/unit/test_citation_resolver.py::test_confident_needs_year_or_author`, `::test_title_only_match_is_weak`, `::test_book_review_is_rejected` — AC-5.
- `tests/unit/test_openalex_client.py::test_parses_best_result` — AC-2 parsing.
- `tests/unit/test_reading_lists.py::test_run_lookup_stores_candidates_for_unlinked_items`, `::test_run_lookup_skips_linked_items` — AC-6.
- `tests/unit/test_reading_lists.py::test_accept_record_only_sets_doi_link` — AC-7.
- M-2 — background progress, the page stays usable, auto-start.

## Files

- `backend/src/services/openalex_client.py` — new, `httpx`.
- `backend/src/services/citation_resolver.py` — arXiv ID, OpenAlex, arXiv search sources; `is_confident`; PDF check.
- `backend/src/services/reading_lists.py` — `run_lookup` for the background thread; `find_papers` starts it.
- `backend/src/api/reading_lists.py` — start lookup after create and parse again; `GET /lists/{id}/lookup-status`.
- `backend/src/templates/lists/detail.html`, `lists/_lookup_status.html`, `lists/review.html`.

## Out of scope

Importing PDFs (epic 03). Search again for one item (phase 03).

## Notes

- arXiv asks for 3 seconds between calls. Reuse one arXiv client per lookup run, or sleep between calls.
- OpenAlex: `GET https://api.openalex.org/works?search=<title>&per-page=5`, no key, no `mailto` (open question in `architecture.md`).
- PDF check: a ranged `GET` of the first bytes; `%PDF` or a PDF content type means free PDF.
- The spike's title rule was too loose. Title similarity alone must never make a match confident.
- Running lookups live in memory, like the batch loop. A restart ends them; the items stay `new` and "Find papers" starts again.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `services/openalex_client.py`: `OpenAlexClient.search` (title search, five results, `[]` on any error) and `OpenAlexWork` (bare lower-case DOI, PDF links, arXiv ID from arXiv landing pages).
2. `citation_resolver.py`: `arxiv_record` (a cited arXiv ID), `openalex_search`, `arxiv_search` (words of the title as `ti:` terms), `pdf_check` (first 1 KB, `%PDF` or a PDF content type), a process-wide 3-second arXiv pause. `resolve` now returns a confident library match first, then tries outside sources, and falls back to a weak library match. An outside match whose arXiv ID or DOI is in the library becomes an in-library match. OpenAlex `book-review`, `paratext`, `erratum` and `retraction` are dropped.
3. Service: `lookup_list` (commits per item) replaces `find_papers`; `start_lookup` / `lookup_running` / `_lookup_thread` run it in a daemon thread with its own session; `lookup_status`; `_accept` handles record-only (DOI link) and, until epic 03, free PDF (a link to it).
4. Routes: `POST /lists/{id}/find` starts the thread and reloads the list; `GET /lists/{id}/lookup-status`; list creation and a successful parse again start lookup. `lists/_lookup_status.html` polls every 2 seconds while a lookup runs.
5. `lists/_item.html` shows an item's `url` as an external link (new tab). Needed for DC-5's DOI link; not listed in the epic's files.

### Tests added

- `tests/unit/test_openalex_client.py` — `test_parses_best_result`, `test_returns_empty_on_http_error`.
- `tests/unit/test_citation_resolver.py` — `test_arxiv_id_in_citation_is_used_first`, `test_openalex_used_when_no_arxiv_id`, `test_outcome_free_pdf`, `test_outcome_record_only`, `test_arxiv_search_used_when_openalex_misses`, `test_outcome_not_found`, `test_book_review_is_rejected`, `test_outside_match_already_in_library_by_doi`, `test_confident_needs_year_or_author`, `test_title_only_match_is_weak`. `test_no_library_match_returns_none` now also stubs the outside sources.
- `tests/unit/test_reading_lists.py` — `test_run_lookup_stores_candidates_for_unlinked_items`, `test_run_lookup_skips_linked_items`, `test_accept_record_only_sets_doi_link`.

Red observed at collection (missing modules) before green.

Manual walkthrough (dev stack, real arXiv and OpenAlex):

- **M-2 (AC-6, DC-4)** — pass. Pasted a 12-item list as "Lookup test". Lookup started by itself; the page showed "Looking up papers… 4 of 12", then "5 of 12"; a tick worked during the lookup. It ended at "Review matches (12)". Outcomes: 5 free PDF (Krotov 2016, Ramsauer, Krotov 2025, Kleyko, Tolman-Eichenbaum via bioRxiv), 7 record only. Only the Solms book was weak and not pre-selected. Singh 2004 matched the 2005 report, not the 2022 paper that fooled the spike.
- **M-3, record-only part (AC-7)** — pass. Applying the review turned record-only items into DOI links that open in a new tab. The rejected item and the unselected weak item stayed text.

### Suite result

`cd backend && uv run pytest` — 117 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 44 source files.

### Deviations from the plan

- `find_papers` became `lookup_list` plus a background thread; `POST /lists/{id}/find` now returns to the list page, which shows progress, not straight to the review page.
- An accepted free-PDF match becomes a link to it until epic 03 adds the import.
- `_item.html` renders `url` links, which DC-5 needs and the epic's file list missed.
- The lookup thread is tested through `lookup_list` with an injected fake resolver; the thread wrapper itself has no unit test.

### Follow-ups

- Collins 1975 matched a 1988 book reprint (confident on the author). Among title matches, prefer the record closest to the cited year.

---

## Review — 2026-09-23

**Verdict:** pass with follow-ups

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_arxiv_id_in_citation_is_used_first` |
| AC-2 | yes | `test_openalex_used_when_no_arxiv_id`, `test_outcome_free_pdf`, `test_parses_best_result` |
| AC-3 | yes | `test_outcome_record_only` |
| AC-4 | yes | `test_arxiv_search_used_when_openalex_misses`, `test_outcome_not_found` |
| AC-5 | yes | `test_title_only_match_is_weak`, `test_confident_needs_year_or_author`, `test_book_review_is_rejected` |
| AC-6 | yes | `test_run_lookup_stores_candidates_for_unlinked_items`, `test_run_lookup_skips_linked_items`; M-2 |
| AC-7 | yes | `test_accept_record_only_sets_doi_link`; M-3 |

Suite re-run by the reviewer: 117 passed; ruff and mypy clean. No test reaches the network.

### Drift

- The lookup runs in a background thread; `architecture.md` names a thread for the import only. The phase plan recorded this as an addition, and it follows the same pattern. No contradiction.
- None against `concept.md`.

### Findings

1. Low — `_item.html` puts `item.url` into an `href`. Jinja2 escapes it, but it does not check the scheme; a `javascript:` URL from OpenAlex data, or one typed in phase 03, would render as a live link. Allow only `http` and `https`.
2. Low — `is_confident` accepts an author match at any distance in years, so a reprint can win over the original (Collins 1975 → 1988 book chapter, seen in M-2).
3. Low — `pdf_check` fetches URLs that OpenAlex supplies, from the server. One user and a public API, so the risk is small.

The deep pass ran inline, not through `/code-review`.

### Follow-ups

- Accept only `http` and `https` item URLs.
- Prefer the title match closest to the cited year.
