# Epic 01 — Library match

**Phase:** 02 Find and import papers
**Goal:** Link list items to papers already in the library, open them with a click, and share their ticks.
**Done criteria covered:** DC-1, DC-5 (library match and reject), DC-7, DC-8

## Behaviour

A list page gets a "Find papers" button. It looks each unlinked item up in the library by arXiv ID, DOI, then title similarity, and opens a review page that shows each match. Will accepts or rejects the matches in one submit. An accepted item links to its paper: its title opens `/paper.html?id=<id>`, and its tick is the paper's `read_at`, shared by every list.

## Acceptance criteria

- **AC-1** — Given an item whose citation holds an arXiv ID that a library paper has, when it is looked up, then that paper is its confident match.
- **AC-2** — Given an item whose DOI a library paper has, when it is looked up, then that paper is its confident match.
- **AC-3** — Given an item with no ID match and a library paper with a close title and the same year, when it is looked up, then that paper is its match.
- **AC-4** — Given a reviewed item whose library match Will accepts, when the review is submitted, then the item's `paper_id` is set and its status is `done`. A rejected item keeps no `paper_id`.
- **AC-5** — Given a paper item, when it is ticked, then `papers.read_at` is set; when it is unticked, it is cleared. The item's own `read_at` is not used.
- **AC-6** — Given a list with one paper item whose paper has `read_at` set and one unticked text item, when progress is read, then it is 1 of 2.
- **AC-7** — Given a linked paper item on the list page, when its title is clicked, then `/paper.html?id=<paper id>` opens.

## Tests

- `tests/unit/test_citation_resolver.py::test_library_match_by_arxiv_id` — AC-1.
- `tests/unit/test_citation_resolver.py::test_library_match_by_doi` — AC-2.
- `tests/unit/test_citation_resolver.py::test_library_title_match_used_when_ids_miss` — AC-3 (the SQL itself: M-1).
- `tests/unit/test_reading_lists.py::test_accept_library_match_links_item`, `::test_reject_leaves_text_item` — AC-4.
- `tests/unit/test_reading_lists.py::test_tick_paper_item_sets_paper_read_at` — AC-5.
- `tests/unit/test_reading_lists.py::test_progress_counts_paper_read_at` — AC-6.
- M-1, M-3 (library part), M-5, M-6 — manual.

## Files

- `backend/src/models/paper.py` — `read_at`, `doi`.
- `backend/src/models/reading_list.py` — `paper_id` (→ `papers.id`, `ON DELETE SET NULL`), `url`, `status`, `candidate_*`, relationship to `Paper`.
- `backend/src/db.py` — `ALTER TABLE … ADD COLUMN IF NOT EXISTS` for the new columns; unique index on `papers.doi`.
- `backend/src/schemas/reading_list.py` — `Candidate`.
- `backend/src/services/citation_resolver.py` — library source and the resolver shell.
- `backend/src/services/reading_lists.py` — `find_papers` (library only, run in the request for this epic), `apply_review`, paper-aware `toggle_tick` and `progress`.
- `backend/src/api/reading_lists.py` — `POST /lists/{id}/find`, `GET /lists/{id}/review`, `POST /lists/{id}/review`.
- `backend/src/templates/lists/review.html`, `lists/_item.html`, `lists/detail.html`, `frontend/static/lists.css`.

## Out of scope

Outside sources, background lookup, imports, DOI links.

## Notes

- Title similarity: `similarity(papers.title, :title) >= 0.6` from `pg_trgm`, best first. Apply the year or author check from DC-3 to call it confident; epic 02 adds the full rule.
- The arXiv ID in a citation: reuse `extract_arxiv_id` on the citation text; catch its `ValueError`.
- Item status values: `new` (default, including every phase 01 item), `review`, `importing`, `done`, `import_failed`.
- Schema changes run on the dev database only. The production database gets them when Will deploys.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `Paper.read_at`, `Paper.doi`; `ReadingListItem.paper_id` (`ON DELETE SET NULL`), `url`, `status` (default `new`), `outcome`, `candidate_json` with a typed `candidate` property, `is_read`, and a `paper` relationship. Idempotent `ALTER`s and a unique index on `papers.doi` in `create_tables()`; the dev database took them on reload.
2. `Candidate` and `Outcome` schemas.
3. `services/citation_resolver.py`: library lookups by arXiv ID and DOI written in the citation, then `pg_trgm` title similarity (≥ 0.6, best five); `title_similarity`, `is_confident` (title ≥ 0.85 plus year ±1 or a shared surname).
4. Service: `find_papers` (library only, in the request), `review_items`, `apply_review` with an `_accept` helper; `toggle_tick` and `progress` use the paper's `read_at` for paper items.
5. Routes `POST /lists/{id}/find`, `GET /lists/{id}/review`, `POST /lists/{id}/review`; `lists/review.html`; "Find papers (n)" and "Review matches (n)" on the list page; linked titles open `/paper.html?id=<paper id>`.

