"""Pydantic schemas for reading lists."""

from pydantic import BaseModel


class ParsedItem(BaseModel):
    """One entry of a reading list, as the LLM parser extracts it."""

    citation: str
    title: str
    authors: list[str]
    year: int | None
    note: str | None
