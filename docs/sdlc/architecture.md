# Architecture — PaperStore reading lists

## Goals

- Turn a pasted LLM reading list into an ordered checklist that links to library papers where they exist or can be fetched.
- Track read state per paper across the whole library, and per item for non-paper items.
- Leave room for Release 2 (non-paper entries in the library) without a second library table.

## Constraints

- Existing app: FastAPI, SQLAlchemy 2, Postgres 16, Google Drive for PDFs, Gemini, Google OAuth, one user.
- No Alembic. Schema changes are idempotent `ALTER … IF NOT EXISTS` statements in `create_tables()`, run on startup.
- Constitution: `uv` only, mypy strict, no `Any`, pydantic or TypedDict for structured data, TDD for backend services only, no remote calls in tests, no new dependency without approval.
- HTMX over vanilla JS for server interactions (user preference). Any JS goes in a static file, never inline.
- `papers.drive_file_id`, `drive_view_url` and `submission_url` are `NOT NULL`. A library paper must have a PDF in Drive.
- The dev environment currently points at the production database (commit `cec4363`). A schema change run in dev runs on live data.
- Backups run from a host cron job, not from Docker Compose: `scripts/backups_script.sh` at 03:15 daily, `pg_dump -Fc` to `~/backups/postgres/`, 14-day retention. Will chose to keep it as it is (2026-09-23), which departs from the global 7/4/6 retention rule.

## Approaches considered

**A. Lists inside PaperStore, resolve then review.** Paste → Gemini parses into items → each item is looked up in the library, then on OpenAlex and arXiv → the user reviews candidates → confirmed papers go through the existing ingestion in a background thread. Trade-off: two external lookups per item and a review screen to build, but it reuses ingestion, Drive and dedupe.

**B. Lists inside PaperStore, LLM finds the URLs.** Gemini with search grounding returns a URL per item, and the app ingests whatever URL comes back. Trade-off: less code, but the LLM invents URLs and DOIs as readily as it invents citations. Matching quality cannot be tested or tuned.

**C. Separate app, links into PaperStore.** A small checklist app that calls the PaperStore API. Trade-off: keeps PaperStore clean, but it duplicates auth and deployment and splits read state across two databases. The user wants one app.

## Recommended approach

A. The deciding factor is matching quality. The review step only helps if the candidates come from real bibliographic records with IDs. Approach A gives arXiv IDs and DOIs from real sources and dedupes on them. B cannot do that, and C is rejected by the concept.

## Stack

- Language: Python 3.11
- Web: FastAPI + Uvicorn; existing pages vanilla JS; new list pages Jinja2 templates + HTMX (vendored static file)
- Database: PostgreSQL 16 (pg_trgm already enabled)
- External: Gemini (list parsing), arXiv API (existing `arxiv` package), OpenAlex REST API via `httpx`, Google Drive
- Tests: pytest with mocks, run with `cd backend && uv run pytest`
- Lint and types: `cd backend && uv run ruff check src tests && uv run mypy src`
- Deploy: Docker Compose on OrbStack via `prod.sh`, exposed through cloudflared

New dependency: `jinja2`. HTMX is a vendored static file, not a package.

## Shape of the system

```
paste ─▶ list parser ─▶ citation resolver ─▶ review page ─▶ import worker ─▶ ingestion (existing)
         (Gemini)       library → arXiv ID    (HTMX)        (thread)          arXiv / bioRxiv / PDF
                        → OpenAlex → arXiv    + PDF upload                    → Drive → papers
```

- `services/reading_list_parser.py` — raw text in, ordered `ParsedItem` models out (title, authors, year, note, raw citation). Gemini structured output against a pydantic schema.
- `services/citation_resolver.py` — one `ParsedItem` in, a `Candidate` or "not found" out. Order: library by arXiv ID or DOI, library by title similarity (pg_trgm), arXiv ID given in the list (fetched and title-checked), OpenAlex title search, arXiv title search last. A candidate auto-matches only when the title matches and the year (±1) or a first-author surname also matches. Otherwise the review page flags it. Each source sits behind a small function so tests mock it.
- A candidate has one of three outcomes: **free PDF** (arXiv, or an OpenAlex PDF link that returns a real PDF), **record only** (a DOI or landing page, no fetchable PDF), or **not found**.
- `services/reading_lists.py` — create list, confirm review, drop item, set URL on item, tick item, reorder. All business rules live here and are unit-tested.
- Import worker — a background thread per confirmed list, the same pattern as `batch_metadata.py`. It calls the existing `IngestionService.ingest(url)` per confirmed item and writes the outcome to the item row.
- `api/reading_lists.py` + `templates/` — HTMX routes return HTML fragments. They sit behind the existing session auth.
- Seam with existing code: the importer calls `IngestionService.ingest()`, and the item upload calls `ingest_local()`. Neither changes ingestion.

A supported URL typed on an unfound item takes the same path as a confirmed candidate. Any other URL is stored on the item as a plain link.

A **record only** item shows the DOI link and an "upload PDF" action. The upload calls the existing `IngestionService.ingest_local()` with the DOI URL as `source_url`. Metadata comes from the PDF, as it does for any upload today. The service then sets `doi` on the new paper from the candidate and links it to the item. This is the path for about 40% of papers (see the spike).

## Data

**`papers` (existing) — new columns**

- `read_at timestamptz NULL` — the shared read flag. Ticking a paper item sets it. The library gets a read / unread filter from it.
- `doi text NULL UNIQUE` — second dedupe key next to `arxiv_id`. Filled from the OpenAlex record, including on a PDF upload against a list item.

