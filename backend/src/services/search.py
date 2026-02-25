"""Search service for the paper library."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.paper import Paper


class SearchService:
    def search(self, query: str | None, db: Session) -> list[Paper]:
        """Return papers matching *query*, or all papers if query is empty.

        Results are ordered by added_at DESC (newest first).
        """
        if not query:
            return db.query(Paper).order_by(Paper.added_at.desc()).all()

        tsquery = func.plainto_tsquery("english", query)
        return (
            db.query(Paper)
            .filter(Paper.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank(Paper.search_vector, tsquery).desc())
            .all()
        )
