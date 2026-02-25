# Tasks: Academic Paper Library

**Input**: Design documents from `/specs/001-paper-library/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅

**Tests**: Backend service tests MUST follow TDD (write test first, confirm it fails, then implement).
Tests MUST NOT be written for frontend components or API endpoint handlers.
Tests MUST NOT call remote APIs (arXiv, Google Drive, httpx) — mock all external dependencies.
If a test cannot be written without a live remote API, omit the test entirely.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, tooling, and Docker environment.

- [x] T001 Initialize uv Python 3.11 project with `pyproject.toml` in `backend/`
- [x] T002 [P] Add backend dependencies: `fastapi uvicorn sqlalchemy alembic pydantic psycopg2-binary httpx arxiv pdfplumber google-api-python-client google-auth-oauthlib` via `uv add` in `backend/`
- [x] T003 [P] Add backend dev dependencies: `pytest pytest-mock mypy ruff` via `uv add --dev` in `backend/`
- [x] T004 [P] Configure `ruff` and `mypy` in `backend/pyproject.toml` (strict mypy, ruff linting + formatting)
- [x] T005 [P] Create `docker-compose.yml` at repo root with PostgreSQL 16 service (port 5432, `paperstore` db/user/password)
- [x] T006 Create `backend/src/` package structure: `models/`, `schemas/`, `services/`, `api/` — add `__init__.py` to each
- [x] T007 [P] Create `backend/tests/` structure: `unit/`, `conftest.py`

**Checkpoint**: `docker compose up -d` starts PostgreSQL; `uv run ruff check backend/src/` passes on empty packages.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on — database, ORM models, schemas, and shared fixtures.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T008 Create SQLAlchemy engine + session factory in `backend/src/db.py` (reads `DATABASE_URL` env var; provides `get_session` generator; `create_tables()` for startup)
- ~~T009 Alembic~~ — dropped in favour of `Base.metadata.create_all()` (prototype simplicity)
- [x] T010 [P] Create `Paper` SQLAlchemy ORM model in `backend/src/models/paper.py` (all fields from data-model.md including `search_vector` TSVECTOR generated column)
- [x] T011 [P] Create `Note` SQLAlchemy ORM model in `backend/src/models/note.py` (FK to papers, UNIQUE on paper_id, default empty content)
- ~~T012 Alembic migration~~ — dropped; schema created via `create_tables()` on app startup
- [x] T013 [P] Create pydantic schemas in `backend/src/schemas/paper.py`: `PaperSubmitRequest`, `PaperSummary`, `PaperDetail`, `NoteSchema`, `ErrorResponse` — all fields typed, no plain dicts
- [x] T014 [P] Create pydantic schemas in `backend/src/schemas/note.py`: `NoteUpdateRequest`, `NoteResponse`
- [x] T015 Create `backend/tests/conftest.py` with pytest fixtures: in-memory SQLite test engine, `db_session` fixture, `mock_drive_client` fixture (MagicMock), `mock_httpx_client` fixture (MagicMock)
- [x] T016 Create `backend/src/main.py`: FastAPI app instance, call `create_tables()` on startup, mount `/papers` router, serve `frontend/` as static files, configure CORS for extension origin

**Checkpoint**: `uv run pytest backend/tests/` collects 0 tests with no errors; `uv run uvicorn backend.src.main:app` starts and creates tables.

---

## Phase 3: User Story 1 — Add Paper via URL (Priority: P1) 🎯 MVP

**Goal**: User pastes an arXiv URL or PDF URL; paper metadata is extracted and the PDF stored in Drive; the paper appears in the library.

**Independent Test**: POST `{"url": "https://arxiv.org/abs/2301.00001"}` to `/papers`; confirm 201 response with title, authors, date, abstract, and drive_view_url populated.

### Tests for User Story 1 (backend services only) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**
> **RULE: No remote API calls — mock arxiv client, httpx, and Drive in all tests**

- [x] T017 [P] [US1] Write unit tests for `ArxivClient.fetch(arxiv_id)` in `backend/tests/unit/test_arxiv_client.py`: test returns `PaperMetadata` with correct fields; test raises on API error; test correctly normalises all arXiv ID forms (abs/, pdf/, versioned)
- [x] T018 [P] [US1] Write unit tests for `PdfParser.download_and_extract(url)` in `backend/tests/unit/test_pdf_parser.py`: test returns `PaperMetadata` from mocked httpx response; test raises on non-PDF content-type; test raises on HTTP error; test handles missing PDF metadata gracefully (blank fields)
- [x] T019 [P] [US1] Write unit tests for `DriveService.upload(file_path, filename)` in `backend/tests/unit/test_drive.py`: test returns `DriveUploadResult` with file_id and view_url; test raises `DriveUploadError` on API failure
- [x] T020 [US1] Write unit tests for `IngestionService.ingest(url)` in `backend/tests/unit/test_ingestion.py`: test detects arXiv URL and delegates to ArxivClient; test detects plain PDF URL and delegates to PdfParser; test raises `DuplicateError` when arxiv_id or submission_url already exists; test persists Paper and Note rows on success; test rolls back on Drive failure

### Implementation for User Story 1

- [x] T021 [P] [US1] Create `PaperMetadata` TypedDict and `DriveUploadResult` TypedDict in `backend/src/services/types.py` (shared typed return types for services)
- [x] T022 [P] [US1] Implement `ArxivClient` in `backend/src/services/arxiv_client.py`: `fetch(arxiv_id: str) -> PaperMetadata` — uses `arxiv` package, normalises ID from any URL form, returns typed metadata
- [x] T023 [P] [US1] Implement `PdfParser` in `backend/src/services/pdf_parser.py`: `download_and_extract(url: str) -> tuple[PaperMetadata, bytes]` — uses `httpx` with `follow_redirects=True`, validates magic bytes, extracts metadata with `pdfplumber`, returns metadata + PDF bytes
- [x] T024 [P] [US1] Implement `DriveService` in `backend/src/services/drive.py`: `upload(pdf_bytes: bytes, filename: str) -> DriveUploadResult` — loads credentials from env-configured paths, uploads to Drive, sets reader permission, returns file_id and view_url
- [x] T025 [US1] Implement `IngestionService` in `backend/src/services/ingestion.py`: `ingest(url: str, db: Session) -> Paper` — detects URL type, calls appropriate client, checks duplicates (raises `DuplicateError`), uploads to Drive, persists Paper + Note in transaction
- [x] T026 [US1] Implement `POST /papers` endpoint in `backend/src/api/papers.py`: accepts `PaperSubmitRequest`, calls `IngestionService.ingest()`, returns 201 `PaperDetail` or appropriate error responses (409, 422, 502)
- [x] T027 [US1] Add `GET /papers` endpoint (list all, no search yet) in `backend/src/api/papers.py`: returns `{"papers": [PaperSummary], "total": N}` ordered by `added_at DESC`

**Checkpoint**: User Story 1 fully functional — POST a real arXiv URL and the paper appears via GET /papers.

---

## Phase 4: User Story 2 — Search and Browse Library (Priority: P2)

**Goal**: User types a query into the search box; matching papers are returned from PostgreSQL full-text search.

**Independent Test**: With 3 papers in the DB, GET `/papers?q=<author-name>` returns only papers by that author in under 2 seconds.

### Tests for User Story 2 (backend services only) ⚠️

- [x] T028 [US2] Write unit tests for `SearchService.search(query, db)` in `backend/tests/unit/test_search.py`: test returns all papers when query is empty or None; test returns matching papers for a title term; test returns matching papers for an author name; test returns empty list when no match; test uses mocked DB session (no live Postgres required in unit tests)

### Implementation for User Story 2

- [x] T029 [US2] Implement `SearchService` in `backend/src/services/search.py`: `search(query: str | None, db: Session) -> list[Paper]` — if query is None/empty returns all papers ordered by `added_at DESC`; otherwise uses `func.plainto_tsquery` + `search_vector` match + `ts_rank` ordering
- [x] T030 [US2] Update `GET /papers` endpoint in `backend/src/api/papers.py` to accept optional `q` query parameter and delegate to `SearchService.search()`
- [x] T031 [US2] Add search input and results list to `frontend/index.html` + `frontend/static/app.js`: search box calls `GET /papers?q=...` on input change (debounced 300ms); renders `PaperSummary` list with title, authors, date; clicking a paper navigates to `paper.html?id=<uuid>`

**Checkpoint**: User Story 2 fully functional — search box filters library results in real time.

---

## Phase 5: User Story 3 — View Paper In-App (Priority: P3)

**Goal**: User selects a paper from the library and views full metadata plus the PDF in-browser without leaving the app.

**Independent Test**: Navigate to `paper.html?id=<uuid>`; confirm metadata panel shows title/authors/date/abstract and `<iframe>` loads the PDF from `/papers/{id}/pdf`.

### Tests for User Story 3 (backend services only) ⚠️

> No new service logic for this story — endpoint and PDF redirect are API-layer tasks (excluded from unit tests per constitution). No test tasks for this phase.

### Implementation for User Story 3

- [x] T032 [US3] Implement `GET /papers/{id}` endpoint in `backend/src/api/papers.py`: fetches Paper + Note by UUID, returns 200 `PaperDetail` or 404
- [x] T033 [US3] Implement `GET /papers/{id}/pdf` endpoint in `backend/src/api/papers.py`: fetches paper's `drive_view_url`, returns 302 redirect to Drive download URL; returns 404 if paper not found
- [x] T034 [US3] Create `frontend/paper.html` + update `frontend/static/app.js`: reads `?id=` from URL, calls `GET /papers/{id}`, renders metadata panel (title, authors, date, abstract), embeds `<iframe src="/papers/{id}/pdf">` for in-browser PDF viewing, adds back-navigation link

**Checkpoint**: User Story 3 fully functional — click a paper in the list, view metadata and PDF in-app.

---

## Phase 6: User Story 4 — Add and Edit Notes on a Paper (Priority: P4)

**Goal**: User writes or edits a plain-text note on any paper; it persists across sessions.

**Independent Test**: PATCH `/papers/{id}/note` with `{"content": "test note"}`; restart backend; GET `/papers/{id}` returns the same note content.

### Tests for User Story 4 (backend services only) ⚠️

- [x] T035 [US4] Write unit tests for `NotesService.upsert(paper_id, content, db)` in `backend/tests/unit/test_notes.py`: test updates content on existing note; test raises `NotFoundError` when paper_id doesn't exist; test returns updated `NoteResponse` with new `updated_at`

### Implementation for User Story 4

- [x] T036 [US4] Implement `NotesService` in `backend/src/services/notes.py`: `upsert(paper_id: UUID, content: str, db: Session) -> NoteResponse` — finds Note by paper_id (raises `NotFoundError` if paper doesn't exist), updates content and `updated_at`, commits, returns typed response
- [x] T037 [US4] Implement `PATCH /papers/{id}/note` endpoint in `backend/src/api/papers.py`: accepts `NoteUpdateRequest`, returns 200 `NoteResponse` or 404 (note: inline in papers.py, no separate NotesService)
- [x] T038 [US4] Add note textarea to `frontend/paper.html` + `frontend/static/app.js`: pre-populates with existing note content from `GET /papers/{id}` response; saves on blur via `PATCH /papers/{id}/note`; shows save confirmation

**Checkpoint**: User Story 4 fully functional — add a note, reload the page, note persists.

---

## Phase 7: User Story 5 — Add Paper via Chrome Extension (Priority: P5)

**Goal**: User clicks the PaperStore extension icon on an arXiv page; the paper is submitted to the backend and appears in the library.

**Independent Test**: Load the extension unpacked; navigate to `arxiv.org/abs/2301.00001`; click the extension icon; confirm paper appears in the library within 30 seconds.

> No backend service tests for this story — the extension is JavaScript (excluded from Python TDD scope); the backend endpoint reused from US1 has no new logic.

### Implementation for User Story 5

- [x] T039 [US5] Create `extension/manifest.json`: MV3 manifest with `host_permissions` for `https://arxiv.org/*` and `http://localhost:8000/*`, content script on `https://arxiv.org/*`, background service worker, `storage` permission
- [x] T040 [P] [US5] Create `extension/content.js`: extracts arXiv ID from current page URL using regex `/(abs|pdf)\/([\d]{4}\.[\d]{4,5}|[\w-]+\/[\d]{7})/`; sends `{type: "SUBMIT_PAPER", arxivId}` message to service worker on icon click (via `chrome.runtime.sendMessage`)
- [x] T041 [P] [US5] Create `extension/service-worker.js`: listens for `SUBMIT_PAPER` message; reads `backendUrl` from `chrome.storage.local` (default `http://localhost:8000`); POSTs `{"url": "https://arxiv.org/abs/{arxivId}"}` to `/papers`; stores and surfaces response status
- [x] T042 [US5] Create `extension/popup.html`: shows submission status (idle / submitting / success / duplicate / error) with a one-line message; icon click triggers submission and opens popup
- [x] T043 [US5] Test extension end-to-end: load unpacked in Chrome, navigate to an arXiv page, click icon, confirm paper appears in `GET /papers`

