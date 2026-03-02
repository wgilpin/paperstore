"""Remove duplicate papers (same title) from the database.

For each group of papers sharing an exact title, keeps the best copy:
  1. Prefers rows that have an abstract.
  2. Among those, prefers the row with the most tag assignments.
  3. Falls back to the earliest added_at.

Tags from all discarded copies are merged onto the keeper before deletion.

Usage (inside the api container):
    uv run python scripts/dedup_papers.py [--dry-run] [--db-url URL]

Usage (on the host against local Docker DB):
    uv run python scripts/dedup_papers.py --db-url postgresql://paperstore:paperstore@localhost:5433/paperstore
"""

import argparse
import sys
from pathlib import Path

# Ensure stdout handles Unicode (needed on Windows).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Allow imports from src/ when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from src.models.note import Note  # noqa: F401 — registers model
from src.models.paper import Paper
from src.models.paper_tag import paper_tags
from src.models.tag import Tag  # noqa: F401 — registers model


def _get_db_url(override: str | None) -> str:
    if override:
        return override
    import os
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("ERROR: DATABASE_URL not set. Pass --db-url or set the env var.")
    return url


def run(db_url: str, dry_run: bool) -> None:
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()

    try:
        # Count tag assignments per paper as a subquery.
        tag_count_sq = (
            db.query(
                paper_tags.c.paper_id,
                func.count(paper_tags.c.tag_id).label("tag_count"),
            )
            .group_by(paper_tags.c.paper_id)
            .subquery()
        )

        # Load all papers with their tag counts.
        rows = (
            db.query(Paper, func.coalesce(tag_count_sq.c.tag_count, 0).label("tag_count"))
            .outerjoin(tag_count_sq, Paper.id == tag_count_sq.c.paper_id)
            .order_by(Paper.title)
            .all()
        )

        # Group by title.
        from collections import defaultdict
        groups: dict[str, list[tuple[Paper, int]]] = defaultdict(list)
        for paper, tag_count in rows:
            groups[paper.title].append((paper, tag_count))

        dup_groups = {title: copies for title, copies in groups.items() if len(copies) > 1}

        if not dup_groups:
            print("No duplicate papers found. Nothing to do.")
            return

        total_deleted = 0
        total_tags_merged = 0

        for title, copies in sorted(dup_groups.items()):
            # Sort: abstract first, then most tags, then oldest.
            copies.sort(key=lambda x: (
                0 if x[0].abstract is not None else 1,
                -x[1],
                x[0].added_at,
            ))
            keeper, _ = copies[0]
            discards = [p for p, _ in copies[1:]]

            keeper_tag_ids = {t.id for t in keeper.tags}
            tags_merged = 0

            for discard in discards:
                for tag in discard.tags:
                    if tag.id not in keeper_tag_ids:
                        keeper.tags.append(tag)
                        keeper_tag_ids.add(tag.id)
                        tags_merged += 1

            print(
                f"  KEEP  [{keeper.id}] {title!r}"
                f" (abstract={'yes' if keeper.abstract else 'no'}, tags={len(keeper_tag_ids)})"
            )
            for discard in discards:
                print(f"  DEL   [{discard.id}]")
                if not dry_run:
                    db.delete(discard)

            total_deleted += len(discards)
            total_tags_merged += tags_merged

        print()
        print(f"Duplicate groups : {len(dup_groups)}")
        print(f"Rows to delete   : {total_deleted}")
        print(f"Tags to merge    : {total_tags_merged}")

        if dry_run:
            print("\nDry run — no changes committed.")
        else:
            db.commit()
            print("\nDone.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without making changes")
    parser.add_argument("--db-url", default=None, help="Database URL (overrides DATABASE_URL env var)")
    args = parser.parse_args()

    db_url = _get_db_url(args.db_url)
    run(db_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
