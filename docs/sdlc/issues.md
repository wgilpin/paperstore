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
