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
        metadata = self.extract_metadata(pdf_bytes)
        return metadata, pdf_bytes

    def extract_metadata(self, pdf_bytes: bytes) -> PaperMetadata:
        raw: dict[str, object] = {}
        first_page_text: str = ""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                raw = pdf.metadata or {}
                if pdf.pages:
                    first_page_text = pdf.pages[0].extract_text() or ""
        except Exception:
            pass

        title: str | None = raw.get("Title") or None  # type: ignore[assignment]
        if not title:
            # Fall back to the first non-empty line of the first page.
            for line in first_page_text.splitlines():
                stripped = line.strip()
                if stripped:
                    title = stripped
                    break

        author_raw: str | None = raw.get("Author") or None  # type: ignore[assignment]
        authors = [a.strip() for a in author_raw.split(";")] if author_raw else []

        return PaperMetadata(
            title=title,
            authors=authors,
            published_date=None,  # PDF metadata rarely has a useful date
            abstract=None,
            arxiv_id=None,
        )
