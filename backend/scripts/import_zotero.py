"""Bulk-import PDFs from a Zotero local storage directory into PaperStore.

Usage:
    uv run python scripts/import_zotero.py [--zotero-dir PATH] [--dry-run]

Walks all subdirectories of --zotero-dir, finds every *.pdf, and imports each
into PaperStore via IngestionService.ingest_local().  Duplicates (by submission
URL or normalised title) are silently skipped.

Requires DATABASE_URL and Google OAuth credentials to be configured.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow running from backend/ directory without installing the package.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

# Load .env from project root (parent of backend/).
load_dotenv(_BACKEND_DIR.parent / ".env")

# Parse --db-url early so we can set DATABASE_URL before the db module
# initialises its lazy engine singleton.
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument(
    "--db-url",
    default="postgresql://paperstore:paperstore@localhost:5433/paperstore",
)
_pre_args, _ = _pre.parse_known_args()
os.environ["DATABASE_URL"] = _pre_args.db_url

from src.db import get_session  # noqa: E402
from src.services.drive import DriveUploadError  # noqa: E402
from src.services.ingestion import DuplicateError, IngestionService  # noqa: E402

_DEFAULT_ZOTERO_DIR = Path("C:/Users/wgilp/Zotero/storage")


def _collect_pdfs(zotero_dir: Path) -> list[Path]:
    return sorted(zotero_dir.rglob("*.pdf"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Zotero PDFs into PaperStore.")
    parser.add_argument(
        "--zotero-dir",
        type=Path,
        default=_DEFAULT_ZOTERO_DIR,
        help=f"Path to Zotero storage directory (default: {_DEFAULT_ZOTERO_DIR})",
    )
    parser.add_argument(
        "--db-url",
        default="postgresql://paperstore:paperstore@localhost:5433/paperstore",
        help="PostgreSQL connection URL (default: localhost:5433)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing to DB or Drive.",
    )
    args = parser.parse_args()

    zotero_dir: Path = args.zotero_dir
    dry_run: bool = args.dry_run

    if not zotero_dir.is_dir():
        print(f"ERROR: Zotero directory not found: {zotero_dir}", file=sys.stderr)
        sys.exit(1)

    pdfs = _collect_pdfs(zotero_dir)
    print(f"Found {len(pdfs)} PDF(s) in {zotero_dir}")
    if dry_run:
        print("DRY RUN — no changes will be made.\n")

    imported = 0
    skipped = 0
    errors = 0

    svc = IngestionService()

    for pdf_path in pdfs:
        relative = pdf_path.relative_to(zotero_dir)
        if dry_run:
            print(f"  WOULD IMPORT  {relative}")
            imported += 1
            continue

        db = get_session()
        try:
            pdf_bytes = pdf_path.read_bytes()
            svc.ingest_local(pdf_bytes, pdf_path, db)
            print(f"  IMPORTED      {relative}")
            imported += 1
        except DuplicateError:
            print(f"  SKIPPED       {relative}  (duplicate)")
            skipped += 1
        except DriveUploadError as exc:
            print(f"  ERROR         {relative}  (Drive: {exc})", file=sys.stderr)
            errors += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR         {relative}  ({exc})", file=sys.stderr)
            errors += 1
        finally:
            db.close()

    print(f"\nDone: {imported} imported, {skipped} skipped, {errors} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
