# Issues — PaperStore reading lists

One line per issue, newest last. Status is `open`, `scheduled`, `fixed`,
or `dropped`. This file records issues. It never records stage status.

## ISS-1 — Dev writes ingested PDFs into the production Drive folder

**Raised:** 2026-09-23
**Status:** fixed
**Lands in:** fixed on epic-03-background-import (phase 02)

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

## ISS-7 — A library match by a cited ID skips the title check

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the phase 02 epic-01-library-match review. A cited arXiv ID or DOI that exists in the library is a confident match even when the titles disagree. The spike found 2 of 9 LLM-given arXiv IDs pointing at differently titled records.

## ISS-8 — Item URLs accept any scheme

**Raised:** 2026-09-23
**Status:** fixed
**Lands in:** fixed on epic-02-add-link (phase 03)

From the phase 02 epic-02-outside-lookup review. `_item.html` renders `item.url` as a link without checking for `http` or `https`. Phase 03 lets Will type URLs, so fix it there.

## ISS-9 — Lookup can prefer a reprint over the original

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the phase 02 epic-02-outside-lookup review. Collins 1975 matched a 1988 book chapter, confident on the author. Prefer the title match closest to the cited year.

## ISS-10 — Papers imported from a list skip the metadata step

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the phase 02 epic-03-background-import review. The library submit route runs `_enrich_paper_async` after ingestion; the list importer does not.

## ISS-11 — Ingestion cannot download some large arXiv PDFs

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

From the phase 03 epic-03-item-actions review. arXiv closed the connection at 3,145,728 of 16,402,634 bytes for 2507.06211, twice. The library's own submit uses the same download, so it fails there too.

## ISS-12 — The startup reset of stuck imports writes no log line

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

Found after the second production deploy. `reset_stuck_imports` marks items `import_failed` at startup but logs nothing, so a failure caused by a restart cannot be told apart from a real import failure.

## ISS-13 — The production container installs dev tools at every start

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

Found in the production log. The Dockerfile `CMD` runs `uv run` without `--no-dev`, so each start downloads ruff, mypy and pygments and re-resolves the lock ("Resolving despite existing lockfile"). Startup is slower and needs the network. Use `uv run --no-dev --frozen`.

## ISS-14 — The prod.sh health check passes on a redirect

**Raised:** 2026-09-23
**Status:** open
**Lands in:** unplanned

`prod.sh` calls `/tags`, which returns 307 to the login page, and `urlopen` follows it. Any running server passes, even with broken routes. Check an auth-exempt route that exercises the app, or treat a redirect as a failure.

## ISS-15 — A user cannot rename a reading list after creating it

**Raised:** 2026-09-24
**Status:** fixed 2026-09-24
**Lands in:** fixed on main

`concept.md` and phase 01 epic-04-manage-lists put rename out of scope, so no route existed. Will reported it on 2026-09-24 and chose to build it now, without a full `/sdlc:concept` pass. `concept.md` Out of scope now allows rename. Proved by `TestRenameList` in `backend/tests/unit/test_reading_lists.py`.
