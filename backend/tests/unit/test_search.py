"""Unit tests for SearchService."""

from unittest.mock import MagicMock

from src.services.search import SearchService, read_filter


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
        db.query.return_value.filter.assert_called()

    def test_returns_empty_list_when_no_match(self) -> None:
        db = _make_db_returning([])

        result_papers, total = SearchService().search("zzznomatch", db)

        assert result_papers == []
        assert total == 0

    def test_search_by_tag_name(self) -> None:
        papers = [_mock_paper("Paper on consciousness")]
        db = _make_db_returning(papers)

        result_papers, total = SearchService().search("consciousness", db)

        assert result_papers == papers
        assert total == len(papers)
        db.query.return_value.filter.assert_called()


class TestReadFilter:
    def test_read_filter_expressions(self) -> None:
        unread, read = read_filter("unread"), read_filter("read")

        assert unread is not None and str(unread.compile()) == "papers.read_at IS NULL"
        assert read is not None and str(read.compile()) == "papers.read_at IS NOT NULL"
        assert read_filter(None) is None

    def test_read_filter_applied_to_listing(self) -> None:
        db = _make_db_returning([_mock_paper("A")])
        listing = db.query.return_value.order_by.return_value
        listing.filter.return_value = listing  # the read filter keeps the same chain

        SearchService().search(None, db, read="read")

        (expr,), _ = listing.filter.call_args
        assert str(expr.compile()) == "papers.read_at IS NOT NULL"

    def test_no_read_filter_by_default(self) -> None:
        db = _make_db_returning([_mock_paper("A")])

        SearchService().search(None, db)

        db.query.return_value.order_by.return_value.filter.assert_not_called()
