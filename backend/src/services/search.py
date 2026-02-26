"""Search service for the paper library."""

from typing import Literal

from sqlalchemy import func, nulls_last
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.models.paper_tag import paper_tags
from src.models.tag import Tag

SortField = Literal["added_at", "title", "published_date"]

PAGE_SIZE = 20


class SearchService:
    def search(
        self,
        query: str | None,
        db: Session,
        sort: SortField = "added_at",
        page: int = 1,
        tag: str | None = None,
    ) -> tuple[list[Paper], int]:
        """Return papers matching *query*, or all papers if query is empty.

        Returns (papers, total_count). When no query, sorts by *sort* field.
        When a query is present, sorts by relevance (ts_rank).
        When *tag* is set, restricts results to papers with that tag name.
        """
        offset = (page - 1) * PAGE_SIZE

        if not query:
            if sort == "published_date":
                order = nulls_last(Paper.published_date.desc())
            elif sort == "title":
                order = Paper.title.asc()
            else:
                order = Paper.added_at.desc()
            base = db.query(Paper).order_by(order)
            if tag:
                base = (
                    base.join(paper_tags, Paper.id == paper_tags.c.paper_id)
                    .join(Tag, Tag.id == paper_tags.c.tag_id)
                    .filter(Tag.name == tag)
                )
            total: int = base.count()
            papers = base.offset(offset).limit(PAGE_SIZE).all()
            return papers, total

        tsquery = func.plainto_tsquery("english", query)
        base = (
            db.query(Paper)
            .filter(Paper.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank(Paper.search_vector, tsquery).desc())
        )
        if tag:
            base = (
                base.join(paper_tags, Paper.id == paper_tags.c.paper_id)
                .join(Tag, Tag.id == paper_tags.c.tag_id)
                .filter(Tag.name == tag)
            )
        total = base.count()
        papers = base.offset(offset).limit(PAGE_SIZE).all()
        return papers, total
