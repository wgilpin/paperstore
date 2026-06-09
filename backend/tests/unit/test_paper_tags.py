"""Unit tests for Paper Tags API endpoint."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.api.papers import update_paper_tags
from src.schemas.paper import PaperTagsUpdateRequest


def _make_paper_id() -> uuid.UUID:
    return uuid.uuid4()


class TestPaperTagsUpdate:
    def test_updates_tags_successfully(self) -> None:
        paper_id = _make_paper_id()
        mock_paper = MagicMock()
        mock_paper.id = paper_id
        mock_paper.tags = []

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            mock_paper,  # first call: db.query(Paper)
            None,  # second call: db.query(Tag) for "ai"
            None,  # third call: db.query(Tag) for "neural-networks"
        ]

        body = PaperTagsUpdateRequest(tags=["ai", "neural-networks"])

        # Call API function directly
        result = update_paper_tags(str(paper_id), body, db)

        # Assert paper was queried
        db.query.assert_called()

        # Verify db was committed and refreshed
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(mock_paper)

        # Result should be a dictionary with tags
        assert "tags" in result
        assert isinstance(result["tags"], list)

    def test_raises_not_found_when_paper_does_not_exist(self) -> None:
        paper_id = _make_paper_id()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        body = PaperTagsUpdateRequest(tags=["science"])

        with pytest.raises(HTTPException) as exc_info:
            update_paper_tags(str(paper_id), body, db)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Paper not found"
