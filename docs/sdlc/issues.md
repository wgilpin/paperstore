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
**Status:** open
**Lands in:** unplanned

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
