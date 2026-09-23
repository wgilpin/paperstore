"""Unit tests for ReadingListService."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.models.reading_list import ReadingList, ReadingListItem
from src.schemas.reading_list import ParsedItem
from src.services.notes import NotFoundError
from src.services.reading_lists import ReadingListService


def _item(title: str, year: int | None = 2020, note: str | None = None) -> ParsedItem:
    return ParsedItem(
        citation=f"{title} ({year})", title=title, authors=["A"], year=year, note=note
    )


class TestCreateList:
    def test_create_list_stores_items_with_positions(self) -> None:
        db = MagicMock()
        items = [_item("First", note="Read first."), _item("Second"), _item("Third", year=None)]

        result = ReadingListService().create_list("Memory", "raw pasted text", items, db)

        db.add.assert_called_once_with(result)
        db.commit.assert_called_once()
        assert result.name == "Memory"
        assert result.raw_text == "raw pasted text"
        assert [(i.position, i.title) for i in result.items] == [
            (0, "First"),
            (1, "Second"),
            (2, "Third"),
        ]
        assert result.items[0].note == "Read first."
        assert result.items[0].citation == "First (2020)"
        assert result.items[0].authors == ["A"]
        assert result.items[2].year is None


class TestCreateListParseFailed:
    def test_create_list_with_no_items_marks_parse_failed(self) -> None:
        db = MagicMock()

        result = ReadingListService().create_list("Memory", "raw pasted text", [], db)

        db.add.assert_called_once_with(result)
        assert result.raw_text == "raw pasted text"
        assert result.items == []
        assert result.parse_failed is True

    def test_create_list_with_items_is_not_marked_parse_failed(self) -> None:
        db = MagicMock()

        result = ReadingListService().create_list("Memory", "raw", [_item("First")], db)

        assert result.parse_failed is False


class TestParseAgain:
    def test_parse_again_replaces_items(self) -> None:
        stored = ReadingList(name="Memory", raw_text="raw", parse_failed=True, items=[])
        db = MagicMock()
        db.get.return_value = stored

        result = ReadingListService().parse_again(
            uuid.uuid4(), [_item("First"), _item("Second")], db
        )

        assert result is stored
        assert [(i.position, i.title) for i in stored.items] == [(0, "First"), (1, "Second")]
        assert stored.parse_failed is False
        db.commit.assert_called_once()

    def test_parse_again_with_no_items_keeps_parse_failed(self) -> None:
        stored = ReadingList(name="Memory", raw_text="raw", parse_failed=True, items=[])
        db = MagicMock()
        db.get.return_value = stored

        ReadingListService().parse_again(uuid.uuid4(), [], db)

        assert stored.items == []
        assert stored.parse_failed is True


class TestGetList:
    def test_get_list_returns_the_list(self) -> None:
        db = MagicMock()
        stored = ReadingList(name="Memory", raw_text="raw")
        db.get.return_value = stored

        assert ReadingListService().get_list(uuid.uuid4(), db) is stored

    def test_get_list_unknown_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().get_list(uuid.uuid4(), db)


def _stored_item(list_id: uuid.UUID, read_at: datetime | None = None) -> ReadingListItem:
    return ReadingListItem(
        list_id=list_id, position=0, citation="c", title="t", authors=[], read_at=read_at
    )


class TestToggleTick:
    def test_toggle_tick_sets_read_at(self) -> None:
        list_id = uuid.uuid4()
        item = _stored_item(list_id)
        db = MagicMock()
        db.get.return_value = item

        result = ReadingListService().toggle_tick(list_id, uuid.uuid4(), db)

        assert result is item
        assert item.read_at is not None
        db.commit.assert_called_once()

    def test_toggle_tick_clears_read_at(self) -> None:
        list_id = uuid.uuid4()
        item = _stored_item(list_id, read_at=datetime(2026, 9, 1, 12, 0))
        db = MagicMock()
        db.get.return_value = item

        ReadingListService().toggle_tick(list_id, uuid.uuid4(), db)

        assert item.read_at is None
        db.commit.assert_called_once()

    def test_toggle_tick_unknown_item_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().toggle_tick(uuid.uuid4(), uuid.uuid4(), db)

    def test_toggle_tick_item_of_another_list_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = _stored_item(uuid.uuid4())

        with pytest.raises(NotFoundError):
            ReadingListService().toggle_tick(uuid.uuid4(), uuid.uuid4(), db)
        db.commit.assert_not_called()


class TestProgress:
    def test_progress_counts_ticked_items(self) -> None:
        list_id = uuid.uuid4()
        ticked = datetime(2026, 9, 1, 12, 0)
        reading_list = ReadingList(
            name="Memory",
            raw_text="raw",
            items=[
                _stored_item(list_id, read_at=ticked),
                _stored_item(list_id),
                _stored_item(list_id, read_at=ticked),
                _stored_item(list_id),
            ],
        )

        progress = ReadingListService().progress(reading_list)

        assert (progress.read, progress.total) == (2, 4)


class TestListSummaries:
    def test_list_summaries_newest_first_with_progress(self) -> None:
        older_id, newer_id = uuid.uuid4(), uuid.uuid4()
        older = ReadingList(
            id=older_id,
            name="Older",
            raw_text="raw",
            created_at=datetime(2026, 9, 1, 9, 0),
            items=[_stored_item(older_id, read_at=datetime(2026, 9, 2)), _stored_item(older_id)],
        )
        newer = ReadingList(
            id=newer_id,
            name="Newer",
            raw_text="raw",
            created_at=datetime(2026, 9, 20, 9, 0),
            items=[_stored_item(newer_id)],
        )
        db = MagicMock()
        db.query.return_value.all.return_value = [older, newer]

        summaries = ReadingListService().list_summaries(db)

        assert [s.name for s in summaries] == ["Newer", "Older"]
        assert summaries[0].id == newer_id
        assert summaries[0].created_at == datetime(2026, 9, 20, 9, 0)
        assert (summaries[1].progress.read, summaries[1].progress.total) == (1, 2)


class TestDropItem:
    def test_drop_item_deletes_only_that_item(self) -> None:
        list_id = uuid.uuid4()
        first, second, third = (_stored_item(list_id) for _ in range(3))
        first.position, second.position, third.position = 0, 1, 2
        db = MagicMock()
        db.get.return_value = second

        ReadingListService().drop_item(list_id, uuid.uuid4(), db)

        db.delete.assert_called_once_with(second)
        db.commit.assert_called_once()
        assert (first.position, third.position) == (0, 2)

    def test_drop_item_unknown_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().drop_item(uuid.uuid4(), uuid.uuid4(), db)
        db.delete.assert_not_called()

    def test_drop_item_of_another_list_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = _stored_item(uuid.uuid4())

        with pytest.raises(NotFoundError):
            ReadingListService().drop_item(uuid.uuid4(), uuid.uuid4(), db)
        db.delete.assert_not_called()


class TestDeleteList:
    def test_delete_list_deletes_list(self) -> None:
        stored = ReadingList(name="Memory", raw_text="raw")
        db = MagicMock()
        db.get.return_value = stored

        ReadingListService().delete_list(uuid.uuid4(), db)

        db.delete.assert_called_once_with(stored)
        db.commit.assert_called_once()

    def test_delete_list_unknown_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().delete_list(uuid.uuid4(), db)
        db.delete.assert_not_called()
