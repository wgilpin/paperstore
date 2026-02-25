# API Contracts: Academic Paper Library

**Feature**: 001-paper-library
**Date**: 2026-02-25
**Base URL**: `http://localhost:8000` (development)

All endpoints accept and return `application/json`.
All timestamps are ISO 8601 UTC strings.
All UUIDs are lowercase hyphenated strings.

---

## Shared Types

### PaperSummary

Returned in list responses.

```json
{
  "id": "uuid",
  "arxiv_id": "2301.00001 | null",
  "title": "string",
  "authors": ["string"],
  "published_date": "YYYY-MM-DD | null",
  "added_at": "ISO8601"
}
```

### PaperDetail

Returned when viewing a single paper.

```json
{
  "id": "uuid",
  "arxiv_id": "2301.00001 | null",
  "title": "string",
  "authors": ["string"],
  "published_date": "YYYY-MM-DD | null",
  "abstract": "string | null",
  "submission_url": "string",
  "drive_view_url": "string",
  "added_at": "ISO8601",
  "note": {
    "content": "string",
    "updated_at": "ISO8601"
  }
}
```

### ErrorResponse

```json
{
  "error": "string",
  "detail": "string | null"
}
```

---

## Endpoints

### GET /auth/login

Initiates the Google OAuth 2.0 web flow.

**Success — 302 Redirect** → Google OAuth consent screen URL.

No request body or parameters required. Stores a CSRF `state` value in a signed session cookie before redirecting.

---

### GET /auth/callback

OAuth redirect endpoint. Exchanges the authorization code for a token and persists it.

**Query parameters** (supplied by Google, not the caller):

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `code` | string | Authorization code from Google |
| `state` | string | CSRF state value to verify against session |

**Success — 302 Redirect** → `/` (app root). Token written to `GOOGLE_TOKEN_PATH`.

**Error**: If state is mismatched or token exchange fails, raises an unhandled exception (returns 500). In a production system this would return a 400; for a prototype the crash surface is acceptable.

---

### POST /papers

Submit a URL to add a paper to the library.

**Request body**:
```json
{
  "url": "https://arxiv.org/abs/2301.00001"
}
```

**Success — 201 Created**:
```json
{
  "paper": PaperDetail
}
```

**Error — 409 Conflict** (duplicate):
```json
{
  "error": "duplicate",
  "detail": "Paper already exists in your library"
}
```

**Error — 422 Unprocessable Entity** (invalid or unsupported URL):
```json
{
  "error": "invalid_url",
  "detail": "URL must be an arXiv page or direct PDF link"
}
```

**Error — 502 Bad Gateway** (external fetch failure):
```json
{
  "error": "fetch_failed",
  "detail": "Could not retrieve the paper from the given URL"
}
```

---

### GET /papers

List all papers, with optional search.

**Query parameters**:

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `q` | string | No | Free-text search query (searches title, authors, abstract, date) |

**Success — 200 OK**:
```json
{
  "papers": [PaperSummary],
  "total": 42
}
```

Returns all papers when `q` is absent or empty. Returns matching papers when `q` is provided.
Returns `{"papers": [], "total": 0}` when no results.

---

### GET /papers/{id}

Retrieve full detail for a single paper.

**Path parameters**:
- `id` — UUID of the paper

**Success — 200 OK**:
```json
{
  "paper": PaperDetail
}
```

**Error — 404 Not Found**:
```json
{
  "error": "not_found",
  "detail": "Paper not found"
}
```

---

### PATCH /papers/{id}/note

Create or update the note for a paper.

**Request body**:
```json
{
  "content": "string"
}
```

**Success — 200 OK**:
```json
{
  "note": {
    "content": "string",
    "updated_at": "ISO8601"
  }
}
```

**Error — 404 Not Found**:
```json
{
  "error": "not_found",
  "detail": "Paper not found"
}
```

---

### GET /papers/{id}/pdf

Proxy or redirect to the paper's PDF for in-app viewing.

**Path parameters**:
- `id` — UUID of the paper

**Success — 302 Redirect** → Google Drive download URL for the PDF.

This allows the frontend to embed `<iframe src="/papers/{id}/pdf">` without exposing the raw
Drive URL or requiring the frontend to know about Google Drive.

**Error — 404 Not Found**:
```json
{
  "error": "not_found",
  "detail": "Paper not found"
}
```

---

## Notes on Design

- The `/papers` list endpoint returns `PaperSummary` (no abstract, no note) to keep list responses
  small. Full abstract and note are only returned on the detail endpoint.
- `PATCH /papers/{id}/note` is idempotent — calling it with the same content has no observable
  side effect.
- The PDF proxy endpoint (`GET /papers/{id}/pdf`) decouples the frontend from Drive URLs and
  allows future storage backend changes without frontend changes.
- No pagination is included at this stage; the 500-paper prototype target does not require it.
