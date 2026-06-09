"""GET /api/search — full-text paper search for external apps."""

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import case, func, nulls_last
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
    """Search for papers by matching query against metadata and tags.

    Supports FTS, fuzzy tag matching, and tie-breaker sorting.
    """
    # Build full-text search query from search term
    tsquery = func.plainto_tsquery("english", q)

    # Check if the paper has any tag matching the search query.
    # We match tags using three fallback levels:
    # 1. Full-text search (stemmed matching): to_tsvector('english', tag) @@ query
    # 2. Trigram similarity (typo tolerance): tag % query (requires pg_trgm extension)
    # 3. Substring matching (case-insensitive partial matching): tag ILIKE %query%
    tag_match_filter = Paper.id.in_(
        db.query(paper_tags.c.paper_id)
        .join(Tag, Tag.id == paper_tags.c.tag_id)
        .filter(
            func.to_tsvector("english", Tag.name).op("@@")(tsquery)
            | Tag.name.op("%")(q)
            | Tag.name.ilike(f"%{q}%")
        )
    )

    # Boost relevance rank by 1.0 if a tag matched the query
    tag_matched_case = case((tag_match_filter, 1.0), else_=0.0)

    # We calculate the relevance score for FTS semantic matching
    rank_expr = func.ts_rank(Paper.search_vector, tsquery)

    # Unified sorting order to satisfy conditional query types:
    # 1. tag_matched_case.desc(): Group tag-matched papers (1.0) above semantic-only papers (0.0).
    # 2. Sort tag-matched papers by added_at descending (most recently added first).
    # 3. Sort semantic-only papers by FTS relevance/closeness (rank_expr desc).
    # 4. Paper.added_at.desc(): Ultimate tie-breaker for identical semantic ranks.
    order_by_clauses = [
        tag_matched_case.desc(),
        nulls_last(case(((tag_matched_case == 1.0, Paper.added_at)), else_=None).desc()),
        nulls_last(case(((tag_matched_case == 0.0, rank_expr)), else_=None).desc()),
        Paper.added_at.desc(),
    ]

    base = (
        db.query(Paper)
        .filter(Paper.search_vector.op("@@")(tsquery) | tag_match_filter)
        .order_by(*order_by_clauses)
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
