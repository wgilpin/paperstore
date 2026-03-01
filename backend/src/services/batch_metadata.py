"""Batch metadata extraction service — background loop using the Gemini Batch API."""

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from google import genai
from sqlalchemy.orm import Session

from src.models.batch_job import BatchJob
from src.models.paper import Paper
from src.schemas.batch import BatchLoopStatus
from src.schemas.paper import ExtractedMetadata
from src.services.drive import DriveService, DriveUploadError
from src.services.gemini import _MAX_PAGES, _PROMPT, _extract_first_pages_text

logger = logging.getLogger(__name__)

COST_PER_PAPER_USD = 0.005
_CHUNK_SIZE = 20
_POLL_INTERVAL_SECONDS = 300

# ── Module-level loop state ───────────────────────────────────────────────────

_running = False
_papers_done = 0
_lock = threading.Lock()


def is_running() -> bool:
    with _lock:
        return _running


def get_status() -> BatchLoopStatus:
    with _lock:
        return BatchLoopStatus(running=_running, papers_done=_papers_done)


def start_loop() -> BatchLoopStatus:
    """Start the background loop. No-op if already running."""
    global _running, _papers_done
    with _lock:
        if _running:
            return BatchLoopStatus(running=True, papers_done=_papers_done)
        _running = True
        _papers_done = 0
    threading.Thread(target=_loop, daemon=True).start()
    return BatchLoopStatus(running=True, papers_done=0)


def stop_loop() -> BatchLoopStatus:
    global _running
    with _lock:
        _running = False
        return BatchLoopStatus(running=False, papers_done=_papers_done)


def _loop() -> None:
    """Continuously process eligible papers in chunks until stopped or exhausted."""
    from sqlalchemy.orm import sessionmaker

    from src.db import _get_engine

    session_factory = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)

    try:
        client, model_name = _get_gemini_client()
    except ValueError as exc:
        logger.error("batch loop: %s", exc)
        stop_loop()
        return

    logger.info("batch loop started")

    while is_running():
        db = session_factory()
        try:
            chunk = [str(p.id) for p in db.query(Paper).all() if _is_eligible(p)][:_CHUNK_SIZE]
            if not chunk:
                logger.info("batch loop: no eligible papers remaining, stopping")
                stop_loop()
                break
            job = _submit_chunk(chunk, client, model_name, db)
            if job is not None:
                threading.Thread(
                    target=_poll_apply_thread,
                    args=(job.id, client, session_factory),
                    daemon=True,
                ).start()
        except Exception as exc:
            logger.error("batch loop: chunk failed: %s", exc)
        finally:
            db.close()
    logger.info("batch loop stopped")


def resume_submitted_chunks(db: Session) -> None:
    """On startup, re-attach to any BatchJob rows left in 'submitted' state and poll them."""
    from sqlalchemy.orm import sessionmaker

    from src.db import _get_engine

    jobs = db.query(BatchJob).filter(BatchJob.state == "submitted").all()
    if not jobs:
        return

    try:
        client, _ = _get_gemini_client()
    except ValueError as exc:
        logger.error("resume: cannot get Gemini client: %s", exc)
        return

    session_factory = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)

    for job in jobs:
        logger.info(
            "resuming in-flight chunk %s — gemini job %s (%d papers)",
            job.id,
            job.gemini_job_name,
            len(job.paper_ids),
        )
        threading.Thread(
            target=_resume_job_thread,
            args=(job.id, client, session_factory),
            daemon=True,
        ).start()


def _resume_job_thread(
    job_id: uuid.UUID,
    client: genai.Client,
    session_factory: Callable[[], Session],
) -> None:
    """Background thread: re-attach to a submitted Gemini batch and apply its results."""
    db = session_factory()
    try:
        job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if job is None:
            logger.error("resume thread: job %s not found in DB", job_id)
            return
        applied = _poll_and_apply(job, client, db)
        logger.info("resume thread: job %s — applied %d", job_id, applied)
    except Exception as exc:
        logger.error("resume thread: job %s failed: %s", job_id, exc)
    finally:
        db.close()


def _poll_apply_thread(
    job_id: uuid.UUID,
    client: genai.Client,
    session_factory: Callable[[], Session],
) -> None:
    """Background thread: poll a newly submitted batch and apply its results."""
    global _papers_done
    db = session_factory()
    try:
        job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if job is None:
            logger.error("poll thread: job %s not found in DB", job_id)
            return
        applied = _poll_and_apply(job, client, db)
        with _lock:
            _papers_done += applied
        logger.info("poll thread: job %s — applied %d", job_id, applied)
    except Exception as exc:
        logger.error("poll thread: job %s failed: %s", job_id, exc)
    finally:
        db.close()


