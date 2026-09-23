"""Unit tests for CitationResolver and its matching rules."""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from src.models.paper import Paper
from src.schemas.reading_list import ParsedItem
from src.services.citation_resolver import CitationResolver


def _query(citation: str, title: str, authors: list[str], year: int | None) -> ParsedItem:
    return ParsedItem(citation=citation, title=title, authors=authors, year=year, note=None)


def _paper(title: str, authors: list[str], year: int, arxiv_id: str | None = None) -> Paper:
    return Paper(
        id=uuid.uuid4(),
        title=title,
        authors=authors,
        published_date=date(year, 1, 1),
        arxiv_id=arxiv_id,
    )


_LIB = "src.services.citation_resolver"


class TestLibraryMatch:
    @patch(f"{_LIB}.library_by_title", return_value=[])
    @patch(f"{_LIB}.library_by_doi", return_value=None)
    @patch(f"{_LIB}.library_by_arxiv_id")
    def test_library_match_by_arxiv_id(
        self, by_arxiv: MagicMock, by_doi: MagicMock, by_title: MagicMock
    ) -> None:
        paper = _paper("Dense Associative Memory for Pattern Recognition", ["D. Krotov"], 2016)
        by_arxiv.return_value = paper
        query = _query(
            'Krotov and Hopfield (2016), "Dense Associative Memory", arXiv 1606.01164',
            "Dense Associative Memory for Pattern Recognition",
            ["Krotov", "Hopfield"],
            2016,
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        by_arxiv.assert_called_once()
        assert by_arxiv.call_args.args[0] == "1606.01164"
        assert candidate is not None
        assert candidate.paper_id == paper.id
        assert candidate.outcome == "in_library"
        assert candidate.confident is True

    @patch(f"{_LIB}.library_by_title", return_value=[])
    @patch(f"{_LIB}.library_by_doi")
    @patch(f"{_LIB}.library_by_arxiv_id", return_value=None)
    def test_library_match_by_doi(
        self, by_arxiv: MagicMock, by_doi: MagicMock, by_title: MagicMock
    ) -> None:
        paper = _paper("Computational principles of synaptic memory consolidation", ["Benna"], 2016)
        by_doi.return_value = paper
        query = _query(
            "Benna and Fusi (2016), Nature Neuroscience, doi:10.1038/nn.4401",
            "Computational principles of synaptic memory consolidation",
            ["Benna", "Fusi"],
            2016,
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        assert by_doi.call_args.args[0] == "10.1038/nn.4401"
        assert candidate is not None
        assert candidate.paper_id == paper.id
        assert candidate.outcome == "in_library"
        assert candidate.confident is True

    @patch(f"{_LIB}.library_by_title")
    @patch(f"{_LIB}.library_by_doi", return_value=None)
    @patch(f"{_LIB}.library_by_arxiv_id", return_value=None)
    def test_library_title_match_used_when_ids_miss(
        self, by_arxiv: MagicMock, by_doi: MagicMock, by_title: MagicMock
    ) -> None:
        paper = _paper(
            "The Tolman-Eichenbaum Machine: Unifying Space and Relational Memory",
            ["James C.R. Whittington"],
            2020,
        )
        by_title.return_value = [paper]
        query = _query(
            'Whittington et al. (2020), "The Tolman-Eichenbaum Machine", Cell.',
            "The Tolman-Eichenbaum Machine",
            ["Whittington"],
            2020,
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        by_arxiv.assert_not_called()  # no arXiv ID in the citation
        assert candidate is not None
        assert candidate.paper_id == paper.id
        assert candidate.outcome == "in_library"
        assert candidate.confident is True

    @patch(f"{_LIB}.library_by_title", return_value=[])
    @patch(f"{_LIB}.library_by_doi", return_value=None)
    @patch(f"{_LIB}.library_by_arxiv_id", return_value=None)
    def test_no_library_match_returns_none(
        self, by_arxiv: MagicMock, by_doi: MagicMock, by_title: MagicMock
    ) -> None:
        query = _query("Anderson (1974), Retrieval", "Retrieval", ["Anderson"], 1974)

        assert CitationResolver().resolve(query, MagicMock()) is None
