"""PDF downloader and metadata extractor."""

import io

import httpx
import pdfplumber

from src.services.types import PaperMetadata

_PDF_MAGIC = b"%PDF"


class PdfParser:
    """Download a PDF from a URL and extract best-effort metadata."""

    def download_and_extract(self, url: str) -> tuple[PaperMetadata, bytes]:
        """Download the PDF at *url* and return (metadata, pdf_bytes).

        Raises:
            httpx.HTTPStatusError: if the HTTP request fails.
            ValueError: if the response is not a PDF.
        """
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type and not response.content.startswith(_PDF_MAGIC):
            raise ValueError(f"URL is not a PDF (content-type: {content_type!r})")

        pdf_bytes = response.content
        metadata = self._extract_metadata(pdf_bytes)
        return metadata, pdf_bytes

    def _extract_metadata(self, pdf_bytes: bytes) -> PaperMetadata:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                raw = pdf.metadata or {}
        except Exception:
            raw = {}

        title: str | None = raw.get("Title") or None
        author_raw: str | None = raw.get("Author") or None
        authors = [a.strip() for a in author_raw.split(";")] if author_raw else []

        return PaperMetadata(
            title=title,
            authors=authors,
            published_date=None,  # PDF metadata rarely has a useful date
            abstract=None,
            arxiv_id=None,
        )
