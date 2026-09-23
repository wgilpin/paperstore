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
