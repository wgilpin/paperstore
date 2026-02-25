# Implementation Plan: Academic Paper Library

**Branch**: `001-paper-library` | **Date**: 2026-02-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-paper-library/spec.md`

## Summary

Build a single-user web application that collects, stores, and searches academic papers. Users
submit arXiv or PDF URLs; the backend extracts metadata and stores PDFs in Google Drive, with
metadata persisted in PostgreSQL. A companion Chrome extension enables one-click submission from
arXiv pages. The web app provides text search, in-app PDF viewing, and per-paper notes.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI + Uvicorn (web framework), SQLAlchemy + Alembic (ORM + migrations),
  pydantic (validation), httpx (HTTP client), arxiv (arXiv API), pdfplumber (PDF parsing),
  google-api-python-client + google-auth-oauthlib (Drive storage)
**Storage**: PostgreSQL (metadata + FTS via tsvector/GIN index); Google Drive (PDF files)
**Testing**: pytest — backend services only (TDD); no tests for FastAPI endpoint handlers or frontend
**Target Platform**: Linux (Docker Compose dev environment); single-user local deployment
**Project Type**: Web service (backend API) + minimal frontend + Chrome extension (JavaScript MV3)
**Performance Goals**: arXiv paper ingestion < 30s; PDF URL ingestion < 60s; search < 2s over 500 papers
**Constraints**: Single-user only; no multi-tenancy; prototype simplicity (YAGNI)
**Scale/Scope**: ~500 papers target; one user; no horizontal scaling required

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Python + uv**: Backend in Python 3.11; `uv` manages all dependencies; `pyproject.toml` required.
- [x] **Simplicity**: Scope matches spec exactly; no extra features introduced.
- [x] **TDD scope**: Service-layer logic (ingestion, search, notes, Drive) tested TDD; FastAPI handlers and frontend excluded.
- [x] **No remote API in tests**: arXiv client, Drive API, httpx calls all mocked in tests.
- [x] **Strong typing**: pydantic models for all API I/O; pydantic/TypedDicts for service layer; no plain dicts; mypy required.
- [x] **Ruff**: All Python files must pass `ruff check` and `ruff format` before saving.
- [x] **PostgreSQL**: Primary data store; tsvector FTS with GIN index; no other databases.
- [x] **Docker Compose**: `docker-compose.yml` at root runs PostgreSQL; app runs via `uv run`.
- [x] **Approval gate**: All features match spec; no additions without user confirmation.

All gates pass. ✅

## Project Structure

### Documentation (this feature)

```text
specs/001-paper-library/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # REST API contracts
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── paper.py         # SQLAlchemy ORM model for Paper
│   │   └── note.py          # SQLAlchemy ORM model for Note
│   ├── schemas/
│   │   ├── paper.py         # Pydantic schemas (PaperSummary, PaperDetail, etc.)
│   │   └── note.py          # Pydantic schemas for Note
│   ├── services/
│   │   ├── ingestion.py     # Paper ingestion orchestration (arXiv + PDF)
│   │   ├── arxiv_client.py  # arXiv API wrapper
│   │   ├── pdf_parser.py    # PDF download + metadata extraction
│   │   ├── drive.py         # Google Drive upload/URL service
│   │   ├── search.py        # PostgreSQL FTS query service
│   │   └── notes.py         # Note CRUD service
│   ├── api/
│   │   ├── papers.py        # FastAPI router: /papers endpoints
│   │   └── deps.py          # Shared dependencies (DB session, Drive client)
│   ├── db.py                # SQLAlchemy engine + session factory
│   └── main.py              # FastAPI app + router registration + static files
├── tests/
│   ├── unit/
│   │   ├── test_arxiv_client.py
│   │   ├── test_pdf_parser.py
│   │   ├── test_ingestion.py
│   │   ├── test_search.py
│   │   └── test_notes.py
│   └── conftest.py          # Fixtures (test DB session, mocked Drive/httpx)
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── pyproject.toml
└── alembic.ini

extension/
├── manifest.json            # Chrome MV3 manifest
├── content.js               # Injected on arxiv.org/* — extracts arXiv ID, sends message
├── service-worker.js        # Background service worker — POSTs to backend API
└── popup.html               # Status popup UI

frontend/                    # Served as FastAPI static files
├── index.html               # Library list + search
├── paper.html               # Paper detail + PDF viewer
└── static/
    └── app.js               # Fetch calls to REST API

docker-compose.yml           # PostgreSQL service
```

**Structure Decision**: Web application layout — Python backend (`backend/`) with plain HTML/JS
frontend served as FastAPI static files (`frontend/`). No npm build step for the prototype. Chrome
extension in `extension/` as plain JavaScript MV3 (no bundler). Tests are co-located under
`backend/tests/` and cover service layer only.
