"""Unit tests for SearchService."""

from unittest.mock import MagicMock

from src.services.search import SearchService


def _mock_paper(title: str = "Paper") -> MagicMock:
    p = MagicMock()
    p.title = title
    return p


def _make_db_returning(papers: list[MagicMock], total: int | None = None) -> MagicMock:
    """Mock db whose query chain returns *papers* and *total* from paginated calls."""
    count = total if total is not None else len(papers)
    db = MagicMock()
    # No-filter path: order_by().count() and order_by().offset().limit().all()
    no_filter = db.query.return_value.order_by.return_value
    no_filter.count.return_value = count
    no_filter.offset.return_value.limit.return_value.all.return_value = papers
    # Filter path: filter().order_by().count() and filter().order_by().offset().limit().all()
    with_filter = db.query.return_value.filter.return_value.order_by.return_value
    with_filter.count.return_value = count
    with_filter.offset.return_value.limit.return_value.all.return_value = papers
    return db


class TestSearchServiceSearch:
    def test_returns_all_papers_when_query_is_none(self) -> None:
        papers = [_mock_paper("A"), _mock_paper("B")]
        db = _make_db_returning(papers)

        result_papers, total = SearchService().search(None, db)

        assert result_papers == papers
        assert total == len(papers)
        # Should NOT call filter (no tsquery)
        db.query.return_value.filter.assert_not_called()

    def test_returns_all_papers_when_query_is_empty_string(self) -> None:
        papers = [_mock_paper()]
        db = _make_db_returning(papers)

        result_papers, total = SearchService().search("", db)

        assert result_papers == papers
        assert total == len(papers)
        db.query.return_value.filter.assert_not_called()

    def test_applies_tsquery_filter_for_non_empty_query(self) -> None:
        papers = [_mock_paper("Transformer paper")]
        db = _make_db_returning(papers)

        result_papers, total = SearchService().search("transformer", db)

        assert result_papers == papers
        assert total == len(papers)
        db.query.return_value.filter.assert_called_once()

    def test_returns_empty_list_when_no_match(self) -> None:
        db = _make_db_returning([])

        result_papers, total = SearchService().search("zzznomatch", db)

        assert result_papers == []
        assert total == 0
