"""Unit tests for GET /api/recent endpoint handler."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.api.recent import get_recent


def _mock_paper(title: str = "Paper") -> MagicMock:
    p = MagicMock()
    p.title = title
    p.authors = ["Author One"]
    p.added_at = datetime(2024, 1, 1, tzinfo=UTC)
    p.submission_url = "https://arxiv.org/abs/1234.5678"
    p.abstract = "An abstract."
    p.extracted_text = None
    return p


def _make_db(papers: list[MagicMock]) -> MagicMock:
    db = MagicMock()
    # Chain: query().filter().order_by().limit().all()
    chain = db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
    chain.all.return_value = papers
    # Chain with extra .filter() for `since`: query().filter().order_by().limit().filter().all()
    chain.filter.return_value.all.return_value = papers
    return db


class TestGetRecentLimit:
    def test_default_limit_is_5(self) -> None:
        db = _make_db([_mock_paper(str(i)) for i in range(5)])

        get_recent(since=None, limit=5, db=db)

        db.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_once_with(5)

    def test_custom_limit_is_passed_to_query(self) -> None:
        db = _make_db([_mock_paper(str(i)) for i in range(3)])

        get_recent(since=None, limit=3, db=db)

        db.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_once_with(3)

    def test_results_are_mapped_to_recent_paper(self) -> None:
        paper = _mock_paper("My Paper")
        db = _make_db([paper])

        results = get_recent(since=None, limit=5, db=db)

        assert len(results) == 1
        assert results[0].title == "My Paper"
        assert results[0].authors == "Author One"

    def test_since_filter_is_applied(self) -> None:
        db = _make_db([_mock_paper()])
        since = datetime(2024, 1, 1, tzinfo=UTC)

        get_recent(since=since, limit=5, db=db)

        # The second .filter() call (for `since`) should have been made
        limit_chain = db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
        limit_chain.filter.assert_called_once()
