"""Unit tests for ArxivClient."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.arxiv_client import ArxivClient


def _make_arxiv_result(
    *,
    title: str = "Test Paper",
    authors: list[str] | None = None,
    published: str = "2023-01-01",
    summary: str = "Abstract text.",
    entry_id: str = "http://arxiv.org/abs/2301.00001v1",
) -> MagicMock:
    result = MagicMock()
    result.title = title
    author_mocks = []
    for a in authors or ["Alice", "Bob"]:
        m = MagicMock()
        m.name = a
        author_mocks.append(m)
    result.authors = author_mocks
    result.published = MagicMock()
    result.published.date.return_value = published
    result.summary = summary
    result.entry_id = entry_id
    return result


class TestArxivClientFetch:
    def test_returns_paper_metadata_with_correct_fields(self) -> None:
        mock_result = _make_arxiv_result()
        with patch("src.services.arxiv_client.arxiv.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.results.return_value = iter([mock_result])

            client = ArxivClient()
            metadata = client.fetch("2301.00001")

        assert isinstance(metadata, dict)
        assert metadata["title"] == "Test Paper"
        assert metadata["authors"] == ["Alice", "Bob"]
        assert metadata["abstract"] == "Abstract text."
        assert metadata["arxiv_id"] == "2301.00001"

    def test_raises_on_empty_results(self) -> None:
        with patch("src.services.arxiv_client.arxiv.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.results.return_value = iter([])

            client = ArxivClient()
            with pytest.raises(ValueError, match="not found"):
                client.fetch("9999.99999")

    @pytest.mark.parametrize(
        "url,expected_id",
        [
            ("https://arxiv.org/abs/2301.00001", "2301.00001"),
            ("https://arxiv.org/pdf/2301.00001", "2301.00001"),
            ("https://arxiv.org/abs/2301.00001v2", "2301.00001"),
            ("2301.00001", "2301.00001"),
            ("https://arxiv.org/abs/hep-th/9901001", "hep-th/9901001"),
        ],
    )
    def test_normalises_arxiv_id_forms(self, url: str, expected_id: str) -> None:
        from src.services.arxiv_client import extract_arxiv_id

        assert extract_arxiv_id(url) == expected_id

    def test_raises_on_non_arxiv_url(self) -> None:
        from src.services.arxiv_client import extract_arxiv_id

        with pytest.raises(ValueError, match="Cannot extract"):
            extract_arxiv_id("https://example.com/paper.pdf")
