"""Pydantic schemas for Paper endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class PaperSubmitRequest(BaseModel):
    url: str = Field(..., description="arXiv page URL or direct PDF URL")


class NoteSchema(BaseModel):
    content: str
    updated_at: datetime


class PaperSummary(BaseModel):
    id: uuid.UUID
    arxiv_id: str | None
    title: str
    authors: list[str]
    published_date: date | None
    added_at: datetime

    model_config = {"from_attributes": True}


class PaperDetail(BaseModel):
    id: uuid.UUID
    arxiv_id: str | None
    title: str
    authors: list[str]
    published_date: date | None
    abstract: str | None
    submission_url: str
    drive_view_url: str
    added_at: datetime
    note: NoteSchema

    model_config = {"from_attributes": True}


class PaperUpdateRequest(BaseModel):
    title: str
    authors: list[str]
    published_date: date | None
    abstract: str | None


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