### Tests added

- `tests/unit/test_citation_resolver.py` — `test_library_match_by_arxiv_id`, `test_library_match_by_doi`, `test_library_title_match_used_when_ids_miss`, `test_no_library_match_returns_none`.
- `tests/unit/test_reading_lists.py` — `test_accept_library_match_links_item`, `test_reject_leaves_text_item`, `test_tick_paper_item_sets_paper_read_at`, `test_progress_counts_paper_read_at`.

All observed red (missing `Candidate` and resolver module) before green.

Manual walkthrough (dev stack, built-in browser):

- **M-1 (AC-3, the SQL)** — pass. New list "Shared test" cites "StoryScope: investigating idiosyncrasies of AI fiction" with no ID. Lookup matched the library paper "StoryScope: Investigating idiosyncrasies in AI fiction" as a confident match.
- **M-3, library part (AC-4)** — pass. On "Memory", "Find papers (15)" opened the review page: Titans matched by arXiv ID and was pre-selected; 14 items showed "Not found" (outside lookup is epic 02). Applying the review linked Titans; the other items stayed text.
- **M-5 (AC-7)** — pass. Clicking the Titans title opened `/paper.html?id=0fe4e4a8-9a3a-45ee-b31b-794b2b451665`, the paper page.
- **M-6 (AC-5, AC-6)** — pass. Accepted both matches on "Shared test", ticked Titans there. "Memory" then shows Titans ticked; progress went to "1 of 2 read" and "2 of 15 read".

### Suite result

`cd backend && uv run pytest` — 102 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 43 source files.

### Deviations from the plan

- The candidate is stored as one JSON text column (`candidate_json`, validated by the `Candidate` model) plus an `outcome` column, not as separate `candidate_*` columns. Same data, fewer columns.
- Reviewed items that are rejected or not found become `done` text items. "Find papers" then skips them; looking one up again is phase 03's "search again".
- A `ruff format src` run reformatted `src/api/papers.py` (ISS-5); that change was reverted, so the epic does not touch the file.

### Follow-ups

None.

---

## Review — 2026-09-23

**Verdict:** pass with follow-ups

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | `test_library_match_by_arxiv_id`; M-3 (Titans) |
| AC-2 | yes | `test_library_match_by_doi` |
| AC-3 | yes | `test_library_title_match_used_when_ids_miss`; M-1 for the SQL |
| AC-4 | yes | `test_accept_library_match_links_item`, `test_reject_leaves_text_item` |
| AC-5 | yes | `test_tick_paper_item_sets_paper_read_at`; M-6 |
| AC-6 | yes | `test_progress_counts_paper_read_at`; M-6 |
| AC-7 | yes | M-5, recorded in the build note |

Suite re-run by the reviewer: 102 passed; the two touched test files also pass on their own.

### Drift

- `architecture.md` lists `candidate_*` columns; the code uses one `candidate_json` column plus `outcome`. Same data and seam. I think the document is only more detailed than it needs to be; no change needed.
- None against `concept.md`.

### Findings

1. Low — `citation_resolver.py`: a library match by an arXiv ID or DOI written in the citation is confident without a title check. The spike found 2 of 9 LLM-given arXiv IDs pointing at a differently titled record. A wrong ID that exists in the library would be pre-selected. The review page shows the matched title, so Will can untick it.
2. Low — `models/reading_list.py` imports `schemas.reading_list` for the `candidate` property: models now depend on schemas. Harmless here; no cycle.
3. Low — progress and `is_read` load each item's paper one by one. At 10 to 40 items this costs nothing.

The deep pass ran inline, not through `/code-review`.

### Follow-ups

- Check the title of a library match found by a cited arXiv ID or DOI, and mark it weak when the titles disagree.
