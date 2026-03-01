"""Batch metadata extraction service — background loop using the Gemini Batch API."""

import json
import logging
import os
import threading
import time

from google import genai
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.schemas.batch import BatchLoopStatus
from src.schemas.paper import ExtractedMetadata
from src.services.drive import DriveService, DriveUploadError
from src.services.gemini import _MAX_PAGES, _PROMPT, _extract_first_pages_text

logger = logging.getLogger(__name__)

_COST_PER_PAPER_USD = 0.005
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

    drive = DriveService()
    logger.info("batch loop started")

    while is_running():
        db = session_factory()
        try:
            chunk = [str(p.id) for p in db.query(Paper).all() if _is_eligible(p)][:_CHUNK_SIZE]
            if not chunk:
                logger.info("batch loop: no eligible papers remaining, stopping")
                stop_loop()
                break
            applied = _process_chunk(chunk, client, model_name, drive, db)
            global _papers_done
            with _lock:
                _papers_done += applied
            logger.info("batch loop: chunk done, %d applied so far", _papers_done)
        except Exception as exc:
            logger.error("batch loop: chunk failed: %s", exc)
        finally:
            db.close()

    logger.info("batch loop stopped")


# ── Helpers (unchanged) ───────────────────────────────────────────────────────

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
