"""Tags API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.tag import Tag

router = APIRouter()


@router.get("")
def list_tags(db: Session = Depends(get_session)) -> dict[str, list[str]]:
    tags = db.query(Tag.name).order_by(Tag.name.asc()).all()
    return {"tags": [row.name for row in tags]}
