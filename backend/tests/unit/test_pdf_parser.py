"""Unit tests for PdfParser."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.pdf_parser import PdfParser

_PDF_MAGIC = b"%PDF-1.4 fake content"


def _make_pdfplumber_mock(
    metadata: dict[str, object],
    first_page_text: str = "",
) -> MagicMock:
    """Return a mock that works as a context manager yielding a pdf with given metadata."""
    page = MagicMock()
    page.extract_text.return_value = first_page_text
    inner = MagicMock()
    inner.metadata = metadata
    inner.pages = [page]
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=inner)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestPdfParserDownloadAndExtract:
    def test_returns_metadata_and_bytes_from_mocked_response(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = _PDF_MAGIC

        mock_ctx = _make_pdfplumber_mock(
            {
                "Title": "My Paper",
                "Author": "Jane Doe",
            }
        )

        with (
            patch("src.services.pdf_parser.httpx.get", return_value=mock_response),
            patch("src.services.pdf_parser.pdfplumber.open", return_value=mock_ctx),
        ):
            parser = PdfParser()
            metadata, pdf_bytes = parser.download_and_extract("https://example.com/paper.pdf")

        assert pdf_bytes == _PDF_MAGIC
        assert metadata["title"] == "My Paper"
        assert metadata["authors"] == ["Jane Doe"]

    def test_raises_on_non_pdf_content_type(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html></html>"  # no PDF magic bytes

        with patch("src.services.pdf_parser.httpx.get", return_value=mock_response):
            parser = PdfParser()
            with pytest.raises(ValueError, match="not a PDF"):
                parser.download_and_extract("https://example.com/page")

    def test_raises_on_http_error(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404")

        with patch("src.services.pdf_parser.httpx.get", return_value=mock_response):
            parser = PdfParser()
            with pytest.raises(Exception, match="404"):
                parser.download_and_extract("https://example.com/missing.pdf")

    def test_falls_back_to_first_page_text_when_no_metadata_title(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = _PDF_MAGIC

        mock_ctx = _make_pdfplumber_mock({}, first_page_text="Attention Is All You Need\nAuthors...")

        with (
            patch("src.services.pdf_parser.httpx.get", return_value=mock_response),
            patch("src.services.pdf_parser.pdfplumber.open", return_value=mock_ctx),
        ):
            parser = PdfParser()
            metadata, _ = parser.download_and_extract("https://example.com/paper.pdf")

        assert metadata["title"] == "Attention Is All You Need"
        assert metadata["authors"] == []
        assert metadata["abstract"] is None

    def test_returns_none_title_when_no_metadata_and_no_page_text(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = _PDF_MAGIC

        mock_ctx = _make_pdfplumber_mock({}, first_page_text="")

        with (
            patch("src.services.pdf_parser.httpx.get", return_value=mock_response),
            patch("src.services.pdf_parser.pdfplumber.open", return_value=mock_ctx),
        ):
            parser = PdfParser()
            metadata, _ = parser.download_and_extract("https://example.com/paper.pdf")

        assert metadata["title"] is None
        assert metadata["authors"] == []
