"""Unit tests for CitationResolver and its matching rules."""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from src.models.paper import Paper
from src.schemas.reading_list import ParsedItem
from src.services.citation_resolver import ArxivHit, CitationResolver, is_confident
from src.services.openalex_client import OpenAlexWork


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

    @patch(f"{_LIB}.arxiv_search", return_value=[])
    @patch(f"{_LIB}.openalex_search", return_value=[])
    @patch(f"{_LIB}.library_by_title", return_value=[])
    @patch(f"{_LIB}.library_by_doi", return_value=None)
    @patch(f"{_LIB}.library_by_arxiv_id", return_value=None)
    def test_no_library_match_returns_none(
        self, by_arxiv: MagicMock, by_doi: MagicMock, by_title: MagicMock, *_: MagicMock
    ) -> None:
        query = _query("Anderson (1974), Retrieval", "Retrieval", ["Anderson"], 1974)

        assert CitationResolver().resolve(query, MagicMock()) is None


def _no_library(fn: object) -> object:
    """Decorate a test so every library lookup misses."""
    for name, value in (
        ("library_by_title", []),
        ("library_by_doi", None),
        ("library_by_arxiv_id", None),
    ):
        fn = patch(f"{_LIB}.{name}", return_value=value)(fn)  # type: ignore[assignment]
    return fn


def _work(
    title: str,
    year: int,
    authors: list[str],
    *,
    doi: str | None = None,
    pdf_urls: list[str] | None = None,
    arxiv_id: str | None = None,
    type_: str = "article",
) -> OpenAlexWork:
    return OpenAlexWork(
        title=title,
        year=year,
        authors=authors,
        doi=doi,
        type=type_,
        pdf_urls=pdf_urls or [],
        arxiv_id=arxiv_id,
        landing_url=f"https://doi.org/{doi}" if doi else None,
    )


