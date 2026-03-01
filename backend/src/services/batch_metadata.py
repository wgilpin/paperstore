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
from google.genai import types as genai_types
from google.genai.types import JOB_STATES_SUCCEEDED
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
_poll_thread: threading.Thread | None = None
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
            # Exclude papers already covered by an in-flight batch (survives restarts)
            in_flight: set[str] = {
                pid
                for job in db.query(BatchJob).filter(BatchJob.state == "submitted").all()
                for pid in job.paper_ids
            }
            chunk = [
                str(p.id)
                for p in db.query(Paper).all()
                if _is_eligible(p) and str(p.id) not in in_flight
            ][:_CHUNK_SIZE]
            if not chunk:
                logger.info("batch loop: no eligible papers remaining, stopping")
                stop_loop()
                break
            job = _submit_chunk(chunk, client, model_name, db)
            if job is not None:
                _ensure_poll_thread(client, session_factory)
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

    logger.info("resume: %d in-flight jobs found — starting poll thread", len(jobs))
    session_factory = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
    _ensure_poll_thread(client, session_factory)


def _ensure_poll_thread(
    client: genai.Client,
    session_factory: Callable[[], Session],
) -> None:
    """Start the shared poll thread if it is not already running."""
    global _poll_thread
    with _lock:
        if _poll_thread is not None and _poll_thread.is_alive():
            return
        t = threading.Thread(
            target=_poll_loop_thread,
            args=(client, session_factory),
            daemon=True,
        )
        _poll_thread = t
    t.start()


def _poll_loop_thread(
    client: genai.Client,
    session_factory: Callable[[], Session],
) -> None:
    """Single background thread: poll all submitted batch jobs on each tick and apply results."""
    global _papers_done
    logger.info("poll loop started")
    try:
        while True:
            time.sleep(_POLL_INTERVAL_SECONDS)
            db = session_factory()
            try:
                jobs = db.query(BatchJob).filter(BatchJob.state == "submitted").all()
                if not jobs:
                    logger.info("poll loop: no submitted jobs remain, stopping")
                    break

                # Fetch all batch statuses concurrently (pure I/O)
                with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
                    batch_futures = {
                        pool.submit(client.batches.get, name=job.gemini_job_name): job
                        for job in jobs
                    }
                    for fut in as_completed(batch_futures):
                        job = batch_futures[fut]
                        try:
                            batch = fut.result()
                        except Exception as exc:
                            logger.error(
                                "poll loop: failed to fetch batch %s: %s",
                                job.gemini_job_name,
                                exc,
                            )
                            continue
                        logger.info(
                            "batch %s state: %s",
                            job.gemini_job_name,
                            batch.state.name if batch.state is not None else "unknown",
                        )
                        if not batch.done:
                            continue
                        try:
                            applied = _apply_batch_results(job, batch, db)
                            with _lock:
                                _papers_done += applied
                        except Exception as exc:
                            logger.error("poll loop: failed to apply job %s: %s", job.id, exc)
            except Exception as exc:
                logger.error("poll loop: tick failed: %s", exc)
            finally:
                db.close()
    except Exception as exc:
        logger.error("poll loop: unexpected error: %s", exc)
    finally:
        logger.info("poll loop stopped")


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
    papers_by_id = {str(p.id): p for p in db.query(Paper).filter(Paper.id.in_(chunk_ids)).all()}

    # Download raw bytes concurrently (pure I/O — safe to parallelise)
    pdf_bytes_by_id: dict[str, bytes] = {}
    eligible_ids = [pid for pid in chunk_ids if pid in papers_by_id]
    with ThreadPoolExecutor(max_workers=len(eligible_ids) or 1) as pool:
        futures = {
            pool.submit(_download_pdf_bytes, pid, papers_by_id[pid]): pid for pid in eligible_ids
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
        try:
            text, _ = _extract_first_pages_text(pdf_bytes_by_id[pid], _MAX_PAGES)
        except Exception as exc:
            reason = str(exc)
            logger.warning("skipping paper %s permanently — text extraction failed: %s", pid, exc)
            paper.metadata_skip_reason = reason
            db.commit()
            continue
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


def _apply_batch_results(
    job: BatchJob,
    batch: genai_types.BatchJob,
    db: Session,
) -> int:
    """Apply completed batch results to papers, update BatchJob state. Returns count applied."""
    batch_name = job.gemini_job_name
    state_name = batch.state.name if batch.state is not None else "unknown"

    if batch.state is None or state_name not in JOB_STATES_SUCCEEDED:
        logger.warning("batch %s ended with state %s — marking failed", batch_name, state_name)
        job.state = "failed"
        job.completed_at = datetime.now(UTC)
        db.commit()
        return 0

    # Fetch fresh paper objects (needed when resuming after restart)
    papers_by_id = {str(p.id): p for p in db.query(Paper).filter(Paper.id.in_(job.paper_ids)).all()}

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
    """Return True if the paper needs metadata extraction and has not been permanently skipped."""
    if paper.metadata_skip_reason is not None:
        return False
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
