"""Pydantic schemas for reading lists."""

import uuid
from datetime import datetime
from typing import Literal

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


class LookupStatus(BaseModel):
    """Lookup progress for one list, for the list page's controls."""

    running: bool
    # Items whose import is in progress.
    importing: int
    looked_up: int
    unlooked: int
    pending_review: int


# How a lookup ended for one item.
Outcome = Literal["in_library", "free_pdf", "record_only", "not_found"]


class Candidate(BaseModel):
    """The best match a lookup found for one list item."""

    # "manual" when Will gave the URL himself.
    source: Literal["library", "arxiv", "openalex", "manual"]
    title: str
    authors: list[str]
    year: int | None
    arxiv_id: str | None = None
    doi: str | None = None
    pdf_url: str | None = None
    landing_url: str | None = None
    # Set when the match is a paper already in the library.
    paper_id: uuid.UUID | None = None
    # True when the title and the year or an author agree; only confident matches
    # are pre-selected on the review page.
    confident: bool
    outcome: Outcome
