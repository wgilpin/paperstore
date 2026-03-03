"""Tag schemas."""

from pydantic import BaseModel


class TagWithCount(BaseModel):
    name: str
    count: int
