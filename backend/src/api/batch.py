"""Batch metadata extraction API router."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_session
from src.schemas.batch import BatchJobStatus, EligibleCountResponse
from src.services.batch_metadata import (
    _COST_PER_PAPER_USD,
    check_and_apply_batch,
    count_eligible_papers,
    start_batch_job,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metadata/eligible-count")
def eligible_count(db: Session = Depends(get_session)) -> EligibleCountResponse:
    """Return the number of papers eligible for metadata extraction and estimated cost."""
    n = count_eligible_papers(db)
    return EligibleCountResponse(count=n, estimated_cost_usd=round(n * _COST_PER_PAPER_USD, 4))


@router.post("/metadata", status_code=202)
def start_metadata_batch(
    db: Session = Depends(get_session),
) -> dict[str, BatchJobStatus]:
    """Start a Gemini batch job to extract metadata for all eligible papers."""
    try:
        status = start_batch_job(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": status}


@router.get("/metadata/status")
def batch_status(
    db: Session = Depends(get_session),
) -> dict[str, BatchJobStatus | None]:
    """Poll the active batch job status. Applies results if the job has succeeded."""
    status = check_and_apply_batch(db)
    return {"job": status}
