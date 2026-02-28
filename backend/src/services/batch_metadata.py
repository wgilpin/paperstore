"""Batch metadata extraction service using the Gemini Batch API."""

import json
import logging
import os
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
    """Return the most recent job that is still pending or running, or None."""
    return (
        db.query(BatchJob)
        .filter(BatchJob.state.in_(["pending", "running"]))
        .order_by(BatchJob.created_at.desc())
        .first()
    )


def _job_to_status(job: BatchJob) -> BatchJobStatus:
    return BatchJobStatus(
        id=job.id,
        state=job.state,
        paper_count=len(job.paper_ids),
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def start_batch_job(db: Session) -> BatchJobStatus:
    """Download PDFs for eligible papers and submit a Gemini batch job.

    Raises ValueError if Gemini env vars are missing or no eligible papers.
    Raises RuntimeError if a job is already active.
    """
    if _active_job(db) is not None:
        raise RuntimeError("A batch job is already active")

    papers: list[Paper] = [p for p in db.query(Paper).all() if _is_eligible(p)]
    if not papers:
        raise ValueError("No papers need metadata extraction")

    client, model_name = _get_gemini_client()
    drive = DriveService()

    inline_requests: list[dict[str, object]] = []
    included_paper_ids: list[str] = []

    for paper in papers:
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
            included_paper_ids.append(str(paper.id))
        except DriveUploadError as exc:
            logger.warning("skipping paper %s — drive download failed: %s", paper.id, exc)

    if not inline_requests:
        raise ValueError("Failed to download PDFs for any eligible papers")

    logger.info("submitting Gemini batch job for %d papers", len(inline_requests))
    batch = client.batches.create(
        model=model_name,
        src=inline_requests,  # type: ignore[arg-type]
        config={"display_name": "paperstore-metadata"},
    )
    logger.info("batch job created: %s", batch.name)

    job = BatchJob(
        id=uuid.uuid4(),
        gemini_job_name=batch.name,
        state="pending",
        paper_ids=included_paper_ids,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_to_status(job)


def _parse_metadata(raw_text: str) -> ExtractedMetadata:
    """Parse Gemini response text into ExtractedMetadata (same as GeminiService)."""
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


def check_and_apply_batch(db: Session) -> BatchJobStatus | None:
    """Poll Gemini for the active job status; apply results if succeeded.

    Returns None if there is no active job.
    Returns updated BatchJobStatus otherwise.
    """
    job = _active_job(db)
    if job is None:
        return None

    try:
        client, _ = _get_gemini_client()
    except ValueError as exc:
        logger.error("cannot check batch job: %s", exc)
        return _job_to_status(job)

    try:
        batch = client.batches.get(name=job.gemini_job_name)
    except Exception as exc:
        logger.error("failed to poll batch job %s: %s", job.gemini_job_name, exc)
        return _job_to_status(job)

    state_name: str = batch.state.name if batch.state is not None else ""
    logger.info("batch job %s state: %s", job.gemini_job_name, state_name)

    if state_name in ("JOB_STATE_PENDING", "JOB_STATE_RUNNING"):
        job.state = "running" if state_name == "JOB_STATE_RUNNING" else "pending"
        db.commit()
        return _job_to_status(job)

    if state_name in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
        job.state = "failed"
        job.completed_at = datetime.now(UTC)
        db.commit()
        return _job_to_status(job)

    if state_name == "JOB_STATE_SUCCEEDED":
        # Apply results positionally — inline batch responses match request order
        responses = (batch.dest.inlined_responses if batch.dest is not None else None) or []
        for idx, inline_response in enumerate(responses):
            if idx >= len(job.paper_ids):
                break
            paper_id = job.paper_ids[idx]
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if paper is None:
                continue
            if inline_response.error:
                logger.warning(
                    "batch result error for paper %s: %s", paper_id, inline_response.error
                )
                continue
            try:
                if inline_response.response is None:
                    continue
                raw_text = inline_response.response.text
                if not raw_text:
                    continue
                meta = _parse_metadata(str(raw_text))
                _apply_metadata(paper, meta)
            except Exception as exc:
                logger.warning("failed to apply metadata for paper %s: %s", paper_id, exc)

        db.commit()
        job.state = "applied"
        job.completed_at = datetime.now(UTC)
        db.commit()
        return _job_to_status(job)

    return _job_to_status(job)
