"""Pydantic schemas for batch metadata endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class BatchJobStatus(BaseModel):
    id: uuid.UUID
    state: str  # pending | running | succeeded | failed | applied
    paper_count: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EligibleCountResponse(BaseModel):
    count: int
    estimated_cost_usd: float
