# Test plan — Phase 03 The manual paths

## Coverage

Services are unit-tested with a mocked session and fake ingestion. Routes, templates and the library page are proved by the manual walkthrough.

| Done criterion | Proved by | Kind |
|---|---|---|
| DC-1 | `test_reading_lists.py::test_upload_pdf_links_item_and_sets_doi`, `::test_upload_non_pdf_is_refused`, `::test_upload_duplicate_links_existing_paper`, `::test_upload_only_for_items_without_paper`; M-1 | automated + manual |
| DC-2 | `test_reading_lists.py::test_add_arxiv_url_starts_import`, `::test_add_pdf_url_starts_import`, `::test_add_other_url_sets_plain_link`, `::test_add_url_refuses_other_schemes`; M-2 | automated + manual |
| DC-3 | `test_reading_lists.py::test_search_again_resets_item_for_lookup`, `::test_search_again_refused_for_linked_item`; M-3 | automated + manual |
| DC-4 | `test_reading_lists.py::test_unlink_clears_paper`; M-3 | automated + manual |
| DC-5 | `test_reading_lists.py::test_retry_sets_importing_again`, `::test_retry_refused_unless_import_failed`; M-3 | automated + manual |
| DC-6 | `test_search.py::test_read_filter_expressions`, `::test_read_filter_applied_to_listing`; M-4 | automated + manual |
| DC-7 | `test_reading_lists.py::test_safe_url_accepts_only_http`; M-2 | automated + manual |

### Manual walkthrough

- **M-1** — On a record-only item, upload a PDF. The item links to a new paper that opens with a click. Upload a `.txt` renamed `.pdf` to another item: a message, no change.
- **M-2** — Add an arXiv URL to a text item: "Importing…", then linked. Add `https://en.wikipedia.org/wiki/Hopfield_network` to another: a plain link that opens in a new tab. Try `javascript:alert(1)`: refused.
- **M-3** — Search again on a text item: it returns to review with a fresh match. Unlink a paper item: it becomes text, the paper stays in the library. Retry an "import failed" item.
- **M-4** — On the library page choose Unread, then Read: the counts change and match the papers ticked on lists; combine with a tag and a search term.

## Gaps

None.

## How to run

```bash
cd backend && uv run pytest
```

Then `cd backend && uv run ruff check src tests && uv run mypy src`.

## Test data

- Mocked `Session`; fake ingestion objects as in phase 02.
- Bytes starting with `%PDF` and bytes that do not.
