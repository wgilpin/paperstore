"""Batch metadata extraction service using the Gemini Batch API."""

import json
import logging
import os
import threading
import time
import uuid
from datetime import UTC, datetime

from google import genai
from sqlalchemy.orm import Session

from src.models.batch_job import BatchJob
from src.models.paper import Paper
from src.schemas.batch import BatchJobStatus
from src.schemas.paper import ExtractedMetadata
from src.services.drive import DriveService, DriveUploadError
from src.services.gemini import _MAX_PAGES, _PROMPT, _extract_first_pages_text

logger = logging.getLogger(__name__)

_COST_PER_PAPER_USD = 0.005
_CHUNK_SIZE = 20
_POLL_INTERVAL_SECONDS = 30


def _is_eligible(paper: Paper) -> bool:
    """Return True if the paper is missing at least one metadata field."""
    has_abstract = bool(paper.abstract and paper.abstract.strip())
    has_authors = bool(paper.authors)
    has_date = paper.published_date is not None
    return not (has_abstract and has_authors and has_date)


def count_eligible_papers(db: Session) -> int:
    """Count papers that are missing at least one metadata field."""
    papers: list[Paper] = db.query(Paper).all()
    return sum(1 for p in papers if _is_eligible(p))


def _get_gemini_client() -> tuple[genai.Client, str]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model_name = os.environ.get("GEMINI_PDF_MODEL", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    if not model_name:
        raise ValueError("GEMINI_PDF_MODEL environment variable is not set")
    return genai.Client(api_key=api_key), model_name


def _active_job(db: Session) -> BatchJob | None:
    """Return the most recent in-progress job (preparing or running), or None."""
    return (
        db.query(BatchJob)
        .filter(BatchJob.state.in_(["preparing", "running"]))
        .order_by(BatchJob.created_at.desc())
        .first()
    )


def _job_to_status(job: BatchJob) -> BatchJobStatus:
    return BatchJobStatus(
        id=job.id,
        state=job.state,
        paper_count=len(job.paper_ids),
        papers_done=job.papers_done,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _parse_metadata(raw_text: str) -> ExtractedMetadata:
    """Parse Gemini response text into ExtractedMetadata."""
    raw = raw_text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        data: object = json.loads(raw)
    except json.JSONDecodeError:
        return ExtractedMetadata(title=None, authors=[], date=None, abstract=None)

    if not isinstance(data, dict):
        return ExtractedMetadata(title=None, authors=[], date=None, abstract=None)

    title = data.get("title")
    authors_raw = data.get("authors", [])
    date = data.get("date")
    abstract = data.get("abstract")

    return ExtractedMetadata(
        title=str(title) if title else None,
        authors=[str(a) for a in authors_raw] if isinstance(authors_raw, list) else [],
        date=str(date) if date else None,
        abstract=str(abstract) if abstract else None,
    )


def _apply_metadata(paper: Paper, meta: ExtractedMetadata) -> None:
    """Write extracted fields to paper only if the field is currently empty."""
    from src.schemas.paper import PaperUpdateRequest

    if not paper.abstract and meta.abstract:
        paper.abstract = meta.abstract
    if not paper.authors and meta.authors:
        paper.authors = meta.authors
    if paper.published_date is None and meta.date:
        try:
            parsed = PaperUpdateRequest.model_validate(
                {
                    "title": paper.title,
                    "authors": paper.authors,
                    "published_date": meta.date,
                    "abstract": paper.abstract,
                    "tags": [],
                }
            )
            paper.published_date = parsed.published_date
        except Exception:
            pass


def _process_chunk(
    chunk_ids: list[str],
    client: genai.Client,
    model_name: str,
    drive: DriveService,
    db: Session,
) -> int:
    """Download, submit, poll, and apply one chunk. Returns number of papers applied."""
    inline_requests: list[dict[str, object]] = []
    resolved_ids: list[str] = []

    for pid in chunk_ids:
        paper = db.query(Paper).filter(Paper.id == pid).first()
        if paper is None:
            continue
        try:
            logger.info("downloading PDF for paper %s (%s)", paper.id, paper.title[:60])
            pdf_bytes = drive.download(paper.drive_file_id)
            text, _ = _extract_first_pages_text(pdf_bytes, _MAX_PAGES)
            inline_requests.append(
                {
                    "contents": [
                        {
                            "parts": [{"text": _PROMPT + "\n\n" + text}],
                            "role": "user",
                        }
                    ]
                }
            )
            resolved_ids.append(str(paper.id))
        except DriveUploadError as exc:
            logger.warning("skipping paper %s — drive download failed: %s", paper.id, exc)

    if not inline_requests:
        return 0

    logger.info("submitting Gemini chunk of %d papers", len(inline_requests))
    batch = client.batches.create(
        model=model_name,
        src=inline_requests,  # type: ignore[arg-type]
        config={"display_name": "paperstore-metadata-chunk"},
    )
    batch_name = batch.name or ""
    logger.info("chunk batch job created: %s", batch_name)

    # Poll until done
    while True:
        time.sleep(_POLL_INTERVAL_SECONDS)
        batch = client.batches.get(name=batch_name)
        state_name = batch.state.name if batch.state is not None else ""
        logger.info("chunk %s state: %s", batch.name, state_name)
        if state_name not in ("JOB_STATE_PENDING", "JOB_STATE_RUNNING"):
            break

    if state_name != "JOB_STATE_SUCCEEDED":
        logger.warning("chunk %s ended with state %s", batch.name, state_name)
        return 0

    responses = (batch.dest.inlined_responses if batch.dest is not None else None) or []
    applied = 0
    for idx, inline_response in enumerate(responses):
        if idx >= len(resolved_ids):
            break
        paper_id = resolved_ids[idx]
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper is None:
            continue
        if inline_response.error:
            logger.warning("chunk result error for paper %s: %s", paper_id, inline_response.error)
            continue
        try:
            if inline_response.response is None:
                continue
            raw_text = inline_response.response.text
            if not raw_text:
                continue
            meta = _parse_metadata(str(raw_text))
            _apply_metadata(paper, meta)
            applied += 1
        except Exception as exc:
            logger.warning("failed to apply metadata for paper %s: %s", paper_id, exc)

    db.commit()
    return applied


def _run_chunked_batches(job_id: uuid.UUID, paper_ids: list[str]) -> None:
    """Process all paper IDs in chunks of _CHUNK_SIZE, updating progress in DB."""
    from sqlalchemy.orm import sessionmaker

    from src.db import _get_engine

    engine = _get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    try:
        job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if job is None:
            logger.error("background thread: job %s not found", job_id)
            return

        try:
            client, model_name = _get_gemini_client()
        except ValueError as exc:
            logger.error("background thread: %s", exc)
            job.state = "failed"
            job.completed_at = datetime.now(UTC)
            db.commit()
            return

        drive = DriveService()
        job.state = "running"
        db.commit()

        chunks = [paper_ids[i : i + _CHUNK_SIZE] for i in range(0, len(paper_ids), _CHUNK_SIZE)]
        logger.info("processing %d papers in %d chunks", len(paper_ids), len(chunks))

        for chunk_num, chunk in enumerate(chunks, 1):
            logger.info("processing chunk %d/%d", chunk_num, len(chunks))
            try:
                applied = _process_chunk(chunk, client, model_name, drive, db)
                job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
                if job is None:
                    return
                job.papers_done = min(job.papers_done + applied, len(paper_ids))
                db.commit()
                logger.info("chunk %d done — %d applied so far", chunk_num, job.papers_done)
            except Exception as exc:
                logger.error("chunk %d failed: %s", chunk_num, exc)
                # Continue to next chunk on error

        job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if job:
            job.state = "applied"
            job.completed_at = datetime.now(UTC)
            db.commit()
        logger.info("all chunks complete for job %s", job_id)

    except Exception as exc:
        logger.error("background thread: unexpected error: %s", exc)
        try:
            job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
            if job:
                job.state = "failed"
                job.completed_at = datetime.now(UTC)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def start_batch_job(db: Session) -> BatchJobStatus:
    """Create a batch job row and kick off chunked processing in a background thread.

    Returns immediately with state="preparing".
    Raises ValueError if Gemini env vars are missing or no eligible papers exist.
    Raises RuntimeError if a job is already active.
    """
    if _active_job(db) is not None:
        raise RuntimeError("A batch job is already active")

    papers: list[Paper] = [p for p in db.query(Paper).all() if _is_eligible(p)]
    if not papers:
        raise ValueError("No papers need metadata extraction")

    # Validate env vars before creating the job row
    _get_gemini_client()

    paper_ids = [str(p.id) for p in papers]

    job = BatchJob(
        id=uuid.uuid4(),
        gemini_job_name="",
        state="preparing",
        paper_ids=paper_ids,
        papers_done=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    threading.Thread(
        target=_run_chunked_batches,
        args=(job.id, paper_ids),
        daemon=True,
    ).start()

    return _job_to_status(job)


def resume_interrupted_job(db: Session) -> None:
    """If a job was left in 'running' state (server restart), re-spawn its thread."""
    job = (
        db.query(BatchJob)
        .filter(BatchJob.state == "running")
        .order_by(BatchJob.created_at.desc())
        .first()
    )
    if job is None:
        return
    logger.info("resuming interrupted batch job %s (%d papers)", job.id, len(job.paper_ids))
    threading.Thread(
        target=_run_chunked_batches,
        args=(job.id, job.paper_ids),
        daemon=True,
    ).start()


def check_and_apply_batch(db: Session) -> BatchJobStatus | None:
    """Return the status of the active batch job, or None if there is none.

    The background thread handles all Gemini polling and result application,
    so this just reads current DB state. If a job is stuck in 'preparing' for
    >10 minutes (thread died on redeploy), it is marked failed.
    """
    job = _active_job(db)
    if job is None:
        # Also surface recently-completed jobs so the UI can show the result
        job = (
            db.query(BatchJob)
            .filter(BatchJob.state.in_(["applied", "failed"]))
            .order_by(BatchJob.created_at.desc())
            .first()
        )
        return _job_to_status(job) if job else None

    if job.state == "preparing":
        age = datetime.now(UTC) - job.created_at.replace(tzinfo=UTC)
        if age.total_seconds() > 600:
            logger.warning("job %s stuck in preparing >10 min — marking failed", job.id)
            job.state = "failed"
            job.completed_at = datetime.now(UTC)
            db.commit()

    return _job_to_status(job)
