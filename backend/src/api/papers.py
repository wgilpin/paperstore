"""Papers API router."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.note import Note
from src.models.paper import Paper
from src.schemas.note import NoteResponse, NoteUpdateRequest
from src.schemas.paper import (
    NoteSchema,
    PaperDetail,
    PaperSubmitRequest,
    PaperSummary,
)
from src.services.drive import DriveUploadError
from src.services.ingestion import DuplicateError, IngestionService
from src.services.search import SearchService

router = APIRouter()


def _to_paper_detail(paper: Paper, note: Note) -> PaperDetail:
    return PaperDetail(
        id=paper.id,
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=paper.authors,
        published_date=paper.published_date,
        abstract=paper.abstract,
        submission_url=paper.submission_url,
        drive_view_url=paper.drive_view_url,
        added_at=paper.added_at,
        note=NoteSchema(content=note.content, updated_at=note.updated_at),
    )


@router.post("", status_code=201)
def submit_paper(
    body: PaperSubmitRequest,
    db: Session = Depends(get_session),
) -> dict[str, PaperDetail]:
    svc = IngestionService()
    try:
        paper = svc.ingest(body.url, db)
    except DuplicateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DriveUploadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    note = db.query(Note).filter(Note.paper_id == paper.id).first()
    assert note is not None
    return {"paper": _to_paper_detail(paper, note)}


@router.get("", response_model=None)
def list_papers(
    q: str | None = Query(default=None),
    sort: Literal["added_at", "title"] = Query(default="added_at"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_session),
) -> dict[str, list[PaperSummary] | int]:
    papers, total = SearchService().search(q, db, sort=sort, page=page)
    summaries = [
        PaperSummary(
            id=p.id,
            arxiv_id=p.arxiv_id,
            title=p.title,
            authors=p.authors,
            published_date=p.published_date,
            added_at=p.added_at,
        )
        for p in papers
    ]
    return {"papers": summaries, "total": total}


@router.get("/{paper_id}")
def get_paper(
    paper_id: str,
    db: Session = Depends(get_session),
) -> dict[str, PaperDetail]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    note = db.query(Note).filter(Note.paper_id == paper.id).first()
    assert note is not None
    return {"paper": _to_paper_detail(paper, note)}


@router.delete("/{paper_id}", status_code=204)
def delete_paper(
    paper_id: str,
    db: Session = Depends(get_session),
) -> None:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    drive_file_id = paper.drive_file_id
    db.query(Note).filter(Note.paper_id == paper.id).delete()
    db.delete(paper)
    db.commit()
    from src.services.drive import DriveService
    DriveService().delete(drive_file_id)


@router.patch("/{paper_id}/note")
def update_note(
    paper_id: str,
    body: NoteUpdateRequest,
    db: Session = Depends(get_session),
) -> dict[str, NoteResponse]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    note = db.query(Note).filter(Note.paper_id == paper.id).first()
    assert note is not None
    note.content = body.content
    db.commit()
    db.refresh(note)
    return {"note": NoteResponse(content=note.content, updated_at=note.updated_at)}


@router.get("/{paper_id}/pdf")
def get_pdf(
    paper_id: str,
    db: Session = Depends(get_session),
) -> RedirectResponse:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return RedirectResponse(url=paper.drive_view_url, status_code=302)
