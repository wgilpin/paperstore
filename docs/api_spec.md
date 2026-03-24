# Paperstore API Spec: `GET /api/recent`

## Purpose

Returns a list of recently saved papers for the news aggregator to summarize.

## Query params

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `since` | string (ISO 8601) | no | If provided, only return papers with `date > since`. If omitted, returns all papers. |

## Response

`200 OK` — JSON array of paper objects:

```json
[
  {
    "title": "Attention Is All You Need",
    "authors": "Vaswani et al.",
    "date": "2024-11-01T12:00:00Z",
    "url": "https://arxiv.org/abs/...",
    "summary": "Abstract text here...",
    "extracted_text": "Full or partial body text..."
  }
]
```

## Field details

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `title` | string | yes | |
| `authors` | string | no | Falls back to `"Unknown"` |
| `date` | string (ISO 8601) | yes | |
| `url` | string | no | Used as unique key to deduplicate summaries |
| `summary` | string | no | Abstract; preferred over `extracted_text` if present and non-empty |
| `extracted_text` | string | no | Fallback content; papers with neither field are skipped |

## Auth

None. Intended for local/OrbStack use only — not to be exposed publicly without adding a shared bearer token.
