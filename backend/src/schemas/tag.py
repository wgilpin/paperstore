"""Tag schemas."""

from pydantic import BaseModel


class TagWithCount(BaseModel):
    name: str
    count: int


class TagMergeRequest(BaseModel):
    into: str


class TagRenameRequest(BaseModel):
    name: str
