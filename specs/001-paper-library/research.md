# Research: Academic Paper Library

**Feature**: 001-paper-library
**Date**: 2026-02-25

## Decision 1: arXiv Metadata Extraction

**Decision**: Use the `arxiv` Python package (PyPI: `arxiv`) to retrieve metadata from arXiv.

**Rationale**: The `arxiv` package wraps the official arXiv API (Atom/XML feed) and returns
structured `Result` objects with `title`, `authors` (list with `.name`), `published` (datetime),
`summary` (abstract), and `pdf_url`. It handles all URL/ID normalisations automatically
(abs/XXXX.XXXXX, pdf/XXXX.XXXXX, versioned IDs). This is the simplest approach and avoids
fragile HTML scraping (explicitly discouraged by arXiv's robots.txt).

**Alternatives considered**:
- `feedparser` + raw HTTP to `export.arxiv.org/api/query`: more control but requires manual Atom
  XML parsing — unnecessary complexity for a prototype.
- HTML scraping: fragile, explicitly discouraged by arXiv.

**Key gotchas**:
- Authors are objects; use `[a.name for a in paper.authors]` to get a list of strings.
- `published` is a UTC `datetime`; store as-is in the database.
- Rate-limited; built-in backoff is sufficient for a single-user prototype.

---

## Decision 2: PDF Metadata Extraction (non-arXiv)

**Decision**: Use `pdfplumber` for best-effort metadata extraction from arbitrary PDFs.

**Rationale**: `pdfplumber.open(path).metadata` returns a dict of standard PDF document
properties (Title, Author, CreationDate, etc.). It is the most reliable Python PDF library for
text extraction (uses pdfminer.six under the hood) and handles most edge cases gracefully.

**Alternatives considered**:
- `pymupdf` (fitz): 3-5× faster but less consistent metadata extraction; overkill for a prototype.
- `pypdf`: pure Python, lightweight, but limited metadata support.

**Key gotchas**:
- PDF metadata is often absent or wrong (especially for older papers); treat it as best-effort.
- `CreationDate` from PDF properties ≠ paper publication date; prefer arXiv API date when available.
- Only scan first 1-2 pages for title/author text when properties are missing.

---

## Decision 3: PDF Download

**Decision**: Use `httpx` with `follow_redirects=True` and a 30-second timeout.

**Rationale**: `httpx` is a modern, actively-maintained HTTP client with native async support,
excellent type hints, and explicit redirect handling. For arXiv, redirect following is required.
Magic-bytes validation (`%PDF`) provides a reliable fallback when servers return wrong content-types.

**Alternatives considered**:
- `requests`: synchronous only; less future-proof; follows redirects by default (implicit behaviour
  is a minor hazard).

**Key gotchas**:
- `follow_redirects=True` must be set explicitly in `httpx`.
- Validate with `response.content[:4] == b'%PDF'` as a fallback if Content-Type header is wrong.
- Use a 30-60 second timeout for large PDFs.

---

## Decision 4: Google Drive File Storage

**Decision**: Use `google-api-python-client` + `google-auth-oauthlib` with a user OAuth2 flow
(Desktop app credentials) and the `drive.file` scope.

**Rationale**: User OAuth (3-legged) is appropriate for a single-user app where the user owns the
files. Service accounts are designed for server-to-server use and require sharing files explicitly.
The `drive.file` scope is minimal (only files created by the app). Credentials are cached in
`token.json` locally and auto-refresh.

**Key URLs for PDF serving**:
- View link: `file['webViewLink']` (opens in Drive viewer)
- Download URL: `https://drive.google.com/uc?id={file_id}&export=download`

**Setup prerequisite** (out of scope for implementation — user must do once):
1. Create OAuth 2.0 Desktop credential in Google Cloud Console.
2. Download as `credentials.json` and place in a config directory.

**Alternatives considered**:
- Service account: requires explicit file-sharing; not natural for personal file ownership.

**Key gotchas**:
- `token.json` must NOT be committed to git.
- File sharing permissions take ~1s to propagate after upload.
- Scope `drive.file` means the app can only see files it created — ideal for this use case.

---

## Decision 5: Full-Text Search in PostgreSQL

**Decision**: Use PostgreSQL native `tsvector`/`tsquery` full-text search with a computed
`GENERATED ALWAYS` column and a GIN index.

**Rationale**: For a library of 500 papers, PostgreSQL FTS with a GIN index gives sub-5ms query
times with no external search service. `tsvector` provides English stemming and stop-word
filtering, which handles academic search well. `plainto_tsquery()` is safe to use with raw user
input (ignores special characters). This is the simplest approach that will scale to 10K+ rows
without change.

**Alternatives considered**:
- `ILIKE` across columns: works at 500 rows but no stemming; doesn't scale.
- `pg_trgm`: good for fuzzy/typo matching but slower for phrase search; not needed here.
- Elasticsearch / external search: massive overkill for a prototype.

**Implementation**: Use a `GENERATED ALWAYS AS (...) STORED` computed column in PostgreSQL 12+
combining `title || ' ' || authors || ' ' || COALESCE(abstract, '')` into a `tsvector`.
SQLAlchemy's `TSVECTOR` type + `Index(..., postgresql_using='gin')` provides clean integration.

---

## Decision 6: Chrome Extension Architecture

**Decision**: Manifest V3 extension with:
- Content script injected on `arxiv.org/*` pages — detects arXiv ID from URL.
- Background service worker — receives message from content script, POSTs to backend API.
- No auth for initial prototype (localhost-only); pre-shared Bearer token for remote deployment.

**arXiv URL pattern** (covers all common forms):
```
/arxiv\.org\/(?:abs|pdf)\/([\d]{4}\.[\d]{4,5}|[\w-]+\/[\d]{7})/
```

**Key MV3 constraint**: Service workers terminate after ~5 minutes of inactivity; all state must
use `chrome.storage.local`, not `localStorage`.

**CORS**: Backend must set `Access-Control-Allow-Origin` to allow the extension's origin, or use
the extension's `host_permissions` to include the backend URL.

**Alternatives considered**:
- Manifest V2: deprecated by Chrome; all new extensions must use MV3.
- Extension-native auth (OAuth via Chrome identity API): overkill for single-user prototype.

---

## Dependency Summary

| Concern | Library | `uv add` |
| ------- | ------- | -------- |
| arXiv metadata | `arxiv` | `uv add arxiv` |
| PDF parsing | `pdfplumber` | `uv add pdfplumber` |
| HTTP client | `httpx` | `uv add httpx` |
| Google Drive | `google-api-python-client google-auth-oauthlib` | `uv add google-api-python-client google-auth-oauthlib` |
| Web framework | `fastapi uvicorn` | `uv add fastapi uvicorn` |
| Database ORM | `sqlalchemy psycopg2-binary alembic` | `uv add sqlalchemy psycopg2-binary alembic` |
| Validation | `pydantic` | `uv add pydantic` |

Chrome extension is plain JavaScript/HTML (Manifest V3) — no npm build required for a prototype.