**Checkpoint**: User Story 5 fully functional — one-click arXiv paper submission from Chrome.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality, environment wiring, and validation of the complete flow.

- [x] T044 [P] Add environment variable loading (`python-dotenv` or direct `os.getenv`) and `.env.example` at repo root with all required variables from quickstart.md
- [x] T045 [P] Add error handling middleware to `backend/src/main.py`: catches `DuplicateError` → 409, `NotFoundError` → 404, `DriveUploadError` → 502, validation errors → 422; returns `ErrorResponse` schema
- [x] T046 [P] Run `uv run mypy backend/src/` and fix all type errors
- [x] T047 [P] Run `uv run ruff check backend/src/ backend/tests/` and `uv run ruff format backend/src/ backend/tests/` — fix all issues
- [x] T048 [P] Run `uv run pytest backend/tests/` — confirm all unit tests pass
- [x] T049 Run quickstart.md validation checklist end-to-end (all 10 checkboxes)
- [x] T050 [P] Update `specs/001-paper-library/checklists/requirements.md` — mark all items complete

---

## Phase 9: Google OAuth Web Flow (FR-000)

**Purpose**: Implement the browser-based OAuth flow so users can authenticate via Google without manually generating a token. Required before Docker deployment is usable.

> No backend service tests — OAuth endpoints are API-layer (excluded by constitution Principle III).