class TestOutsideLookup:
    @_no_library
    @patch(f"{_LIB}.openalex_search")
    @patch(f"{_LIB}.arxiv_record")
    def test_arxiv_id_in_citation_is_used_first(
        self, record: MagicMock, openalex: MagicMock, *_: MagicMock
    ) -> None:
        record.return_value = ArxivHit(
            arxiv_id="2203.08913", title="Memorizing Transformers", authors=["Yuhuai Wu"], year=2022
        )
        query = _query(
            'Wu et al. (2022), "Memorizing Transformers", arXiv 2203.08913',
            "Memorizing Transformers",
            ["Wu"],
            2022,
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        record.assert_called_once_with("2203.08913")
        openalex.assert_not_called()
        assert candidate is not None
        assert candidate.source == "arxiv"
        assert candidate.outcome == "free_pdf"
        assert candidate.pdf_url == "https://arxiv.org/pdf/2203.08913"
        assert candidate.confident is True

    @_no_library
    @patch(f"{_LIB}.pdf_check", return_value=True)
    @patch(f"{_LIB}.openalex_search")
    def test_openalex_used_when_no_arxiv_id(
        self, openalex: MagicMock, pdf_check: MagicMock, *_: MagicMock
    ) -> None:
        openalex.return_value = [
            _work(
                "Intrinsic Motivation Systems for Autonomous Mental Development",
                2007,
                ["Pierre-Yves Oudeyer"],
                doi="10.1109/tevc.2006.890271",
                pdf_urls=["http://cogprints.org/5473/1/ims.pdf"],
            )
        ]
        query = _query(
            "Oudeyer, Kaplan & Hafner (2007). Intrinsic motivation systems.",
            "Intrinsic motivation systems for autonomous mental development",
            ["Oudeyer", "Kaplan", "Hafner"],
            2007,
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        assert candidate is not None
        assert candidate.source == "openalex"
        assert candidate.doi == "10.1109/tevc.2006.890271"
        assert candidate.confident is True

    @_no_library
    @patch(f"{_LIB}.pdf_check", return_value=True)
    @patch(f"{_LIB}.openalex_search")
    def test_outcome_free_pdf(
        self, openalex: MagicMock, pdf_check: MagicMock, *_: MagicMock
    ) -> None:
        openalex.return_value = [
            _work("Dickinson paper", 1994, ["Dickinson"], pdf_urls=["https://x.org/a.pdf"])
        ]

        candidate = CitationResolver().resolve(
            _query("Dickinson (1994)", "Dickinson paper", ["Dickinson"], 1994), MagicMock()
        )

        assert candidate is not None
        assert candidate.outcome == "free_pdf"
        assert candidate.pdf_url == "https://x.org/a.pdf"

    @_no_library
    @patch(f"{_LIB}.pdf_check", return_value=False)
    @patch(f"{_LIB}.openalex_search")
    def test_outcome_record_only(
        self, openalex: MagicMock, pdf_check: MagicMock, *_: MagicMock
    ) -> None:
        openalex.return_value = [
            _work(
                "Computational principles of synaptic memory consolidation",
                2016,
                ["Marcus K. Benna"],
                doi="10.1038/nn.4401",
                pdf_urls=["https://www.nature.com/articles/nn.4401.pdf"],
            )
        ]
        query = _query(
            "Benna and Fusi (2016)",
            "Computational principles of synaptic memory consolidation",
            ["Benna", "Fusi"],
            2016,
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        assert candidate is not None
        assert candidate.outcome == "record_only"
        assert candidate.pdf_url is None
        assert candidate.landing_url == "https://doi.org/10.1038/nn.4401"

    @_no_library
    @patch(f"{_LIB}.arxiv_search")
    @patch(f"{_LIB}.openalex_search", return_value=[])
    def test_arxiv_search_used_when_openalex_misses(
        self, openalex: MagicMock, search: MagicMock, *_: MagicMock
    ) -> None:
        search.return_value = [
            ArxivHit(
                arxiv_id="2507.06211",
                title="Modern Methods in Associative Memory",
                authors=["Dmitry Krotov"],
                year=2025,
            )
        ]
        query = _query(
            "Krotov et al. (2025)", "Modern methods in associative memory", ["Krotov"], 2025
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        assert candidate is not None
        assert candidate.source == "arxiv"
        assert candidate.arxiv_id == "2507.06211"
        assert candidate.outcome == "free_pdf"

    @_no_library
    @patch(f"{_LIB}.arxiv_search", return_value=[])
    @patch(f"{_LIB}.openalex_search")
    def test_outcome_not_found(self, openalex: MagicMock, search: MagicMock, *_: MagicMock) -> None:
        openalex.return_value = [_work("Something else entirely", 2011, ["Nobody"])]

        candidate = CitationResolver().resolve(
            _query("Milinkovic & Aru", "unfolding argument rapid plasticity", ["Milinkovic"], None),
            MagicMock(),
        )

        assert candidate is None

    @_no_library
    @patch(f"{_LIB}.arxiv_search", return_value=[])
    @patch(f"{_LIB}.openalex_search")
    def test_book_review_is_rejected(
        self, openalex: MagicMock, search: MagicMock, *_: MagicMock
    ) -> None:
        openalex.return_value = [
            _work(
                "The Hidden Spring, a Journey to the Source of Consciousness",
                2022,
                ["Some Reviewer"],
                pdf_urls=["http://www.jkapa.org/review.pdf"],
                type_="book-review",
            )
        ]
        query = _query(
            "Solms (2021). The Hidden Spring.",
            "The Hidden Spring: A Journey to the Source of Consciousness",
            ["Solms"],
            2021,
        )

        assert CitationResolver().resolve(query, MagicMock()) is None

    @patch(f"{_LIB}.library_by_title", return_value=[])
    @patch(f"{_LIB}.library_by_doi")
    @patch(f"{_LIB}.library_by_arxiv_id", return_value=None)
    @patch(f"{_LIB}.openalex_search")
    def test_outside_match_already_in_library_by_doi(
        self, openalex: MagicMock, by_arxiv: MagicMock, by_doi: MagicMock, by_title: MagicMock
    ) -> None:
        paper = _paper("Motivational control of goal-directed action", ["A. Dickinson"], 1994)
        by_doi.return_value = paper
        openalex.return_value = [
            _work(
                "Motivational control of goal-directed action",
                1994,
                ["A. Dickinson"],
                doi="10.3758/bf03199951",
            )
        ]
        query = _query(
            "Dickinson & Balleine (1994)",
            "Motivational control of goal-directed action",
            ["Dickinson", "Balleine"],
            1994,
        )

        candidate = CitationResolver().resolve(query, MagicMock())

        assert candidate is not None
        assert candidate.outcome == "in_library"
        assert candidate.paper_id == paper.id


class TestConfidence:
    def test_confident_needs_year_or_author(self) -> None:
        query = _query(
            "Singh, Barto & Chentanez (2004)",
            "Intrinsically motivated reinforcement learning",
            ["Singh", "Barto", "Chentanez"],
            2004,
        )

        assert is_confident(
            query, "Intrinsically Motivated Reinforcement Learning", ["Satinder Singh"], 2005
        )
        assert not is_confident(
            query, "Intrinsically Motivated Reinforcement Learning", ["Someone Else"], 2012
        )

    def test_title_only_match_is_weak(self) -> None:
        query = _query(
            "Singh, Barto & Chentanez (2004)",
            "Intrinsically motivated reinforcement learning",
            ["Singh", "Barto", "Chentanez"],
            2004,
        )

        assert not is_confident(
            query,
            "Intrinsically-Motivated Reinforcement Learning: A Brief Introduction",
            ["Mingqi Yuan"],
            2022,
        )
