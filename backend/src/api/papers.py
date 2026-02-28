"""Papers API router."""

import logging
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.note import Note
from src.models.paper import Paper
from src.models.tag import Tag
from src.schemas.note import NoteResponse, NoteUpdateRequest
from src.schemas.paper import (
    ExtractedMetadata,
    NoteSchema,
    PaperDetail,
    PaperSubmitRequest,
    PaperSummary,
    PaperUpdateRequest,
)
from src.services.drive import DriveUploadError
from src.services.gemini import GeminiService
from src.services.ingestion import DuplicateError, IngestionService
from src.services.search import SearchService

logger = logging.getLogger(__name__)

router = APIRouter()


def _enrich_paper_async(paper_id: str, drive_file_id: str) -> None:
    """Spawn a daemon thread to extract metadata and apply it to empty fields."""
    def _run() -> None:
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        from src.db import _get_engine
        db = _sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)()
        try:
            from src.services.drive import DriveService
            pdf_bytes = DriveService().download(drive_file_id)
            metadata = GeminiService().extract_metadata(pdf_bytes)
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if paper is None:
                return
            if not paper.abstract and metadata.abstract:
                paper.abstract = metadata.abstract
            if not paper.authors and metadata.authors:
                paper.authors = metadata.authors
            if paper.published_date is None and metadata.date:
                try:
                    parsed = PaperUpdateRequest.model_validate(
                        {
                            "title": paper.title,
                            "authors": paper.authors,
                            "published_date": metadata.date,
                            "abstract": paper.abstract,
                            "tags": [],
                        }
                    )
                    paper.published_date = parsed.published_date
                except Exception:
                    pass
            if not paper.title and metadata.title:
                paper.title = metadata.title
            db.commit()
        except Exception:
            logger.exception("Background metadata extraction failed for paper %s", paper_id)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()


def _tag_names(paper: Paper) -> list[str]:
    return sorted(t.name for t in (paper.tags or []))


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
        tags=_tag_names(paper),
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

    if not (paper.title and paper.authors and paper.published_date):
        _enrich_paper_async(str(paper.id), paper.drive_file_id)

    note = db.query(Note).filter(Note.paper_id == paper.id).first()
    assert note is not None
    return {"paper": _to_paper_detail(paper, note)}


@router.get("", response_model=None)
def list_papers(
    q: str | None = Query(default=None),
    sort: Literal["added_at", "title", "published_date"] = Query(default="added_at"),
    page: int = Query(default=1, ge=1),
    tag: str | None = Query(default=None),
    db: Session = Depends(get_session),
) -> dict[str, list[PaperSummary] | int]:
    papers, total = SearchService().search(q, db, sort=sort, page=page, tag=tag)
    summaries = [
        PaperSummary(
            id=p.id,
            arxiv_id=p.arxiv_id,
            title=p.title,
            authors=p.authors,
            published_date=p.published_date,
            added_at=p.added_at,
            tags=_tag_names(p),
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


def _sync_tags(paper: Paper, tag_names: list[str], db: Session) -> None:
    """Replace paper.tags with the given list of tag names, creating new tags as needed."""
    resolved: list[Tag] = []
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        tag = db.query(Tag).filter(Tag.name == name).first()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        resolved.append(tag)
    paper.tags = resolved


@router.patch("/{paper_id}")
def update_paper(
    paper_id: str,
    body: PaperUpdateRequest,
    db: Session = Depends(get_session),
) -> dict[str, PaperDetail]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    paper.title = body.title
    paper.authors = body.authors
    paper.published_date = body.published_date
    paper.abstract = body.abstract
    _sync_tags(paper, body.tags, db)
    db.commit()
    db.refresh(paper)
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


@router.post("/{paper_id}/extract-metadata")
def extract_metadata(
    paper_id: str,
    db: Session = Depends(get_session),
) -> dict[str, ExtractedMetadata]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    try:
        from src.services.drive import DriveService

        logger.info("downloading PDF from Drive for paper %s", paper_id)
        t0 = time.monotonic()
        pdf_bytes = DriveService().download(paper.drive_file_id)
        logger.info("Drive download complete in %.1fs (%d bytes)", time.monotonic() - t0, len(pdf_bytes))
    except DriveUploadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        metadata = GeminiService().extract_metadata(pdf_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"metadata": metadata}


@router.get("/{paper_id}/pdf")
def get_pdf(
    paper_id: str,
    db: Session = Depends(get_session),
) -> RedirectResponse:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return RedirectResponse(url=paper.drive_view_url, status_code=302)
