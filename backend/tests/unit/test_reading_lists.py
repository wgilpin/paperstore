"""Unit tests for ReadingListService."""

import uuid
from unittest.mock import MagicMock

import pytest

from src.models.reading_list import ReadingList
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
