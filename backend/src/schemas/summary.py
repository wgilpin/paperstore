"""Pydantic schemas for Summary endpoints."""

from pydantic import BaseModel


class SummaryGenerateRequest(BaseModel):
    instructions: str | None = None


class SummaryResponse(BaseModel):
    summary_text: str | None
    has_image: bool
