"""Reading list parser — splits pasted LLM reading-list text into ordered items via Gemini."""

import logging
import os

from google import genai
from google.genai import types
from pydantic import TypeAdapter

from src.schemas.reading_list import ParsedItem

logger = logging.getLogger(__name__)

_PROMPT = (
    "The text below is a reading list, usually written by an LLM. Extract every item "
    "the reader is told to read (papers, books, articles, software, anything else), in the "
    "order they appear. Ignore section headings and introductions.\n"
    "For each item return:\n"
    "- citation: the item's line of text, as written, without its commentary\n"
    "- title: the title of the work (for software, its name)\n"
    "- authors: author surnames or full names, as given; [] if none\n"
    "- year: the publication year as an integer, or null\n"
    "- note: the commentary the list gives for this item (why to read it, what to skip), "
    "or null\n"
    "Do not invent details that are not in the text.\n\n"
    "Reading list:\n"
)

_ITEMS = TypeAdapter(list[ParsedItem])


class ReadingListParser:
    """Calls Gemini to split a pasted reading list into ParsedItems."""

    def parse(self, text: str) -> list[ParsedItem]:
        """Return the items of *text* in list order.

        Raises ValueError if GEMINI_API_KEY or GEMINI_PDF_MODEL is not set.
        """
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        model_name = os.environ.get("GEMINI_PDF_MODEL", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        if not model_name:
            raise ValueError("GEMINI_PDF_MODEL environment variable is not set")

        client = genai.Client(api_key=api_key)
        # Structured output: Gemini returns a JSON array matching ParsedItem.
        response = client.models.generate_content(
            model=model_name,
            contents=_PROMPT + text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[ParsedItem],
            ),
        )
        items = _ITEMS.validate_json(response.text or "[]")
        logger.info("parsed reading list into %d item(s)", len(items))
        return items
