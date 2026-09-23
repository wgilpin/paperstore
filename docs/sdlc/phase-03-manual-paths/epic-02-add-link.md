# Epic 02 — Add link

**Phase:** 03 The manual paths
**Goal:** Give an item a URL: import it when it is a paper, keep it as a link otherwise.
**Done criteria covered:** DC-2, DC-7

## Behaviour

An item without a paper shows "Add link". Will pastes a URL. An arXiv, alphaXiv or bioRxiv URL, or a URL that serves a PDF, is imported in the background with phase 02's importer and then linked. Any other `http(s)` URL becomes the item's plain link. Other schemes are refused. The list page only renders `http(s)` URLs as links.

## Acceptance criteria

- **AC-1** — Given an arXiv or alphaXiv URL, when it is added, then the item is `importing` with the arXiv ID as its source.
- **AC-2** — Given a bioRxiv URL, or a URL that passes the PDF check, when it is added, then the item is `importing` with that URL as its source.
- **AC-3** — Given any other `https` URL, when it is added, then it is the item's `url` and the item is `done`.
- **AC-4** — Given `javascript:alert(1)`, `ftp://…` or an empty string, when it is added, then the service refuses it and the item does not change.
- **AC-5** — Given a stored URL that is not `http(s)`, when the item is rendered, then it shows as text.

## Tests

- `tests/unit/test_reading_lists.py::test_add_arxiv_url_starts_import` — AC-1.
- `tests/unit/test_reading_lists.py::test_add_pdf_url_starts_import` — AC-2.
- `tests/unit/test_reading_lists.py::test_add_other_url_sets_plain_link` — AC-3.
- `tests/unit/test_reading_lists.py::test_add_url_refuses_other_schemes` — AC-4.
- `tests/unit/test_reading_lists.py::test_safe_url_accepts_only_http` — AC-5 (the helper the template uses).
- M-2.

## Files

- `backend/src/services/reading_lists.py` — `add_url`, `safe_url`.
- `backend/src/schemas/reading_list.py` — candidate source `manual`.
- `backend/src/api/reading_lists.py` — `POST /lists/{id}/items/{item_id}/link`; `safe_url` as a template global.
- `backend/src/templates/lists/_item.html`.

## Out of scope

Editing or removing an existing link (a new link replaces it).

## Notes

- Reuse `pdf_check` from `citation_resolver` and `is_biorxiv_url` from `biorxiv_client`.
- Resolves ISS-8.
