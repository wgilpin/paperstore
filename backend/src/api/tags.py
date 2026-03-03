"""Tags API router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.paper_tag import paper_tags
from src.models.tag import Tag
from src.schemas.tag import TagWithCount

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


@router.get("/with-counts")
def list_tags_with_counts(db: Session = Depends(get_session)) -> dict[str, list[TagWithCount]]:
    rows = (
        db.query(Tag.name, func.count(paper_tags.c.paper_id).label("count"))
        .outerjoin(paper_tags, Tag.id == paper_tags.c.tag_id)
        .group_by(Tag.name)
        .order_by(Tag.name.asc())
        .all()
    )
    return {"tags": [TagWithCount(name=row.name, count=row.count) for row in rows]}


@router.delete("/{name}", status_code=204)
def delete_tag(name: str, db: Session = Depends(get_session)) -> None:
    tag = db.query(Tag).filter(Tag.name == name).first()
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
