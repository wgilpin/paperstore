# Test plan — Phase 01 Paste and tick

## Coverage

The constitution allows unit tests for backend services only. API handlers and templates have no unit tests, so their behaviour is proved by the manual walkthrough. Services are tested with a mocked session and a mocked Gemini client.

| Done criterion | Proved by | Kind |
|---|---|---|
| DC-1 | M-1: run `dev.sh`, create a list, confirm with `psql` on port 5434 that the row exists, and on port 5433 that it does not | manual |
| DC-2 | M-2: before deploying the first schema change, run `ls -la ~/backups/postgres/ \| grep paperstore \| tail -1` and `tail -3 ~/backups/postgres/backup.log`; the newest dump is under 24 hours old and the log shows it succeeded | manual |
| DC-3 | `test_reading_list_parser.py::test_parses_items_in_order_with_notes`, `test_reading_lists.py::test_create_list_stores_items_with_positions`; M-3 | automated + manual |
| DC-4 | `test_reading_lists.py::test_toggle_tick_sets_read_at`, `::test_toggle_tick_clears_read_at`; M-4 | automated + manual |
| DC-5 | `test_reading_lists.py::test_progress_counts_ticked_items`; M-4 | automated + manual |
| DC-6 | `test_reading_lists.py::test_list_summaries_newest_first_with_progress`; M-5 | automated + manual |
| DC-7 | `test_reading_lists.py::test_drop_item_deletes_only_that_item`, `::test_drop_item_unknown_raises_not_found`; M-6 | automated + manual |
| DC-8 | `test_reading_lists.py::test_delete_list_deletes_list`, `::test_delete_list_unknown_raises_not_found`; M-7 | automated + manual |
| DC-9 | `test_reading_list_parser.py::test_returns_empty_on_invalid_json`, `::test_returns_empty_on_empty_response`, `test_reading_lists.py::test_create_list_with_no_items_marks_parse_failed`, `::test_parse_again_replaces_items`; M-8 | automated + manual |
| DC-10 | M-9: in a private window, open `/lists` and confirm a redirect to `/auth/login` | manual |

### Manual walkthrough

- **M-3** — Paste list one from the spike (16 items) with the name "Memory". The page shows 16 items in the pasted order, each with title, authors, year and note.
- **M-4** — Tick items 1 and 3. The page shows "2 of 16 read". Reload: both are still ticked. Untick item 3: "1 of 16 read".
- **M-5** — Open the library menu, click "Reading lists". Both test lists appear, newest first, with name, date and progress.
- **M-6** — Drop item 2. It disappears. Items 1 and 3 onward keep their order after a reload.
- **M-7** — Delete a list and confirm. It disappears from the index. The library page shows the same paper count as before.
- **M-8** — Set `GEMINI_API_KEY` to an invalid value in dev, paste a list. The page says parsing failed and shows the raw text. Restore the key, click "parse again". The items appear.

## Gaps

None. DC-1, DC-2 and DC-10 are manual only: they concern Docker configuration and the auth middleware, which no service test reaches.

## How to run

```bash
cd backend && uv run pytest
```

Then `cd backend && uv run ruff check src tests && uv run mypy src`.

## Test data

- Mocked `Session` (`MagicMock`), as in `tests/unit/test_notes.py`.
- Mocked Gemini client returning fixed JSON for a three-item list, an empty response, and invalid JSON.
- For the manual walkthrough: the two reading lists from the spike.
