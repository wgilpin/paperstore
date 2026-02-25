"""Notes service — upsert note content for a paper."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models.note import Note
from src.models.paper import Paper
from src.schemas.note import NoteResponse


class NotFoundError(Exception):
    """Raised when the requested paper does not exist."""


class NotesService:
    def upsert(self, paper_id: uuid.UUID, content: str, db: Session) -> NoteResponse:
        """Update the note for *paper_id*; raise NotFoundError if paper absent."""
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper is None:
            raise NotFoundError(f"Paper {paper_id} not found")

        note = db.query(Note).filter(Note.paper_id == paper_id).first()
        assert note is not None  # Note is always created with the Paper

        note.content = content
        note.updated_at = datetime.now(tz=UTC).replace(tzinfo=None)
        db.commit()
        db.refresh(note)

        return NoteResponse(content=note.content, updated_at=note.updated_at)
