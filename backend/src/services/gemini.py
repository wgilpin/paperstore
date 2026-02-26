"""Gemini LLM service for extracting paper metadata from PDF bytes."""

import io
import json
import os

from google import genai

from src.schemas.paper import ExtractedMetadata

_PROMPT = (
    "You are a research paper metadata extractor. "
    "Read the attached PDF and return ONLY a valid JSON object with these keys:\n"
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

        client = genai.Client(api_key=api_key)

        uploaded = client.files.upload(
            file=io.BytesIO(pdf_bytes),
            config={"mime_type": "application/pdf"},
        )

        response = client.models.generate_content(
            model=model_name,
            contents=[uploaded, _PROMPT],
        )

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
