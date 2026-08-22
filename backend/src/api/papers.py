"""Papers API router."""

import logging
import threading
import time
from pathlib import Path
from typing import Literal

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
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
    PaperTagsUpdateRequest,
    PaperUpdateRequest,
)
from src.schemas.summary import SummaryGenerateRequest, SummaryResponse
from src.services.arxiv_client import ArxivUnavailableError
from src.services.batch_metadata import _apply_metadata, _is_eligible
from src.services.drive import DriveUploadError
from src.services.gemini import GeminiService
from src.services.ingestion import DuplicateError, IngestionService
from src.services.search import SearchService
from src.services.summary import SummaryService

logger = logging.getLogger(__name__)

router = APIRouter()


def _enrich_paper_async(paper_id: str, drive_file_id: str) -> None:
    """Spawn a daemon thread to extract metadata via Gemini and apply it to empty fields."""

    def _run() -> None:
        from sqlalchemy.orm import sessionmaker

        from src.db import _get_engine
        from src.services.drive import DriveService

        db = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)()
        try:
            pdf_bytes = DriveService().download(drive_file_id)
            metadata = GeminiService().extract_metadata(pdf_bytes)
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if paper is None:
                return
            _apply_metadata(paper, metadata, overwrite_title=True)
            db.commit()
        except Exception:
            logger.exception("Background metadata extraction failed for paper %s", paper_id)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()


def _tag_names(paper: Paper) -> list[str]:
    return sorted(t.name for t in (paper.tags or []))


def _to_paper_detail(paper: Paper, note: Note) -> PaperDetail:
    import os

    folder_id = os.environ.get("DRIVE_FOLDER_ID", "").strip()
    drive_folder_url = f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else None
    return PaperDetail(
        id=paper.id,
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=paper.authors,
        published_date=paper.published_date,
        abstract=paper.abstract,
        submission_url=paper.submission_url,
        drive_view_url=paper.drive_view_url,
        drive_folder_url=drive_folder_url,
        added_at=paper.added_at,
        note=NoteSchema(content=note.content, updated_at=note.updated_at),
        tags=_tag_names(paper),
    )



@router.get("/receive-share", response_class=RedirectResponse)
def receive_share(
    request: Request,
    url: str | None = None,
    title: str | None = None,
    text: str | None = None,
) -> RedirectResponse:
    if not request.session.get("authenticated"):
        return RedirectResponse("/auth/login")

    # Android often places the URL in the text field rather than url
    resolved_url = url or ""
    if not resolved_url and text:
        import re

        match = re.search(r"https?://\S+", text)
        if match:
            resolved_url = match.group(0)

    if resolved_url:
        from urllib.parse import urlencode

        query = urlencode({"add_url": resolved_url})
        return RedirectResponse(f"/?{query}", status_code=303)
    return RedirectResponse("/", status_code=303)


@router.post("", status_code=201)
def submit_paper(
    body: PaperSubmitRequest,
    db: Session = Depends(get_session),
) -> dict[str, PaperDetail]:
    svc = IngestionService()
    try:
        paper = svc.ingest(body.url, db)
    except DuplicateError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate", "message": str(exc), "paper_id": exc.paper_id},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DriveUploadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ArxivUnavailableError as exc:
        logger.exception("arXiv API unavailable during ingestion of %s", body.url)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("PDF download failed for %s: %s", body.url, exc)
        detail = f"Could not download the PDF (HTTP {exc.response.status_code})."
        if exc.response.status_code == 429:
            detail += " The publisher is rate-limiting the server — try again later."
        raise HTTPException(status_code=502, detail=detail) from exc

    if _is_eligible(paper):
        _enrich_paper_async(str(paper.id), paper.drive_file_id)

    note = db.query(Note).filter(Note.paper_id == paper.id).first()
    assert note is not None
    return {"paper": _to_paper_detail(paper, note)}


@router.post("/upload", status_code=201)
def upload_paper(
    file: UploadFile = File(...),
    source_url: str | None = Form(default=None),
    db: Session = Depends(get_session),
) -> dict[str, PaperDetail]:
    pdf_bytes = file.file.read()
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Uploaded file is not a PDF")
    filename = file.filename or "upload.pdf"
    local_path = Path(filename)
    svc = IngestionService()
    try:
        paper = svc.ingest_local(
            pdf_bytes=pdf_bytes, local_path=local_path, source_url=source_url, db=db
        )
    except DuplicateError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate", "message": str(exc), "paper_id": exc.paper_id},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DriveUploadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if _is_eligible(paper):
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


