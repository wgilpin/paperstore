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
