# Phase 01 — Paste and tick

**Goal:** Paste an LLM reading list and get an ordered, tickable list page.

## Scope

- Infrastructure: a dev stack that uses its own database container. Backups already run from a host cron job and do not change.
- New tables `reading_lists` and `reading_list_items`, created by `create_tables()`.
- New services `reading_list_parser.py` (Gemini) and `reading_lists.py` (business rules).
- New router `api/reading_lists.py` under `/lists`, returning Jinja2 templates with HTMX. It must not sit under `/api/`, because `/api/` is exempt from auth.
- New dependency `jinja2`. HTMX vendored as `frontend/static/htmx.min.js`.
- A "Reading lists" link in the library page menu.
- `papers` is not touched.

## Done criteria

- **DC-1** — The dev stack (`dev.sh`) reads and writes its own database container, not the production database.
- **DC-2** — Before the first schema change reaches production, `~/backups/postgres/` holds a PaperStore dump from the last 24 hours, and `backup.log` records it as a success.
- **DC-3** — Pasting list text with a name creates a list. Its page shows the items in the pasted order, each with its title, authors, year and the LLM's note.
- **DC-4** — Ticking an item persists across a page reload. Unticking clears it.
- **DC-5** — A list page shows its progress as "n of m read".
- **DC-6** — A lists index, linked from the library menu, shows every list with its name, created date and progress, newest first.
- **DC-7** — Dropping an item removes it from the list. The other items keep their order.
- **DC-8** — Deleting a list, after a confirmation, removes the list and its items. Library papers are unchanged.
- **DC-9** — If parsing fails or finds no items, the list is saved with its raw text. The page says parsing failed and offers "parse again". A successful parse again replaces the items.
- **DC-10** — List pages need a login. A request without a session is redirected to the login page.

## Not in this phase

Any citation lookup, links to library papers, imports, `papers` changes, URLs on items, add item, reorder, archive.

## Epics

1. `epic-01-safe-database.md` — dev gets its own database, and a recent production dump is confirmed. Precondition for every later epic.
2. `epic-02-paste-to-list.md` — tracer: paste a list, Gemini parses it, the list page renders the items.
3. `epic-03-tick-items.md` — tick and untick items, with progress on the list page.
4. `epic-04-manage-lists.md` — lists index, menu link, drop item, delete list.
5. `epic-05-parse-again.md` — keep the raw text when parsing fails, and parse again.

Epics 03, 04 and 05 each need epic 02 only. They are independent of each other.

## Risks

- **Section headings are dropped.** LLM lists group items under headings ("Cognitive foundations"). Phase 01 keeps item order but not the headings. Keeping them is a feature change, so it needs approval.
- **Parsing runs inside the request.** A 40-item list can take 10 to 20 seconds in Gemini. The form shows an HTMX loading indicator. If this is too slow, move parsing to a background thread in a later epic.
- **Gemini model setting.** The parser reuses `GEMINI_PDF_MODEL` to avoid a new setting.
- **Unit tests mock the session.** Ordering and cascade deletes are proved by service tests against a mock, and by the manual walkthrough against a real database.
