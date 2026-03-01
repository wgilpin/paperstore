"""Pydantic schemas for batch metadata endpoints."""

from pydantic import BaseModel


class BatchLoopStatus(BaseModel):
    running: bool
    papers_done: int


class EligibleCountResponse(BaseModel):
    count: int
    estimated_cost_usd: float
