"""Batch metadata extraction API router."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db import get_session
from src.schemas.batch import BatchLoopStatus, EligibleCountResponse
from src.services.batch_metadata import (
    COST_PER_PAPER_USD,
    count_eligible_papers,
    get_status,
    start_loop,
    stop_loop,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metadata/eligible-count")
def eligible_count(db: Session = Depends(get_session)) -> EligibleCountResponse:
    """Return the number of papers eligible for metadata extraction and estimated cost."""
    n = count_eligible_papers(db)
    return EligibleCountResponse(count=n, estimated_cost_usd=round(n * COST_PER_PAPER_USD, 4))


@router.get("/metadata/status")
def batch_status() -> dict[str, BatchLoopStatus]:
    """Return current loop status."""
    return {"status": get_status()}


@router.post("/metadata/start", status_code=200)
def start_metadata_loop() -> dict[str, BatchLoopStatus]:
    """Start the background metadata extraction loop."""
    return {"status": start_loop()}


@router.post("/metadata/stop", status_code=200)
def stop_metadata_loop() -> dict[str, BatchLoopStatus]:
    """Stop the background metadata extraction loop."""
    return {"status": stop_loop()}
