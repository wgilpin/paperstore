"""GET /api/recent — returns recently saved papers for the news aggregator."""

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.paper import Paper
from src.schemas.paper import RecentPaper

router = APIRouter()

_RECENT_TOKEN = os.environ.get("RECENT_API_TOKEN", "")


def _verify_token(authorization: str | None = Header(default=None)) -> None:
    if not _RECENT_TOKEN:
        raise HTTPException(status_code=500, detail="RECENT_API_TOKEN not configured")
    if authorization != f"Bearer {_RECENT_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/recent", dependencies=[Depends(_verify_token)])
def get_recent(
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_session),
) -> list[RecentPaper]:
    query = db.query(Paper).order_by(Paper.added_at.desc())
    if since is not None:
        since_utc = since.replace(tzinfo=UTC) if since.tzinfo is None else since
        query = query.filter(Paper.added_at > since_utc)
    papers = query.all()
    return [
        RecentPaper(
            title=p.title,
            authors=", ".join(p.authors) if p.authors else "Unknown",
            date=p.added_at.replace(tzinfo=UTC) if p.added_at.tzinfo is None else p.added_at,
            url=p.submission_url,
            summary=p.abstract or None,
            extracted_text=p.extracted_text,
        )
        for p in papers
        if p.abstract or p.extracted_text
    ]
