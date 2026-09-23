"""Reading list ORM models: a pasted list and its ordered items."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class ReadingList(Base):
    __tablename__ = "reading_lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # The pasted text, kept so the list can be parsed again.
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    items: Mapped[list[ReadingListItem]] = relationship(
        "ReadingListItem",
        back_populates="reading_list",
        order_by="ReadingListItem.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ReadingListItem(Base):
    __tablename__ = "reading_list_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reading_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(nullable=False)
    citation: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    year: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tick state for this item; null means unread.
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)

    reading_list: Mapped[ReadingList] = relationship("ReadingList", back_populates="items")
