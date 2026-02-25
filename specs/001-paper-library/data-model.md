# Data Model: Academic Paper Library

**Feature**: 001-paper-library
**Date**: 2026-02-25

## Entities

### Paper

The primary record for a collected academic paper.

| Field | Type | Constraints | Notes |
| ----- | ---- | ----------- | ----- |
| `id` | UUID | PRIMARY KEY, default gen_random_uuid() | Stable internal identifier |
| `arxiv_id` | TEXT | UNIQUE, nullable | arXiv ID (e.g. `2301.00001`); NULL for non-arXiv PDFs |
| `title` | TEXT | NOT NULL | Extracted from arXiv API or PDF metadata |
| `authors` | TEXT[] | NOT NULL, default `{}` | Ordered list of author name strings |
| `published_date` | DATE | nullable | Paper publication date; NULL if not determinable |
| `abstract` | TEXT | nullable | Full abstract text |
| `submission_url` | TEXT | NOT NULL | Original URL submitted by user |
| `drive_file_id` | TEXT | NOT NULL | Google Drive file ID |
| `drive_view_url` | TEXT | NOT NULL | Google Drive web-view URL |
| `added_at` | TIMESTAMPTZ | NOT NULL, default NOW() | When the record was created |
| `search_vector` | TSVECTOR | GENERATED ALWAYS (stored) | Combined FTS index over title + authors + abstract |

**Indexes**:
- `UNIQUE (arxiv_id)` — deduplicate arXiv papers
- `UNIQUE (submission_url)` — deduplicate non-arXiv PDFs by source URL
- `GIN (search_vector)` — full-text search

**Notes**:
- `authors` stored as `TEXT[]` (PostgreSQL array) to preserve ordering and allow individual author
  lookup via `= ANY(authors)`.
- `search_vector` is a `GENERATED ALWAYS AS ... STORED` computed column:
  ```sql
  to_tsvector('english',
    title || ' ' ||
    array_to_string(authors, ' ') || ' ' ||
    COALESCE(abstract, '')
  )
  ```
- Both `arxiv_id` and `submission_url` carry UNIQUE constraints to cover all duplicate detection
  paths (FR-005).

---

### Note

A single plain-text annotation attached to one Paper.

| Field | Type | Constraints | Notes |
| ----- | ---- | ----------- | ----- |
| `id` | UUID | PRIMARY KEY, default gen_random_uuid() | |
| `paper_id` | UUID | NOT NULL, FK → papers(id) ON DELETE CASCADE | One-to-one via UNIQUE |
| `content` | TEXT | NOT NULL, default `''` | Plain-text note; empty string when no note written |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default NOW() | Last save timestamp |

**Indexes**:
- `UNIQUE (paper_id)` — enforces exactly one note per paper (FR-012)

**Notes**:
- Note rows are created eagerly when a paper is ingested (content = empty string), so the
  frontend always finds a Note record and can render the empty field without a separate creation
  step.

---

## Entity Relationships

```
Paper (1) ───── (1) Note
```

One Paper has exactly one Note (enforced by UNIQUE constraint on `paper_id`).

---

## State Transitions

### Paper ingestion lifecycle

```
URL submitted
    │
    ▼
[VALIDATING] — invalid/unsupported URL ──→ error returned, no record created
    │
    ▼
[DOWNLOADING] — download failure ──────→ error returned, no record created
    │
    ▼
[EXTRACTING] — metadata parse failure ─→ partial metadata stored, blanks for missing fields
    │
    ▼
[UPLOADING_TO_DRIVE] — Drive failure ──→ error returned, no record created
    │
    ▼
[SAVED] — paper appears in library ────→ Note row created (empty content)
```

All failure states result in no partial Paper record being persisted (transactional rollback).
Metadata extraction failures are the only exception — papers with partial metadata are allowed
(title required; other fields nullable).

---

## Validation Rules

- `title` is required; a paper cannot be saved without at least a title.
- `arxiv_id` must match pattern `^\d{4}\.\d{4,5}$` or the legacy `^[\w-]+/\d{7}$` if provided.
- `submission_url` must be a well-formed HTTP/HTTPS URL.
- `drive_file_id` must not be empty at save time.
- A Note's `content` may be empty string but must not be NULL.

---

## Database Schema (SQL)

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE papers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arxiv_id        TEXT UNIQUE,
    title           TEXT NOT NULL,
    authors         TEXT[] NOT NULL DEFAULT '{}',
    published_date  DATE,
    abstract        TEXT,
    submission_url  TEXT NOT NULL UNIQUE,
    drive_file_id   TEXT NOT NULL,
    drive_view_url  TEXT NOT NULL,
    added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector   TSVECTOR GENERATED ALWAYS AS (
                        to_tsvector('english',
                            title || ' ' ||
                            array_to_string(authors, ' ') || ' ' ||
                            COALESCE(abstract, ''))
                    ) STORED
);

CREATE INDEX idx_papers_search ON papers USING gin(search_vector);

CREATE TABLE notes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    UUID NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,
    content     TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
