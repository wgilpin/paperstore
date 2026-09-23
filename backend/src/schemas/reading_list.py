"""Pydantic schemas for reading lists."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ParsedItem(BaseModel):
    """One entry of a reading list, as the LLM parser extracts it."""

    citation: str
    title: str
    authors: list[str]
    year: int | None
    note: str | None


class ListProgress(BaseModel):
    """How many items of a reading list are ticked."""

    read: int
    total: int


class ListSummary(BaseModel):
    """One row of the lists index."""

    id: uuid.UUID
    name: str
    created_at: datetime
    progress: ListProgress