- [x] T051 [P] Add `SESSION_SECRET` to `.env.example`; add `OAUTHLIB_INSECURE_TRANSPORT: "1"` to `docker-compose.yml` api service environment
- [x] T052 Create `backend/src/api/auth.py`: `GET /auth/login` (build `Flow`, store state in signed session cookie, redirect to Google) and `GET /auth/callback` (verify state, call `flow.fetch_token()`, write `token.json`, redirect to `/`)
- [x] T053 Update `backend/src/main.py`: add `AuthMiddleware` (checks token validity, redirects to `/auth/login` if unauthenticated, exempts `/auth/*`), add `SessionMiddleware` with `SESSION_SECRET`, register auth router at `/auth`
- [x] T054 Update `specs/001-paper-library/contracts/api.md` with `/auth/login` and `/auth/callback` endpoint contracts

**Checkpoint**: `docker compose up --build`; navigate to `http://localhost:8000` → redirected to Google sign-in → after auth, redirected back to app.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **User Stories (Phases 3–7)**: Depend on Phase 2 completion; can proceed in priority order P1 → P5
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2 — no dependency on other stories
- **US2 (P2)**: Starts after Phase 2 — no dependency on US1 (search service is independent; list endpoint from US1 is extended, not replaced)
- **US3 (P3)**: Starts after Phase 2 — no dependency on US1/US2 (new endpoints only)
- **US4 (P4)**: Starts after Phase 2 — no dependency on other stories (Note model created in Phase 2)
- **US5 (P5)**: Starts after US1 — reuses `POST /papers` endpoint; no other dependencies

