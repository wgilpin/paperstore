"""Paper ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, FetchedValue, Index, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base

if TYPE_CHECKING:
    from src.models.tag import Tag


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    arxiv_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    published_date: Mapped[date | None] = mapped_column(nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    submission_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    drive_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    drive_view_url: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    # search_vector is a GENERATED ALWAYS column — created by raw DDL in create_tables().
    # server_default=FetchedValue() tells SQLAlchemy the DB owns this column;
    # never include in INSERT/UPDATE.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, nullable=True, server_default=FetchedValue()
    )

    tags: Mapped[list[Tag]] = relationship("Tag", secondary="paper_tags", back_populates="papers")

    __table_args__ = (Index("idx_papers_search", "search_vector", postgresql_using="gin"),)
