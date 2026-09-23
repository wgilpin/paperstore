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

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `safe_url` (http or https with a host, else `None`) and `ReadingListService.add_url`: an arXiv or alphaXiv host with an ID, a bioRxiv URL, or a URL that passes `pdf_check` becomes a `manual` candidate and goes to `importing`; any other http(s) URL becomes the plain link; other input raises `ValueError`, the item unchanged. Candidate source gains `manual`.
2. `POST /lists/{id}/items/{item_id}/link` starts the import when there is one, and returns the item row plus the status block out of band (`_item_and_status.html`), so the page polls during the import and reloads when it ends.
3. `_item.html`: "Add link" / "Change link" in a `<details>` element (no JavaScript) for items without a paper; links render only when `safe_url` accepts them (Jinja global).

### Tests added

- `tests/unit/test_reading_lists.py` — `test_add_arxiv_url_starts_import`, `test_add_pdf_url_starts_import`, `test_add_biorxiv_url_starts_import_without_pdf_check`, `test_add_other_url_sets_plain_link`, `test_add_url_refuses_other_schemes`, `test_safe_url_accepts_only_http`.

Red observed at collection (missing `safe_url`) before green.

Manual walkthrough (dev stack, "Memory" list):

- **M-2 (AC-1, AC-3, AC-4, DC-7)** — pass. `https://en.wikipedia.org/wiki/Spreading_activation` on "A spreading-activation theory…" became a plain link opening in a new tab. `javascript:alert(1)` on "Why there are complementary…" was refused with "Use a link that starts with http:// or https://." `https://arxiv.org/abs/1606.01164` on "Dense Associative Memory…" showed "Importing…" and "Importing 1 paper…", then linked to paper `38e9f3c0…` after the page reloaded by itself.

### Suite result

`cd backend && uv run pytest` — 133 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 44 source files.

### Deviations from the plan

- The route returns the status block out of band, so the page polls during a link import; not in the spec, needed for the item to update.
- "Change link" replaces an existing plain link; the spec said a new link replaces it, and the label says so.
- A bioRxiv URL skips the PDF check, since ingestion handles bioRxiv pages itself; one extra test covers it.

### Follow-ups

None.

---

## Review — 2026-09-23

**Verdict:** pass

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_add_arxiv_url_starts_import`; M-2 |
| AC-2 | yes | `test_add_pdf_url_starts_import`, `test_add_biorxiv_url_starts_import_without_pdf_check` |
| AC-3 | yes | `test_add_other_url_sets_plain_link`; M-2 |
| AC-4 | yes | `test_add_url_refuses_other_schemes`; M-2 |
| AC-5 | yes | `test_safe_url_accepts_only_http` (the helper `_item.html` uses) |

Suite re-run by the reviewer: 133 passed; ruff and mypy clean. No inline JavaScript.

### Drift

None. Paper URLs go through phase 02's importer and the existing ingestion.

### Findings

1. Low — `pdf_check` runs inside the request for a URL that is not arXiv or bioRxiv, up to its 15-second timeout. The form shows "Checking…".
2. Low — if Will adds a link to an item while a lookup thread is resolving that same item, the lookup can put it back in review afterwards. Rare, and the review page shows it.
3. Low — the server fetches URLs that Will types, as the library's own submit route already does. Single user, behind login.

The deep pass ran inline, not through `/code-review`. ISS-8 is resolved by this epic.

### Follow-ups

None.
