"""Unit tests for SearchService."""

from unittest.mock import MagicMock

from src.services.search import SearchService


def _mock_paper(title: str = "Paper") -> MagicMock:
    p = MagicMock()
    p.title = title
    return p


def _make_db_returning(papers: list[MagicMock]) -> MagicMock:
    """Mock db whose query chain returns *papers* from .all()."""
    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = papers
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = papers
    return db


class TestSearchServiceSearch:
    def test_returns_all_papers_when_query_is_none(self) -> None:
        papers = [_mock_paper("A"), _mock_paper("B")]
        db = _make_db_returning(papers)

        result = SearchService().search(None, db)

        assert result == papers
        # Should NOT call filter (no tsquery)
        db.query.return_value.filter.assert_not_called()

    def test_returns_all_papers_when_query_is_empty_string(self) -> None:
        papers = [_mock_paper()]
        db = _make_db_returning(papers)

        result = SearchService().search("", db)

        assert result == papers
        db.query.return_value.filter.assert_not_called()

    def test_applies_tsquery_filter_for_non_empty_query(self) -> None:
        papers = [_mock_paper("Transformer paper")]
        db = _make_db_returning(papers)

        result = SearchService().search("transformer", db)

        assert result == papers
        db.query.return_value.filter.assert_called_once()

    def test_returns_empty_list_when_no_match(self) -> None:
        db = _make_db_returning([])

        result = SearchService().search("zzznomatch", db)

        assert result == []
