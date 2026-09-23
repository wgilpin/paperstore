# 0001 — One library table, typed by `kind`

**Status:** accepted
**Date:** 2026-09-23

## Context

Reading lists (Release 1) link list items to library papers in the `papers` table. Release 2 adds non-paper material to the library: books, articles, videos, pasted text, and PDFs uploaded against a list item. Those entries need the same read flag, tags, notes and full-text search as papers, and a list item must be able to link to any of them.

Today `papers` assumes every entry has a PDF in Drive: `drive_file_id`, `drive_view_url` and `submission_url` are `NOT NULL`.

## Decision

Non-paper entries go in the existing `papers` table. A new `kind` column (default `paper`) says what each entry is. Release 2 makes the Drive and submission URL columns nullable. The table keeps its name.

Release 1 list items link to `papers.id` and must not assume that every row is a paper.

## Consequences

- A list item has one foreign key, and list queries join one table.
- Tags, notes, read state, search and the library view work for every kind without new joins.
- The table name `papers` is misleading once it holds books and notes. Code that reads `papers` must filter on `kind` where only papers make sense (the default library view, Drive download, summaries, the `/api/recent` feed).
- Paper-only columns (`arxiv_id`, `drive_*`, `summary_*`) are empty for other kinds.
- The search trigger must include `extracted_text` for non-paper kinds, because pasted text has no abstract.

## Alternatives rejected

- **A separate table for non-paper entries.** Keeps `papers` clean, but a list item then links to one of two tables. Every list query, the read flag, tags and notes must handle both.
- **Rename `papers` to `library_entries`.** Accurate, but it touches every query, model and API response for a naming gain. No Alembic makes the rename a manual, risky change on a live database.
- **Keep non-paper items on the list only.** This is the Release 1 behaviour. It fails the Release 2 requirement that this material is searchable and reusable across lists.
