# Issues — PaperStore reading lists

One line per issue, newest last. Status is `open`, `scheduled`, `fixed`,
or `dropped`. This file records issues. It never records stage status.

## ISS-1 — Dev writes ingested PDFs into the production Drive folder

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the epic-01-safe-database review. Dev reads the production `.env`, so `DRIVE_FOLDER_ID` is shared. Decide before phase 02 ingests papers in dev.

## ISS-2 — The dev stack needs the external gateway networks to exist

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the epic-01-safe-database review. `docker-compose.yml` declares `gateway_net` and `web-routing` as external, so dev fails on a machine without them.

## ISS-3 — Parsing a long list can outlast the proxy timeouts

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the epic-02-paste-to-list review. A 16-item list took 27 seconds inside the request. Check the cloudflared and Caddy timeouts against a 40-item list, or parse in the background.

## ISS-4 — The new-list form shows nothing when the POST fails

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the epic-02-paste-to-list review. A missing Gemini key gives a JSON 500; HTMX does not swap it, so the indicator stops with no message.

## ISS-5 — Two existing files fail `ruff format --check`

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

Found during epic-02-paste-to-list. `src/api/papers.py` and `tests/unit/test_drive.py` need reformatting. Not caused by the reading-lists work.

## ISS-6 — Parse again can replace the items of a list that parsed fine

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the epic-05-parse-again review. `POST /lists/{id}/parse` does not check `parse_failed`, so a direct request loses the list's ticks.
