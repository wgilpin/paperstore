# SDLC state

Project: PaperStore — reading lists
Updated: 2026-09-23

## Stack

- Language: Python 3.11
- Web: FastAPI + Uvicorn; existing pages vanilla JS; new list pages Jinja2 templates + HTMX (vendored static file)
- Database: PostgreSQL 16 (pg_trgm already enabled)
- External: Gemini (list parsing), arXiv API (existing `arxiv` package), OpenAlex REST API via `httpx`, Google Drive
- Tests: pytest with mocks, run with `cd backend && uv run pytest`
- Lint and types: `cd backend && uv run ruff check src tests && uv run mypy src`
- Deploy: Docker Compose on OrbStack via `prod.sh`, exposed through cloudflared

## Stages

- concept: approved 2026-09-23
- explore: pending
- architecture: approved 2026-09-23
- design: pending
- phases: approved 2026-09-23

## Phases

- [x] 01-paste-and-tick — done
  - [x] epic-01-safe-database — merged 2026-09-23
  - [x] epic-02-paste-to-list — merged 2026-09-23
  - [x] epic-03-tick-items — merged 2026-09-23
  - [x] epic-04-manage-lists — merged 2026-09-23
  - [x] epic-05-parse-again — merged 2026-09-23
- [x] 02-find-and-import — done
  - [x] epic-01-library-match — reviewed 2026-09-23
  - [x] epic-02-outside-lookup — reviewed 2026-09-23
  - [x] epic-03-background-import — merged 2026-09-23
- [ ] 03-manual-paths — pending
- [ ] 04-mvp-test — pending
- [ ] 05-non-paper-material — pending

## Notes for a fresh session

- `.exploration/reading-lists.md` holds an earlier product-explore pass (gaps, red-team, Release 1 / Release 2 split).
- Release 2 must use the same library table as papers, with a type column. Release 1 list items must link to that table.
- Backups: host cron runs `scripts/backups_script.sh` daily at 03:15 into `~/backups/postgres/` (14 days). Kept as is by choice; no compose backup service.
