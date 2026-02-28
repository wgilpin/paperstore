"""Pydantic schemas for batch metadata endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class BatchJobStatus(BaseModel):
    id: uuid.UUID
    state: str  # preparing | running | applied | failed
    paper_count: int
    papers_done: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EligibleCountResponse(BaseModel):
    count: int
    estimated_cost_usd: float
