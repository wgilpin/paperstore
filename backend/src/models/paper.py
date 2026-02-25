"""Paper ORM model."""

import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, Index, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


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
    added_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    # search_vector is a GENERATED ALWAYS column — created by raw DDL in create_tables().
    # Declared here so SQLAlchemy knows the column exists for query expressions.
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (Index("idx_papers_search", "search_vector", postgresql_using="gin"),)
