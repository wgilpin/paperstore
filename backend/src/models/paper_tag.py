"""paper_tags association table."""

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from src.db import Base

paper_tags = Table(
    "paper_tags",
    Base.metadata,
    Column(
        "paper_id", UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    ),
)
