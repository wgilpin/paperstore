"""GET /api/search — full-text paper search for external apps."""

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.paper import Paper
from src.models.paper_tag import paper_tags
from src.models.tag import Tag
from src.schemas.paper import SearchPaper

router = APIRouter()

_RECENT_TOKEN = os.environ.get("RECENT_API_TOKEN", "")


def _verify_token(authorization: str | None = Header(default=None)) -> None:
    if not _RECENT_TOKEN:
        raise HTTPException(status_code=500, detail="RECENT_API_TOKEN not configured")
    if authorization != f"Bearer {_RECENT_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/search", dependencies=[Depends(_verify_token)])
def search_papers(
    q: str = Query(...),
    limit: int = Query(default=20, ge=1),
    tag: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_session),
) -> list[SearchPaper]:
    tsquery = func.plainto_tsquery("english", q)
    base = (
        db.query(Paper)
        .filter(Paper.search_vector.op("@@")(tsquery))
        .order_by(func.ts_rank(Paper.search_vector, tsquery).desc())
    )
    if tag:
        base = base.filter(
            Paper.id.in_(
                db.query(paper_tags.c.paper_id)
                .join(Tag, Tag.id == paper_tags.c.tag_id)
                .filter(Tag.name == tag)
            )
        )
    if since is not None:
        since_utc = since.replace(tzinfo=UTC) if since.tzinfo is None else since
        base = base.filter(Paper.added_at > since_utc)
    papers = base.limit(limit).all()
    return [
        SearchPaper(
            id=p.id,
            title=p.title,
            authors=p.authors,
            added_at=p.added_at.replace(tzinfo=UTC) if p.added_at.tzinfo is None else p.added_at,
            published_date=p.published_date,
            url=p.submission_url,
            tags=[t.name for t in p.tags],
            summary=p.abstract,
            extracted_text=p.extracted_text,
        )
        for p in papers
    ]