**`reading_lists`**

- `id`, `name`, `raw_text` (the paste, kept for re-parsing), `created_at`.

**`reading_list_items`**

- `id`, `list_id` (cascade delete), `position`
- `citation` (raw line), `title`, `authors`, `year`, `note`
- `paper_id` → `papers.id`, `ON DELETE SET NULL`
- `url` — a plain link, or the candidate URL during review
- `read_at` — used only when `paper_id` is null
- `status` — `review`, `importing`, `done`, `import_failed`
- `candidate_outcome` — `free_pdf`, `record_only`, `not_found`
- `candidate_*` — source, title, arXiv ID, DOI, PDF URL, match score. Filled by the resolver, read by the review page, cleared on import.

An item is a paper item if `paper_id` is set, a link item if `url` is set, and a text item otherwise. The tick on a paper item reads and writes `papers.read_at`.

**Release 2 (recorded now so Release 1 does not block it)**

- Non-paper entries go in `papers` with a new `kind` column (default `paper`). There is no second library table.
- `drive_file_id`, `drive_view_url` and `submission_url` become nullable.
- Pasted text goes in `extracted_text`. The search trigger then includes `extracted_text` for non-paper kinds only.
- Release 2 moves `read_at` from ticked text items onto their new library entries.

## Key decisions

- **One library table in both releases.** Rejected: a separate table for non-paper entries, which makes every list query join two tables. See the Release 2 notes above and [ADR 0001](../adr/0001-one-library-table.md).
- **Per-paper read state in `papers.read_at`.** Rejected: read state per list item. The concept chose per paper.
- **Found paper with no free PDF stays a link item until Will uploads its PDF.** The library requires a PDF in Drive. Rejected: adding a PDF-less paper to the library, which is Release 2 work.
- **Resolver order: library, given arXiv ID, OpenAlex, arXiv title search.** The spike showed OpenAlex finds the right record for about 95% of papers. arXiv title search added one paper OpenAlex missed. Rejected: Semantic Scholar, because its keyless rate limit is tight. Cheap to reverse: each source is one function.
- **Auto-match needs title plus year or author.** Title alone produced two wrong matches in the spike (Singh 2004 matched a 2022 paper; a book matched a review of it).
- **PDF upload on a paper item is in Release 1.** About 40% of papers are found with no fetchable PDF. Without upload on the item, those papers cannot reach the library linked to their list.
- **HTMX + Jinja2 for the new pages only.** Rejected: rewriting existing pages, and vanilla JS for the new ones. Cheap to reverse per page.
- **Review state lives in the database.** A half-reviewed list survives a reload or a restart. Rejected: holding candidates in the browser.
- **Background thread, not a job queue.** One user and a few lists a month. Rejected: Celery or a task table with a worker process.

## Scale

One user. A few lists a month, 10 to 30 items each. A library of hundreds to low thousands of papers. Title similarity is a sequential pg_trgm scan, which is fine at this size. No index is needed now.

## Failure

- **Gemini parse fails or returns nothing.** The list is saved with its raw text and no items. The page offers "parse again". Nothing else runs.
- **arXiv or OpenAlex is down or rate-limits.** The item is marked not found, with a "search again" action. The list stays usable.
- **A wrong candidate.** The review step catches it. After import, "unlink" clears `paper_id` on the item. The paper stays in the library.
- **Ingestion fails for one item** (PDF behind a login, Drive error). The item goes to `import_failed` and keeps the candidate URL as a link. Other items go on.
- **The app restarts during import.** On startup, items left in `importing` go to `import_failed` with a retry action.
- **A paper is deleted from the library.** `ON DELETE SET NULL` turns the item back into a text item. The list stays intact.
- **Duplicate on ingest (409).** The resolver should have caught it. If not, the importer links the existing paper.

## Risks and spikes

**Spike: citation hit rate — done 2026-09-23.** Two real Claude reading lists, 43 items: 37 papers, 5 books, 2 other. Script and raw results in the session scratchpad; not kept in the repo.

- Free, fetchable PDF found for 19 of 37 papers (51%). ML papers from 2016 on: about 11 of 12. Older journal papers: about 5 of 20.
- Correct record with DOI found for about 35 of 37 papers. Most misses are publisher PDFs that block scripts (ScienceDirect, Cell, some AAAI and eLife links).
- No invented papers. The one doubtful item was already flagged as unverified by the LLM. Seven of nine given arXiv IDs matched; the other two point to the right work under another title.
- Two wrong matches from title-only matching. Both are caught by a year or author check.
- Outcome: below the 60% line, so manual steps are a main path. This moved PDF upload on paper items into Release 1 and changed the resolver order and match rule above. Gemini parsing was not tested by the spike.

**Risk: schema changes hit production.** Dev points at the production database, and `create_tables()` runs `ALTER` on startup. Split dev onto its own database, and check that a dump from the last 24 hours exists before the first run of the new schema.

**Risk: the service worker and HTMX.** A recent fix stopped the service worker from truncating non-GET bodies. HTMX POSTs and HTML fragments must bypass the cache. Check the service worker rules for the new routes.

**Risk: title similarity is untested by unit tests.** Unit tests mock the session, so the pg_trgm query only gets tested manually. Accept for a prototype, or add a test database (the global rules require a separate container).

## Open questions

- Can a list be edited after import (add, remove, reorder items)? The data model supports it. The concept must decide whether Release 1 includes it.
- Does a list have a finished or archived state?
- OpenAlex asks for a `mailto` parameter to use its faster pool. Send an address from an env var, or use the slower anonymous pool?
