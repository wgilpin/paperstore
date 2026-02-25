"""Shared typed return types for backend services."""

from datetime import date
from typing import TypedDict


class PaperMetadata(TypedDict):
    title: str | None
    authors: list[str]
    published_date: date | None
    abstract: str | None
    arxiv_id: str | None


class DriveUploadResult(TypedDict):
    file_id: str
    view_url: str
