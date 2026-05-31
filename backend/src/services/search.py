"""Search service for the paper library."""

from typing import Literal

from sqlalchemy import case, func, nulls_last
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
                order = Paper.title.asc()  # type: ignore[assignment]
            else:
                order = Paper.added_at.desc()  # type: ignore[assignment]
            base = db.query(Paper).order_by(order)
            if tag:
                base = base.filter(
                    Paper.id.in_(
                        db.query(paper_tags.c.paper_id)
                        .join(Tag, Tag.id == paper_tags.c.tag_id)
                        .filter(Tag.name == tag)
                    )
                )
            total: int = base.count()
            papers = base.offset(offset).limit(PAGE_SIZE).all()
            return papers, total

        # Build full-text search query from search term
        tsquery = func.plainto_tsquery("english", query)

        # Check if the paper has any tag matching the search query.
        # We match tags using three fallback levels:
        # 1. Full-text search (stemmed matching): to_tsvector('english', tag) @@ query
        # 2. Trigram similarity (typo tolerance): tag % query (requires pg_trgm extension)
        # 3. Substring matching (case-insensitive partial matching): tag ILIKE %query%

        tag_match_filter = Paper.id.in_(
            db.query(paper_tags.c.paper_id)
            .join(Tag, Tag.id == paper_tags.c.tag_id)
            .filter(
                func.to_tsvector("english", Tag.name).op("@@")(tsquery) |
                Tag.name.op("%")(query) |
                Tag.name.ilike(f"%{query}%")
            )
        )

        # Boost relevance rank by 1.0 if a tag matched the query
        tag_matched_case = case(
            (tag_match_filter, 1.0),
            else_=0.0
        )

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
            Paper.added_at.desc()
        ]

        base = (
            db.query(Paper)
            .filter(Paper.search_vector.op("@@")(tsquery) | tag_match_filter)
            .order_by(*order_by_clauses)
        )

        # Restrict to a specific tag if filtered
        if tag:
            base = base.filter(
                Paper.id.in_(
                    db.query(paper_tags.c.paper_id)
                    .join(Tag, Tag.id == paper_tags.c.tag_id)
                    .filter(Tag.name == tag)
                )
            )
        total = base.count()
        papers = base.offset(offset).limit(PAGE_SIZE).all()
        return papers, total
