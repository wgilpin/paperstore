# PaperStore API

Base URL: `https://papers.teleosis.ai`

All endpoints except `/auth/*` and `GET /api/recent` require an active session (set via Google OAuth login).

---

## Auth

### `GET /auth/login`

Initiates Google OAuth 2.0 flow. Redirects to Google.

### `GET /auth/callback`

OAuth callback. Stores credentials, sets session cookie, redirects to `/`.

---

## Papers

### `GET /papers`

List papers with optional search and filtering.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | — | Full-text search query |
| `sort` | `added_at` \| `title` \| `published_date` | `added_at` | Sort field |
| `page` | int | `1` | Page number |
| `tag` | string | — | Filter by tag name |

**Response `200`**

```json
{
  "papers": [PaperSummary],
  "total": 42
}
```

---

### `POST /papers`

Submit a paper by URL (arXiv page or direct PDF link).

**Request body**

```json
{ "url": "https://arxiv.org/abs/2301.00001" }
```

**Response `201`** — `{ "paper": PaperDetail }`

**Errors** — `409` duplicate, `422` invalid URL, `502` Drive upload failed

---

### `POST /papers/upload`

Upload a PDF file directly.

**Request** — `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | PDF file | Yes |
| `source_url` | string | No |

**Response `201`** — `{ "paper": PaperDetail }`

**Errors** — `409` duplicate, `422` not a PDF, `502` Drive upload failed

---

### `GET /papers/{paper_id}`

Get a single paper by ID.

**Response `200`** — `{ "paper": PaperDetail }`
**Errors** — `404`

---

### `PATCH /papers/{paper_id}`

Update paper metadata.

**Request body**

```json
{
  "title": "string",
  "authors": ["string"],
  "published_date": "2024-01-15",
  "abstract": "string | null",
  "tags": ["string"]
}
```

**Response `200`** — `{ "paper": PaperDetail }`
**Errors** — `404`

---

### `DELETE /papers/{paper_id}`

Delete a paper and its note.

**Response `204`**
**Errors** — `404`

---

### `PATCH /papers/{paper_id}/note`

Update the note for a paper.

**Request body**

```json
{ "content": "string" }
```

**Response `200`** — `{ "note": { "content": "string", "updated_at": "datetime" } }`
**Errors** — `404`

---

### `POST /papers/{paper_id}/extract-metadata`

Extract metadata from the paper's PDF using Gemini.

**Response `200`**

```json
{
  "metadata": {
    "title": "string | null",
    "authors": ["string"],
    "date": "string | null",
    "abstract": "string | null"
  }
}
```

**Errors** — `404`, `502` Drive error, `503` Gemini error

---

### `GET /papers/{paper_id}/pdf`

Redirect to the paper's PDF on Google Drive.

**Response `302`**
**Errors** — `404`

---

## Tags

### `GET /tags`

List all tag names ordered by frequency.

**Response `200`** — `{ "tags": ["string"] }`

---

### `GET /tags/with-counts`

List all tags with paper counts.

**Response `200`**

```json
{ "tags": [{ "name": "string", "count": 3 }] }
```

---

### `PATCH /tags/{name}`

Rename a tag.

**Request body** — `{ "name": "new-name" }`

**Response `204`**
**Errors** — `404`, `409` name already exists, `422` empty name

---

### `POST /tags/{name}/merge`

Merge a tag into another (source tag is deleted).

**Request body** — `{ "into": "target-tag" }`

**Response `204`**
**Errors** — `404`, `422` source and target are the same

---

### `DELETE /tags/{name}`

Delete a tag.

**Response `204`**
**Errors** — `404`

---

## Batch Metadata

### `GET /batch/metadata/eligible-count`

Count of papers eligible for metadata extraction and estimated Gemini cost.

**Response `200`**

```json
{ "count": 12, "estimated_cost_usd": 0.036 }
```

---

### `GET /batch/metadata/status`

Current batch extraction loop status.

**Response `200`**

```json
{ "status": { "running": true, "papers_done": 5 } }
```

---

### `POST /batch/metadata/start`

Start the background metadata extraction loop.

**Response `200`** — `{ "status": BatchLoopStatus }`

---

### `POST /batch/metadata/stop`

Stop the background metadata extraction loop.

**Response `200`** — `{ "status": BatchLoopStatus }`

---

## Recent Papers (External)

### `GET /api/recent`

Recently saved papers for external consumers (e.g. news aggregator).

**Auth** — `Authorization: Bearer <RECENT_API_TOKEN>`

| Param | Type | Description |
|-------|------|-------------|
| `since` | datetime | Only return papers added after this time |

**Response `200`**

```json
[
  {
    "title": "string",
    "authors": "Author One, Author Two",
    "date": "datetime",
    "url": "string",
    "summary": "string | null",
    "extracted_text": "string | null"
  }
]
```

**Errors** — `401` missing/invalid token

---

## Schemas

### PaperSummary

```json
{
  "id": "uuid",
  "arxiv_id": "string | null",
  "title": "string",
  "authors": ["string"],
  "published_date": "date | null",
  "added_at": "datetime",
  "tags": ["string"]
}
```

### PaperDetail

```json
{
  "id": "uuid",
  "arxiv_id": "string | null",
  "title": "string",
  "authors": ["string"],
  "published_date": "date | null",
  "abstract": "string | null",
  "submission_url": "string",
  "drive_view_url": "string",
  "added_at": "datetime",
  "note": {
    "content": "string",
    "updated_at": "datetime"
  },
  "tags": ["string"]
}
```
