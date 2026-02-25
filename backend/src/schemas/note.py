"""Pydantic schemas for Note endpoints."""

from datetime import datetime

from pydantic import BaseModel


class NoteUpdateRequest(BaseModel):
    content: str


class NoteResponse(BaseModel):
    content: str
    updated_at: datetime
