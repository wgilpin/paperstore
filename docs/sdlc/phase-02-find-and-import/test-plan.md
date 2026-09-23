# Test plan — Phase 02 Find and import papers

## Coverage

Services are unit-tested with a mocked session, a mocked `httpx`, a mocked arXiv client and a mocked `IngestionService`. Routes and templates are proved by the manual walkthrough, as the constitution requires.

| Done criterion | Proved by | Kind |
|---|---|---|
| DC-1 | `test_citation_resolver.py::test_library_match_by_arxiv_id`, `::test_library_match_by_doi`, `::test_library_title_match_used_when_ids_miss`; M-1 (title similarity in SQL) | automated + manual |
| DC-2 | `test_citation_resolver.py::test_arxiv_id_in_citation_is_used_first`, `::test_openalex_used_when_no_arxiv_id`, `::test_arxiv_search_used_when_openalex_misses`, `::test_outcome_free_pdf`, `::test_outcome_record_only`, `::test_outcome_not_found`; `test_openalex_client.py::test_parses_best_result`; M-2 | automated + manual |
| DC-3 | `test_citation_resolver.py::test_confident_needs_year_or_author`, `::test_title_only_match_is_weak`, `::test_book_review_is_rejected` | automated |
| DC-4 | `test_reading_lists.py::test_run_lookup_stores_candidates_for_unlinked_items`, `::test_run_lookup_skips_linked_items`; M-2 (progress, page stays usable, auto-start) | automated + manual |
| DC-5 | `test_reading_lists.py::test_accept_library_match_links_item`, `::test_accept_record_only_sets_doi_link`, `::test_reject_leaves_text_item`, `::test_accept_free_pdf_marks_importing`; M-3 | automated + manual |
| DC-6 | `test_reading_lists.py::test_import_links_new_paper_and_sets_doi`, `::test_import_duplicate_links_existing_paper`, `::test_import_failure_marks_item_and_keeps_url`; M-4 | automated + manual |
| DC-7 | M-5 | manual |
| DC-8 | `test_reading_lists.py::test_tick_paper_item_sets_paper_read_at`, `::test_progress_counts_paper_read_at`; M-6 | automated + manual |
| DC-9 | `test_reading_lists.py::test_reset_stuck_imports_marks_import_failed` | automated |
| DC-10 | M-7 | manual |

### Manual walkthrough

- **M-1** — On a list that holds a paper already in the library under a slightly different title, click "Find papers". The review page shows that library paper as the match.
- **M-2** — Paste list one from the spike as a new list. Lookup starts by itself. The list page shows progress and can be scrolled and ticked during lookup. When it finishes, the review page shows an outcome for every item, and weak matches are flagged and not pre-selected.
- **M-3** — Accept a library match, a record-only match and a free-PDF match; reject one. The library match links at once, the record-only item becomes a DOI link, the rejected item stays text, the free-PDF item shows "importing".
- **M-4** — The free-PDF item links to its new paper when the import ends. One item that is already in the library links to the existing paper. The new paper's DOI is set.
- **M-5** — Click a linked paper item. `/paper.html?id=<id>` opens.
- **M-6** — Put the same paper on two lists. Tick it on one. The other list shows it ticked, and both progress lines count it.
- **M-7** — In the dev API container, `DRIVE_FOLDER_ID` is empty or equals `DEV_DRIVE_FOLDER_ID`, never the production folder ID.

## Gaps

None. DC-7 and DC-10 are manual only: a link in a template and a container setting.

## How to run

```bash
cd backend && uv run pytest
```

Then `cd backend && uv run ruff check src tests && uv run mypy src`.

## Test data

- Mocked `Session`, as in the existing tests.
- Fixed OpenAlex JSON for: an exact match with a PDF link, a match with a DOI and no PDF, a book review, and no results.
- ParsedItem-like citations from the two spike lists, including the Singh 2004 and Solms cases.
