"""Reading list ORM models: a pasted list and its ordered items."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, ForeignKey, String, Text, false, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base
from src.schemas.reading_list import Candidate

if TYPE_CHECKING:
    from src.models.paper import Paper


class ReadingList(Base):
    __tablename__ = "reading_lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # The pasted text, kept so the list can be parsed again.
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    # True when the last parse found no items; the page then offers "parse again".
    parse_failed: Mapped[bool] = mapped_column(nullable=False, server_default=false())
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
    # Tick state for a text or link item; a paper item uses papers.read_at instead.
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Set when the item is linked to a library paper.
    paper_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("papers.id", ondelete="SET NULL"), nullable=True
    )
    # A plain link for the item (a DOI link, or a URL kept after a failed import).
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # new | review | importing | done | import_failed
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="new")
    # How the last lookup ended (see schemas.reading_list.Outcome); null before lookup.
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The lookup's best match as Candidate JSON; cleared once the review is applied.
    candidate_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    reading_list: Mapped[ReadingList] = relationship("ReadingList", back_populates="items")
    paper: Mapped[Paper | None] = relationship("Paper")

    @property
    def candidate(self) -> Candidate | None:
        """The stored lookup match, if any."""
        return Candidate.model_validate_json(self.candidate_json) if self.candidate_json else None

    @candidate.setter
    def candidate(self, value: Candidate | None) -> None:
        self.candidate_json = value.model_dump_json() if value else None

    @property
    def is_read(self) -> bool:
        """A paper item is read when its paper is; any other item uses its own tick."""
        if self.paper is not None:
            return self.paper.read_at is not None
        return self.read_at is not None
