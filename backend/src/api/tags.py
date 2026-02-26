"""Tags API router."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.paper_tag import paper_tags
from src.models.tag import Tag

router = APIRouter()


@router.get("")
def list_tags(db: Session = Depends(get_session)) -> dict[str, list[str]]:
    rows = (
        db.query(Tag.name, func.count(paper_tags.c.paper_id).label("n"))
        .outerjoin(paper_tags, Tag.id == paper_tags.c.tag_id)
        .group_by(Tag.name)
        .order_by(func.count(paper_tags.c.paper_id).desc(), Tag.name.asc())
        .all()
    )
    return {"tags": [row.name for row in rows]}
