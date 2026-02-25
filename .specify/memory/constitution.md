<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0 (initial ratification)
Modified principles: N/A (initial creation)
Added sections:
  - Core Principles (I–VI)
  - Technology Stack
  - Development Workflow
  - Governance
Templates updated:
  ✅ .specify/templates/plan-template.md — Constitution Check gates align with principles below
  ✅ .specify/templates/spec-template.md — no constitution-driven mandatory section changes required
  ✅ .specify/templates/tasks-template.md — test task guidance aligns with Principle III scope
Follow-up TODOs:
  - TODO(RATIFICATION_DATE): Set exact date when team formally ratifies; using initial-commit date as proxy.
-->

# PaperStore Constitution

## Core Principles

### I. Python + uv Toolchain

All backend code MUST be written in Python. The `uv` tool MUST be used for dependency management,
virtual environment creation, and script execution — no `pip`, `pip-tools`, or `poetry` directly.
Every project MUST include a `pyproject.toml` managed by `uv`.

**Rationale**: Consistent, fast toolchain reduces onboarding friction and environment drift.

### II. Prototype Simplicity (NON-NEGOTIABLE)

This codebase is a demo/prototype, not a production system. Code MUST be kept as simple as possible.

- No feature MUST be added without explicit user approval first.
- No speculative abstractions, no premature generalisation, no "future-proofing".
- YAGNI (You Aren't Gonna Need It) applies at all times.
- The minimum code that satisfies the requirement is the correct code.

**Rationale**: Complexity accumulates silently. Enforcing simplicity as a hard rule prevents scope
creep in a prototype context where iteration speed matters more than extensibility.

### III. Test-Driven Development — Backend Services Only

TDD MUST be applied to backend service logic:

- Tests MUST be written first and confirmed to fail before implementation begins.
- Red → Green → Refactor cycle is mandatory for backend services.

**Scope exclusions** — unit tests MUST NOT be written for:

- Frontend components (UI layer).
- API endpoint handlers (HTTP layer); these are covered by manual or integration testing.
- Any code path that would require calling a remote API (LLM, third-party service, etc.):
  if a test cannot run without a live remote API, it MUST NOT be written.

**Remote API rule**: Tests MUST NEVER call remote APIs. All external dependencies (LLMs, external
services) MUST be mocked. If mocking is impractical or pointless for a given test, the test MUST
be omitted entirely.

**Rationale**: Tests that depend on remote state are fragile, slow, and non-deterministic.
Frontend component tests offer low ROI in a prototype. Focussing TDD effort on business logic
maximises value.

### IV. Strong Typing (NON-NEGOTIABLE)

All Python code MUST use strong, explicit typing throughout:

- Every function argument and return value MUST have a type annotation.
- `TypedDict` or `pydantic` models MUST be used for structured data — plain `dict` is forbidden
  as a function argument or return type.
- The `Any` type MUST NOT be used. If `Any` appears to be necessary, reconsider the design.
- `mypy` MUST pass with no errors on all source files before code is considered complete.
- All code MUST pass `ruff` (linting + formatting) before saving.

**Rationale**: Strong typing catches bugs at development time, improves readability, and makes
refactoring safer — all critical in a prototype where the code will evolve rapidly.

### V. Infrastructure: PostgreSQL + Docker Compose

- PostgreSQL MUST be used as the storage backend. No other databases are permitted without
  explicit approval.
- The full development environment MUST be runnable via `docker compose up`.
- All services (app, database, any supporting services) MUST be defined in `docker-compose.yml`
  at the project root.

**Rationale**: Reproducible environments eliminate "works on my machine" problems. PostgreSQL
provides a robust, standard relational store appropriate for prototype and production alike.

### VI. No Unauthorised Feature Additions

New features MUST NOT be implemented without the user explicitly requesting them and confirming
the addition. This applies to:

- New endpoints, screens, or workflows.
- New dependencies or integrations.
- Any behaviour not described in the current feature specification.

When in doubt, ask before building.

**Rationale**: Prototype scope is especially prone to silent expansion. This principle keeps work
aligned with stated requirements.

## Technology Stack

| Concern | Choice |
| ------- | ------ |
| Language | Python 3.11 |
| Dependency manager | uv |
| Typing enforcement | mypy (strict mode recommended) |
| Linter/formatter | ruff |
| Data validation | pydantic / TypedDict |
| Database | PostgreSQL |
| Infrastructure | Docker Compose |
| Backend testing | pytest (services only, TDD) |
| Frontend testing | None (excluded by Principle III) |

## Development Workflow

1. **Specify** (`/speckit.specify`): Define the feature in business terms.
2. **Clarify** (`/speckit.clarify`): Resolve ambiguities before planning.
3. **Plan** (`/speckit.plan`): Design data model, contracts, and structure.
4. **Tasks** (`/speckit.tasks`): Generate ordered task list.
5. **Implement** (`/speckit.implement`): Execute tasks — TDD for backend services.

### Per-task implementation checklist

- [ ] Types annotated on all function signatures.
- [ ] No plain `dict` as argument or return type.
- [ ] No `Any` in new code.
- [ ] `mypy` passes.
- [ ] `ruff check` and `ruff format` pass.
- [ ] If backend service: test written first, confirmed failing, then implemented.
- [ ] No remote API called from any test.

## Governance

This constitution supersedes all other development practices for the PaperStore project. Any
conflict between a team convention and this constitution MUST be resolved in favour of the
constitution, or the constitution MUST be amended first.

### Amendment procedure

1. Propose the change with a rationale.
2. Increment the version (MAJOR/MINOR/PATCH per semantic versioning rules above).
3. Update `LAST_AMENDED_DATE`.
4. Propagate changes to affected templates (`plan-template.md`, `spec-template.md`,
   `tasks-template.md`).
5. Record the change in a Sync Impact Report comment at the top of this file.

### Versioning policy

- **MAJOR**: Removal or redefinition of an existing principle.
- **MINOR**: New principle or section added.
- **PATCH**: Clarification, wording fix, or non-semantic refinement.

### Compliance

All pull requests / code reviews MUST verify compliance with these principles. Violations MUST be
called out and resolved before merge.

**Version**: 1.0.0 | **Ratified**: 2026-02-25 | **Last Amended**: 2026-02-25
