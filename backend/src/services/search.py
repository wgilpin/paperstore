"""Search service for the paper library."""

from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.paper import Paper

SortField = Literal["added_at", "title"]

PAGE_SIZE = 20


class SearchService:
    def search(
        self,
        query: str | None,
        db: Session,
        sort: SortField = "added_at",
        page: int = 1,
    ) -> tuple[list[Paper], int]:
        """Return papers matching *query*, or all papers if query is empty.

        Returns (papers, total_count). When no query, sorts by *sort* field.
        When a query is present, sorts by relevance (ts_rank).
        """
        offset = (page - 1) * PAGE_SIZE

        if not query:
            order = Paper.added_at.desc() if sort == "added_at" else Paper.title.asc()
            base = db.query(Paper).order_by(order)
            total: int = base.count()
            papers = base.offset(offset).limit(PAGE_SIZE).all()
            return papers, total

        tsquery = func.plainto_tsquery("english", query)
        base = (
            db.query(Paper)
            .filter(Paper.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank(Paper.search_vector, tsquery).desc())
        )
        total = base.count()
        papers = base.offset(offset).limit(PAGE_SIZE).all()
        return papers, total
