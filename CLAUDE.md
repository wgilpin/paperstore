# PaperStore — Claude Development Guide

## Environment

- **OS**: Windows 11, developed in Git Bash
- **Shell**: Always use Unix shell syntax (forward slashes, `/dev/null`, not `NUL`)
- **File paths**: Use forward slashes in all commands and scripts (e.g., `src/models/foo.py`)
- **Python version**: 3.11
- **Python toolchain**: `uv` only — never use `pip`, `pip-tools`, or `poetry` directly

## Constitution

Project principles are in [.specify/memory/constitution.md](.specify/memory/constitution.md).
Read it before planning or implementing any feature. Key rules:

- Python + `uv` for all dependency management
- TDD for backend services only — no tests for frontend components or API endpoint handlers
- No remote API calls in tests — mock all external dependencies; skip tests that require a live LLM
- Keep code as simple as possible — this is a prototype, not a production system
- Never add features without explicit user approval
- Strong typing everywhere: pydantic/TypedDict, no plain `dict` args/returns, no `Any`
- All code must pass `mypy` and `ruff` before saving
- PostgreSQL for storage; Docker Compose for the full dev environment

## Workflow

Use the speckit commands in order:

1. `/speckit.specify` — write the feature spec
2. `/speckit.clarify` — resolve ambiguities (if needed)
3. `/speckit.plan` — design data model, contracts, structure
4. `/speckit.tasks` — generate ordered task list
5. `/speckit.implement` — execute tasks

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
Do not mention Claude or co-authors in commit messages.
Describe changes, not motivation or benefits.

## Recent Changes
- 001-paper-library: Added Python 3.11 + FastAPI + Uvicorn (web framework), SQLAlchemy + Alembic (ORM + migrations),
- 001-paper-library: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

## Active Technologies
- Python 3.11 + FastAPI + Uvicorn (web framework), SQLAlchemy, (001-paper-library)
- PostgreSQL (metadata + FTS via tsvector/GIN index); Google Drive (PDF files) (001-paper-library)
- We do not use Alembic