@router.get("/check")
def check_paper(
    url: str = Query(...),
    db: Session = Depends(get_session),
) -> dict[str, object]:
    """Check if a paper is already saved by submission URL or arXiv ID."""
    from src.services.arxiv_client import extract_arxiv_id
    from src.services.ingestion import _is_arxiv_url, normalize_url

    url = normalize_url(url)

    # Check by submission URL
    paper = db.query(Paper).filter(Paper.submission_url == url).first()
    if paper:
        return {"saved": True, "paper_id": str(paper.id)}

    # Check by arXiv ID if applicable
    if _is_arxiv_url(url):
        arxiv_id = extract_arxiv_id(url)
        paper = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
        if paper:
            return {"saved": True, "paper_id": str(paper.id)}

    return {"saved": False, "paper_id": None}


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
    old_tags = list(paper.tags)
    resolved: list[Tag] = []
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        tag = db.query(Tag).filter(Tag.name.ilike(name)).first()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        resolved.append(tag)
    paper.tags = resolved
    db.flush()
    for tag in old_tags:
        if not tag.papers:
            db.delete(tag)


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


@router.patch("/{paper_id}/tags")
def update_paper_tags(
    paper_id: str,
    body: PaperTagsUpdateRequest,
    db: Session = Depends(get_session),
) -> dict[str, list[str]]:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    _sync_tags(paper, body.tags, db)
    db.commit()
    db.refresh(paper)
    return {"tags": _tag_names(paper)}


@router.delete("/{paper_id}", status_code=204)
def delete_paper(
    paper_id: str,
    db: Session = Depends(get_session),
) -> None:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    drive_file_id = paper.drive_file_id
    tags_to_check = list(paper.tags)
    db.query(Note).filter(Note.paper_id == paper.id).delete()
    db.delete(paper)
    db.flush()
    for tag in tags_to_check:
        if not tag.papers:
            db.delete(tag)
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
        logger.info(
            "Drive download complete in %.1fs (%d bytes)",
            time.monotonic() - t0,
            len(pdf_bytes),
        )
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


@router.get("/{paper_id}/download")
def download_paper(
    paper_id: str,
    db: Session = Depends(get_session),
) -> Response:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    try:
        from src.services.drive import DriveService

        pdf_bytes = DriveService().download(paper.drive_file_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Drive download failed: {exc}") from exc

    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in paper.title).strip()
    if not safe_title:
        safe_title = "paper"
    filename = f"{safe_title}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.get("/{paper_id}/summary", response_model=SummaryResponse)
def get_paper_summary(
    paper_id: str,
    db: Session = Depends(get_session),
) -> SummaryResponse:
    """Get the cached paper summary."""
    try:
        summary_text, has_image = SummaryService().get_summary(paper_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SummaryResponse(summary_text=summary_text, has_image=has_image)


@router.post("/{paper_id}/summary", response_model=SummaryResponse)
def generate_paper_summary(
    paper_id: str,
    body: SummaryGenerateRequest | None = None,
    db: Session = Depends(get_session),
) -> SummaryResponse:
    """Generate or regenerate the paper summary."""
    instructions = body.instructions if body else None
    try:
        summary_text, has_image = SummaryService().generate_summary(
            paper_id=paper_id, db=db, instructions=instructions
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Summary generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SummaryResponse(summary_text=summary_text, has_image=has_image)


@router.get("/{paper_id}/summary-image")
def get_paper_summary_image(
    paper_id: str,
    db: Session = Depends(get_session),
) -> Response:
    """Get the cached paper summary whiteboard image."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not paper.summary_image:
        raise HTTPException(status_code=404, detail="Summary image not found")
    
    image_data = paper.summary_image
    if image_data.startswith(b"<svg") or b"<svg" in image_data[:100]:
        media_type = "image/svg+xml"
    else:
        media_type = "image/jpeg"
        
    return Response(content=image_data, media_type=media_type)