# ── Core chunk functions ──────────────────────────────────────────────────────

def _download_pdf_bytes(pid: str, paper: Paper) -> tuple[str, bytes]:
    """Download raw PDF bytes for a single paper using a thread-local DriveService."""
    return pid, DriveService().download(paper.drive_file_id)


def _submit_chunk(
    chunk_ids: list[str],
    client: genai.Client,
    model_name: str,
    db: Session,
) -> BatchJob | None:
    """Download PDFs in parallel, extract text sequentially, submit to Gemini Batch API."""
    papers_by_id = {
        str(p.id): p
        for p in db.query(Paper).filter(Paper.id.in_(chunk_ids)).all()
    }

    # Download raw bytes concurrently (pure I/O — safe to parallelise)
    pdf_bytes_by_id: dict[str, bytes] = {}
    with ThreadPoolExecutor(max_workers=_CHUNK_SIZE) as pool:
        futures = {
            pool.submit(_download_pdf_bytes, pid, papers_by_id[pid]): pid
            for pid in chunk_ids
            if pid in papers_by_id
        }
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                _, pdf_bytes = fut.result()
                pdf_bytes_by_id[pid] = pdf_bytes
            except DriveUploadError as exc:
                logger.warning("skipping paper %s — drive download failed: %s", pid, exc)

    # Extract text sequentially (pdfplumber uses C extensions — not thread-safe)
    # Build requests in chunk_ids order to preserve index-to-paper mapping
    inline_requests: list[dict[str, object]] = []
    resolved_ids: list[str] = []
    for pid in chunk_ids:
        if pid not in pdf_bytes_by_id:
            continue
        paper = papers_by_id[pid]
        text, _ = _extract_first_pages_text(pdf_bytes_by_id[pid], _MAX_PAGES)
        logger.info("extracted text for paper %s (%s)", pid, paper.title[:60])
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
        resolved_ids.append(pid)

    if not inline_requests:
        return None

    logger.info("submitting Gemini chunk of %d papers", len(inline_requests))
    batch = client.batches.create(
        model=model_name,
        src=inline_requests,  # type: ignore[arg-type]
        config={"display_name": "paperstore-metadata-chunk"},
    )
    batch_name = batch.name or ""
    logger.info("Gemini batch created: %s", batch_name)

    job = BatchJob(
        id=uuid.uuid4(),
        gemini_job_name=batch_name,
        state="submitted",
        paper_ids=resolved_ids,
        papers_done=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("BatchJob %s persisted (state=submitted)", job.id)
    return job


def _poll_and_apply(job: BatchJob, client: genai.Client, db: Session) -> int:
    """Poll Gemini until the batch is done, apply results, update BatchJob state."""
    batch_name = job.gemini_job_name
    state_name = ""

    while True:
        time.sleep(_POLL_INTERVAL_SECONDS)
        batch = client.batches.get(name=batch_name)
        state_name = batch.state.name if batch.state is not None else "JOB_STATE_SUCCEEDED"
        logger.info("batch %s state: %s", batch_name, state_name)
        if state_name not in ("JOB_STATE_PENDING", "JOB_STATE_RUNNING"):
            break

    if state_name not in ("JOB_STATE_SUCCEEDED", ""):
        logger.warning("batch %s ended with state %s — marking failed", batch_name, state_name)
        job.state = "failed"
        job.completed_at = datetime.now(UTC)
        db.commit()
        return 0

    # Fetch fresh paper objects (needed when resuming after restart)
    papers_by_id = {
        str(p.id): p
        for p in db.query(Paper).filter(Paper.id.in_(job.paper_ids)).all()
    }

    responses = (batch.dest.inlined_responses if batch.dest is not None else None) or []
    applied = 0
    for idx, inline_response in enumerate(responses):
        if idx >= len(job.paper_ids):
            break
        paper_id = job.paper_ids[idx]
        paper = papers_by_id.get(paper_id)
        if paper is None:
            continue
        if inline_response.error:
            logger.warning("batch result error for paper %s: %s", paper_id, inline_response.error)
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

    job.state = "applied"
    job.papers_done = applied
    job.completed_at = datetime.now(UTC)
    db.commit()
    logger.info("batch %s applied %d/%d papers", batch_name, applied, len(job.paper_ids))
    return applied


# ── Helpers ───────────────────────────────────────────────────────────────────

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

    if not paper.title and meta.title:
        paper.title = meta.title
    if not paper.authors and meta.authors:
        paper.authors = meta.authors
    if not paper.abstract and meta.abstract:
        paper.abstract = meta.abstract
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