### Within Each User Story

- Backend service tests MUST be written and FAIL before implementation (TDD)
- No tests for FastAPI endpoint handlers or frontend code
- No remote API calls in any test — mock all external dependencies
- TypedDicts/models before services; services before endpoints; endpoints before frontend
- Story complete and manually tested before moving to next priority

### Parallel Opportunities

- T002, T003, T004, T005, T007 (Phase 1) can all run in parallel
- T010, T011, T013, T014 (Phase 2 models + schemas) can run in parallel after T008
- T017, T018, T019 (US1 tests) can run in parallel
- T022, T023, T024, T021 (US1 services) can run in parallel after their tests
- T040, T041 (extension content/service-worker) can run in parallel
- T044, T045, T046, T047, T048 (Polish) can all run in parallel

---

## Parallel Examples

### Phase 2 Parallel

```text
After T008 (db.py):
  → T010 [P] Paper ORM model        (backend/src/models/paper.py)
  → T011 [P] Note ORM model         (backend/src/models/note.py)
  → T013 [P] Paper pydantic schemas (backend/src/schemas/paper.py)
  → T014 [P] Note pydantic schemas  (backend/src/schemas/note.py)
```

### User Story 1 Parallel

```text
Tests first (must all FAIL before implementation):
  → T017 [P] test_arxiv_client.py
  → T018 [P] test_pdf_parser.py
  → T019 [P] test_drive.py

Then implementation (after tests written):
  → T021 [P] services/types.py
  → T022 [P] services/arxiv_client.py
  → T023 [P] services/pdf_parser.py
  → T024 [P] services/drive.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (arXiv + PDF ingestion)
4. **STOP and VALIDATE**: POST a real arXiv URL, confirm paper stored and retrievable
5. Demo/review before continuing

### Incremental Delivery

1. Phase 1 + 2: Foundation ready
2. Phase 3 (US1): Paper submission → MVP ✅
3. Phase 4 (US2): Search → can find papers ✅
4. Phase 5 (US3): In-app viewing → full read workflow ✅
5. Phase 6 (US4): Notes → annotations ✅
6. Phase 7 (US5): Chrome extension → frictionless capture ✅
7. Phase 8: Polish → release-ready prototype ✅

---

## Notes

- `[P]` tasks = different files, no blocking dependencies within the phase
- `[USN]` label maps each task to a user story for traceability
- TDD is mandatory for all service-layer tasks (T017–T020, T028, T035)
- Verify tests fail (red) before implementing the corresponding service (green)
- All Python must pass `ruff` and `mypy` before marking a task complete
- Commit after each completed task or logical group
- Stop at each phase checkpoint to validate independently before proceeding
