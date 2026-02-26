"""Pydantic schemas for Paper endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


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
    tags: list[str]

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
    tags: list[str]

    model_config = {"from_attributes": True}


class PaperUpdateRequest(BaseModel):
    title: str
    authors: list[str]
    published_date: date | None
    abstract: str | None
    tags: list[str] = Field(default_factory=list)

    @field_validator("published_date", mode="before")
    @classmethod
    def parse_partial_date(cls, v: object) -> date | None:
        if v is None or v == "":
            return None
        if isinstance(v, date):
            return v
        # Normalise unicode dashes to ASCII hyphen before splitting
        s = str(v).strip().replace("\u2013", "-").replace("\u2014", "-")
        parts = s.split("-")
        try:
            if len(parts) == 1:
                return date(int(parts[0]), 1, 1)
            if len(parts) == 2:
                a, b = int(parts[0]), int(parts[1])
                if a > 31:  # YYYY-MM
                    return date(a, b, 1)
                else:  # MM-YYYY
                    return date(b, a, 1)
            # 3-part: disambiguate YYYY-MM-DD vs DD-MM-YYYY vs MM-DD-YYYY.
            a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
            if a > 31:  # first part is a year → YYYY-MM-DD
                return date(a, b, c)
            elif c > 31:  # last part is a year
                if a > 12:  # first part can't be a month → DD-MM-YYYY
                    return date(c, b, a)
                else:  # ambiguous; assume DD-MM-YYYY
                    return date(c, b, a)
            else:
                raise ValueError(f"Unrecognised date format: {v!r}")
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Unrecognised date format: {v!r}") from exc


class ExtractedMetadata(BaseModel):
    title: str | None
    authors: list[str]
    date: str | None
    abstract: str | None


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
