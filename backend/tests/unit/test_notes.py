"""Unit tests for NotesService."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.services.notes import NotesService, NotFoundError


def _make_paper_id() -> uuid.UUID:
    return uuid.uuid4()


def _mock_note(content: str = "", paper_id: uuid.UUID | None = None) -> MagicMock:
    note = MagicMock()
    note.content = content
    note.updated_at = datetime(2026, 1, 1, 12, 0, 0)
    note.paper_id = paper_id or _make_paper_id()
    return note


class TestNotesServiceUpsert:
    def test_updates_content_on_existing_note(self) -> None:
        paper_id = _make_paper_id()
        existing_note = _mock_note(content="old content", paper_id=paper_id)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(),  # paper found
            existing_note,  # note found
        ]

        result = NotesService().upsert(paper_id, "new content", db)

        assert existing_note.content == "new content"
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(existing_note)
        assert result.content == existing_note.content

    def test_raises_not_found_error_when_paper_does_not_exist(self) -> None:
        paper_id = _make_paper_id()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            NotesService().upsert(paper_id, "some content", db)

    def test_returns_note_response_with_updated_at(self) -> None:
        paper_id = _make_paper_id()
        existing_note = _mock_note(content="", paper_id=paper_id)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(),  # paper found
            existing_note,  # note found
        ]

        result = NotesService().upsert(paper_id, "my note", db)

        # Service sets updated_at to now(); result must be a datetime
        assert isinstance(result.updated_at, datetime)
