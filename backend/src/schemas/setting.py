"""Pydantic schemas for Setting endpoints."""

from pydantic import BaseModel


class SettingsSchema(BaseModel):
    about_me: str | None = None
