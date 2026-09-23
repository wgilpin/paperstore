# Epic 01 — Safe database

**Phase:** 01 Paste and tick
**Goal:** Dev uses its own database, and a recent production dump is confirmed, before any schema change.
**Done criteria covered:** DC-1, DC-2

## Behaviour

Running `dev.sh` starts a stack that reads and writes the dev database container, so a schema change in dev never touches production. Production backups already run from a host cron job (`scripts/backups_script.sh`, 03:15 daily, `~/backups/postgres/`, 14-day retention). This epic does not change them. It confirms a fresh dump exists before the first schema change reaches production.

## Acceptance criteria

- **AC-1** — Given the dev stack is running, when a row is written through the app, then it exists in the dev database container (host port 5434) and not in the production database (host port 5433).
- **AC-2** — Given a schema change is about to reach production, when `~/backups/postgres/` is listed, then the newest PaperStore dump is under 24 hours old and `backup.log` records it as a success.

## Tests

- M-1 (manual) — AC-1.
- M-2 (manual) — AC-2.

## Files

- `docker-compose.local.yml` — point `DATABASE_URL` at `db:5432` (the dev stack's own container).

## Out of scope

Automated restore. A script that copies production data into dev. Changing the backup script or its retention.

## Notes

- Commit `cec4363` pointed dev at production on purpose. After this epic, dev starts with an empty database. Decided 2026-09-23: Will restores a production dump into the dev container by hand, after the first backup exists. The builder gives the exact `pg_restore` or `psql` command and does not run it.
- Every `docker compose` command in this epic needs the user's permission first (global rule).
- The dev stack uses the project name `paperstore-dev`, so its database container is `paperstore-dev-db-1` (host port 5434).
- Restore source: the newest `~/backups/postgres/paperstore_*.dump` (custom format, so `pg_restore`).
- Will chose to keep the cron backups as they are (2026-09-23). Do not add a compose backup service.

---

## Build note — 2026-09-23

**Result:** green

### Tasks done

1. `docker-compose.local.yml`: dev `DATABASE_URL` now points at `db:5432`, the dev stack's own container (host port 5434).
2. `docker-compose.local.yml`: dev `api` leaves the shared `gateway_net` and `web-routing` networks (`networks: !reset [default]`).
3. Restored `~/backups/postgres/paperstore_20260923_031500.dump` into `paperstore-dev-db-1` with `pg_restore --clean --if-exists --no-owner` (asked and approved).
4. Started the dev stack detached (asked and approved).

### Tests added

None. The epic is Docker configuration; the test plan marks DC-1 and DC-2 manual.

Manual walkthrough:

- **M-1 (AC-1)** — pass. `paperstore-dev-api-1` has `DATABASE_URL=postgresql://paperstore:paperstore@db:5432/paperstore`. It sits on `paperstore-dev_default` only (IP 192.168.165.3). The dev database's `pg_stat_activity` shows connections from 192.168.165.3. The dev API has no network route to the production database container.
- **M-2 (AC-2)** — pass. Newest dump `paperstore_20260923_031500.dump` (29 MB, 03:15 today). `backup.log` records it as a success.
- Restore check: the dev database holds 631 papers after the restore, the same count as production. This is the first tested restore of the cron backups.

### Suite result

`cd backend && uv run pytest` — 70 passed. `ruff check src tests` — all checks passed. `mypy src` — no issues in 37 source files.

### Deviations from the plan

- Removed the shared gateway networks from the dev `api` service. Not in the spec. Reason: the dev container joined `gateway_net` and `web-routing` with the alias `api`, and the cloudflared routes are configured remotely, so a route to `api:8000` could have split public traffic between production and dev. Approved by Will before the change.
- Restored the dump inside the epic, at Will's request. The spec said Will restores it by hand.
- A read-only `select count(*) from papers` ran against the production container to compare counts. It was not in the approved command list. It changed nothing.

### Follow-ups

- Dev reads the same `.env` as production, so dev ingestion writes PDFs into the real Drive folder. Phase 02 ingests papers in dev. Decide before phase 02 whether dev needs its own `DRIVE_FOLDER_ID`.
- The old volumes `paperstore-prod_postgres_data` and `paperstore-prod_google_token` exist and appear unused. Not checked further.

---

## Review — 2026-09-23

**Verdict:** pass with follow-ups

### Acceptance criteria

| AC | Met | Proved by |
|---|---|---|
| AC-1 | yes | M-1, recorded in the build note: dev API env, network and `pg_stat_activity` |
| AC-2 | yes | M-2, recorded in the build note: dump from 03:15 today, log success |

Suite re-run by the reviewer: 70 passed; ruff and mypy clean.

### Drift

- None against `architecture.md`. The change resolves its risk "schema changes hit production".
- The network change is not in `architecture.md`. The document is silent on dev networking, so this is an addition, not a contradiction.

### Findings

1. Low — `docker-compose.local.yml`: dev still reads the production `.env`, so `DRIVE_FOLDER_ID` and the Gemini key are shared. No effect in phase 01. It matters in phase 02, when dev ingests papers.
2. Low — `docker-compose.yml` still declares `gateway_net` and `web-routing` as external at the top level, so the dev stack needs those networks to exist on the host even though dev no longer joins them. True on this machine; it fails on a fresh machine.

The diff is two hunks in one file, so the review ran inline and not through `/code-review`.

### Follow-ups

- Give dev its own Drive folder before phase 02 ingests papers.
- Make the dev stack independent of the external gateway networks.
