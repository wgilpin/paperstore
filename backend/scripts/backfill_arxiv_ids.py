"""Backfill arxiv_id for papers that were imported from local files.

For each paper with arxiv_id IS NULL, searches the arXiv API by title.
If the top result's title matches closely enough, updates the DB.

Usage (inside the api container):
    uv run python scripts/backfill_arxiv_ids.py [--dry-run] [--db-url URL]

Usage (on the host against local Docker DB):
    uv run python scripts/backfill_arxiv_ids.py --db-url postgresql://paperstore:paperstore@localhost:5433/paperstore
"""

import argparse
import os
import sys
import time
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

load_dotenv(_BACKEND_DIR.parent / ".env")

_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument(
    "--db-url",
    default="postgresql://paperstore:paperstore@db:5432/paperstore",
)
_pre_args, _ = _pre.parse_known_args()
os.environ["DATABASE_URL"] = _pre_args.db_url

import arxiv  # noqa: E402

from src.db import get_session  # noqa: E402
from src.models.paper import Paper  # noqa: E402
from src.services.arxiv_client import extract_arxiv_id  # noqa: E402


def _normalise(title: str) -> str:
    """Lowercase, strip accents, collapse whitespace for comparison."""
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_title = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_title.lower().split())


def _search_arxiv(title: str) -> tuple[str, str] | None:
    """Search arXiv by title. Returns (arxiv_id, matched_title) or None."""
    search = arxiv.Search(
        query=f'ti:"{title}"',
        max_results=1,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    client = arxiv.Client()
    results = list(client.results(search))
    if not results:
        return None
    result = results[0]
    arxiv_id = extract_arxiv_id(str(result.entry_id))
    return arxiv_id, result.title


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill arxiv_id for local-file papers.")
    parser.add_argument(
        "--db-url",
        default="postgresql://paperstore:paperstore@db:5432/paperstore",
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches without writing to DB.",
    )
    args = parser.parse_args()
    dry_run: bool = args.dry_run

    if dry_run:
        print("DRY RUN — no changes will be written.\n")

    db = get_session()
    try:
        papers: list[Paper] = db.query(Paper).filter(Paper.arxiv_id.is_(None)).all()
    finally:
        db.close()

    print(f"Found {len(papers)} paper(s) with no arxiv_id.\n")

    updated = 0
    no_match = 0
    mismatch = 0

    for paper in papers:
        time.sleep(3)  # be polite to the arXiv API (rate limit: ~1 req/3s)

        result = _search_arxiv(paper.title)
        if result is None:
            print(f"  NO RESULT     {paper.title[:70]}")
            no_match += 1
            continue

        arxiv_id, matched_title = result
        if _normalise(matched_title) != _normalise(paper.title):
            print(f"  MISMATCH      {paper.title[:60]!r}")
            print(f"                ≠ {matched_title[:60]!r}")
            mismatch += 1
            continue

        if dry_run:
            print(f"  WOULD UPDATE  {paper.title[:60]!r}  →  {arxiv_id}")
            updated += 1
            continue

        db = get_session()
        try:
            db_paper = db.query(Paper).filter(Paper.id == paper.id).one()
            db_paper.arxiv_id = arxiv_id
            db.commit()
            print(f"  UPDATED       {paper.title[:60]!r}  →  {arxiv_id}")
            updated += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            print(f"  ERROR         {paper.title[:60]!r}  ({exc})", file=sys.stderr)
        finally:
            db.close()

    print(f"\nDone: {updated} updated, {no_match} no result, {mismatch} title mismatch.")


if __name__ == "__main__":
    main()
