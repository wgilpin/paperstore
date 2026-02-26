"""Gemini LLM service for extracting paper metadata from PDF bytes."""

import io
import json
import logging
import os

import pdfplumber
from google import genai

from src.schemas.paper import ExtractedMetadata

logger = logging.getLogger(__name__)

_MAX_PAGES = 2


def _page_text(page: pdfplumber.page.Page) -> str:  # type: ignore[name-defined]
    """Extract text from a pdfplumber page using word-level joining to preserve spaces."""
    words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
    if not words:
        return ""
    lines: list[str] = []
    current_line: list[str] = []
    prev_bottom: float = words[0]["bottom"]
    for word in words:
        if abs(word["bottom"] - prev_bottom) > 5:
            lines.append(" ".join(current_line))
            current_line = []
        current_line.append(word["text"])
        prev_bottom = word["bottom"]
    if current_line:
        lines.append(" ".join(current_line))
    return "\n".join(lines)


def _extract_first_pages_text(pdf_bytes: bytes, max_pages: int) -> tuple[str, int]:
    """Return text of the first *max_pages* pages and the actual page count sent."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages[:max_pages]
        text = "\n\n".join(_page_text(p) for p in pages)
        return text, len(pages)


_PROMPT = (
    "You are a research paper metadata extractor. "
    "The following is text extracted from the first pages of a research paper PDF. "
    "Return ONLY a valid JSON object with these keys:\n"
    '  "title": string or null,\n'
    '  "authors": array of strings (full names),\n'
    '  "date": string in YYYY or YYYY-MM or YYYY-MM-DD format, or null,\n'
    '  "abstract": string or null\n'
    "Return nothing except the JSON object — no markdown, no explanation."
)


class GeminiService:
    """Calls the Gemini API to extract metadata from a PDF."""

    def extract_metadata(self, pdf_bytes: bytes) -> ExtractedMetadata:
        """Send *pdf_bytes* to Gemini and return structured metadata.

        Raises ValueError if required env vars are missing.
        Returns an all-None ExtractedMetadata on LLM parse failure.
        """
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        model_name = os.environ.get("GEMINI_PDF_MODEL", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        if not model_name:
            raise ValueError("GEMINI_PDF_MODEL environment variable is not set")

        text, pages_sent = _extract_first_pages_text(pdf_bytes, _MAX_PAGES)
        logger.info("sending %d page(s) (%d chars) to Gemini model %s", pages_sent, len(text), model_name)

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=[_PROMPT, text],
        )

        logger.info("Gemini response received (%d chars)", len(response.text))
        raw = response.text.strip()
        # Strip optional markdown code fence
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        try:
            data: object = json.loads(raw)
        except json.JSONDecodeError:
            return ExtractedMetadata(title=None, authors=[], date=None, abstract=None)

        if not isinstance(data, dict):
            return ExtractedMetadata(title=None, authors=[], date=None, abstract=None)

        title = data.get("title")
        authors_raw = data.get("authors", [])
        date = data.get("date")
        abstract = data.get("abstract")

        return ExtractedMetadata(
            title=str(title) if title else None,
            authors=[str(a) for a in authors_raw] if isinstance(authors_raw, list) else [],
            date=str(date) if date else None,
            abstract=str(abstract) if abstract else None,
        )
