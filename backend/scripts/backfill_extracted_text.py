"""Backfill extracted_text for papers that were ingested before this field existed.

For each paper with extracted_text IS NULL, downloads the PDF from Drive and
extracts full text via pdfplumber.

Usage (inside the api container):
    uv run python scripts/backfill_extracted_text.py [--dry-run]

Usage (on the host against prod Docker DB):
    uv run python scripts/backfill_extracted_text.py --db-url postgresql://paperstore:paperstore@localhost:5433/paperstore
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

load_dotenv(_BACKEND_DIR.parent / ".env")

_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--db-url", default="postgresql://paperstore:paperstore@db:5432/paperstore")
_pre_args, _ = _pre.parse_known_args()
os.environ["DATABASE_URL"] = _pre_args.db_url

from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.db import _get_engine  # noqa: E402
from src.models.paper import Paper  # noqa: E402
from src.models.paper_tag import paper_tags  # noqa: E402, F401
from src.models.tag import Tag  # noqa: E402, F401
from src.services.drive import DriveService  # noqa: E402
from src.services.pdf_parser import PdfParser  # noqa: E402


def _make_session():  # type: ignore[return]
    engine = _get_engine()
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return factory()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill extracted_text for existing papers.")
    parser.add_argument("--db-url", default="postgresql://paperstore:paperstore@db:5432/paperstore")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be updated without writing.")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — no changes will be written.\n")

    db = _make_session()
    try:
        papers: list[Paper] = db.query(Paper).filter(Paper.extracted_text.is_(None)).all()
    finally:
        db.close()

    print(f"Found {len(papers)} paper(s) with no extracted_text.\n")

    drive = DriveService()
    pdf_parser = PdfParser()
    updated = 0
    failed = 0

    for paper in papers:
        print(f"  {paper.title[:70]!r} ...", end=" ", flush=True)

        if args.dry_run:
            print("SKIP (dry run)")
            updated += 1
            continue

        try:
            pdf_bytes = drive.download(paper.drive_file_id)
            text = pdf_parser.extract_full_text(pdf_bytes)
        except Exception as exc:
            print(f"DRIVE ERROR ({exc})")
            failed += 1
            continue

        if not text:
            print("NO TEXT EXTRACTED")
            failed += 1
            continue

        db = _make_session()
        try:
            db_paper = db.query(Paper).filter(Paper.id == paper.id).one()
            db_paper.extracted_text = text
            db.commit()
            print(f"OK ({len(text)} chars)")
            updated += 1
        except Exception as exc:
            db.rollback()
            print(f"DB ERROR ({exc})", file=sys.stderr)
            failed += 1
        finally:
            db.close()

    print(f"\nDone: {updated} updated, {failed} failed.")


if __name__ == "__main__":
    main()
