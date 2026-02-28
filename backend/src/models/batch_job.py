"""BatchJob ORM model — tracks a Gemini batch metadata extraction job."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gemini_job_name: Mapped[str] = mapped_column(Text, nullable=False)
    # state: pending | running | succeeded | failed | applied
    state: Mapped[str] = mapped_column(Text, nullable=False)
    paper_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
