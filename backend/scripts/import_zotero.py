"""Bulk-import PDFs from a Zotero local storage directory into PaperStore.

Usage:
    uv run python scripts/import_zotero.py [--zotero-dir PATH] [--dry-run]

Walks all subdirectories of --zotero-dir, finds every *.pdf, and imports each
into PaperStore via IngestionService.ingest_local().  Duplicates (by submission
URL or normalised title) are silently skipped.

After PDF import, syncs tags from the Zotero SQLite database: for each Zotero
item, finds the matching paper in PaperStore by normalised title and adds any
missing tags.

Requires DATABASE_URL and Google OAuth credentials to be configured.
"""

import argparse
import os
import re
import sqlite3
import sys
import uuid
from collections import defaultdict
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
from src.models.paper import Paper  # noqa: E402
from src.models.paper_tag import paper_tags  # noqa: E402
from src.models.tag import Tag  # noqa: E402
from src.services.drive import DriveUploadError  # noqa: E402
from src.services.ingestion import DuplicateError, IngestionService  # noqa: E402

_DEFAULT_ZOTERO_DIR = Path("C:/Users/wgilp/Zotero/storage")
_DEFAULT_ZOTERO_DB = Path("C:/Users/wgilp/Zotero/zotero.sqlite")

# Tags added automatically by Zotero connectors — not useful for search.
_ZOTERO_AUTO_TAGS = {
    "No DOI Found",
    "Metadata Updated",
    "Via Zotero Translator",
    "CrossRef Failed",
    "DOI Added",
    "needs-pdf",
    "_tablet",
    "_tablet_modified",
}

# Zotero internal collection/group IDs stored as tags — skip these.
_UUID_TAG_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _collect_pdfs(zotero_dir: Path) -> list[Path]:
    return sorted(zotero_dir.rglob("*.pdf"))


_ZOTERO_KEY_RE = re.compile(r"/storage/([A-Z0-9]{8})/", re.IGNORECASE)


def _load_zotero_tags(zotero_db: Path) -> dict[str, list[str]]:
    """Return {attachment_key: [tag_name, ...]} from the Zotero SQLite DB.

    Tags live on the parent item; the attachment item key matches the folder
    name embedded in submission_url.  Skips auto-generated Zotero tags.
    """
    conn = sqlite3.connect(str(zotero_db))
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT attach_item.key AS attachment_key, t.name AS tag
            FROM itemAttachments ia
            JOIN items attach_item ON attach_item.itemID = ia.itemID
            JOIN itemTags it ON it.itemID = ia.parentItemID
            JOIN tags t ON t.tagID = it.tagID
            """
        )
        result: dict[str, list[str]] = defaultdict(list)
        for key, tag in cursor.fetchall():
            if tag in _ZOTERO_AUTO_TAGS or _UUID_TAG_RE.match(tag):
                continue
            result[key.upper()].append(tag)
        return dict(result)
    finally:
        conn.close()


def _sync_tags(zotero_db: Path, dry_run: bool) -> None:
    """Sync Zotero tags into PaperStore using attachment-key matching."""
    print(f"\nLoading tags from {zotero_db} …")
    key_to_tags = _load_zotero_tags(zotero_db)
    print(f"Found {len(key_to_tags)} Zotero attachment(s) with user tags.")

    tagged = 0
    unmatched = 0
    already_tagged = 0

    db = get_session()
    try:
        papers: list[Paper] = db.query(Paper).all()

        # Build lookup: Zotero attachment key → Paper
        key_to_paper: dict[str, Paper] = {}
        for p in papers:
            m = _ZOTERO_KEY_RE.search(p.submission_url)
            if m:
                key_to_paper[m.group(1).upper()] = p

        for zotero_key, tags in key_to_tags.items():
            paper = key_to_paper.get(zotero_key)
            if paper is None:
                print(f"  NO MATCH      key={zotero_key}")
                unmatched += 1
                continue

            existing_tag_names = {t.name for t in paper.tags}
            new_tags = [t for t in tags if t not in existing_tag_names]
            if not new_tags:
                already_tagged += 1
                continue

            if dry_run:
                print(f"  WOULD TAG     {paper.title[:60]}  →  {new_tags}")
                tagged += 1
                continue

            for tag_name in new_tags:
                tag = db.query(Tag).filter(Tag.name == tag_name).first()
                if tag is None:
                    tag = Tag(id=uuid.uuid4(), name=tag_name)
                    db.add(tag)
                    db.flush()
                db.execute(
                    paper_tags.insert().values(paper_id=paper.id, tag_id=tag.id)
                )
                print(f"  TAGGED        {paper.title[:60]}  →  {tag_name!r}")

            db.commit()
            tagged += 1

    finally:
        db.close()

    print(
        f"\nTag sync done: {tagged} paper(s) updated, "
        f"{already_tagged} already up-to-date, {unmatched} unmatched."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Zotero PDFs into PaperStore.")
    parser.add_argument(
        "--zotero-dir",
        type=Path,
        default=_DEFAULT_ZOTERO_DIR,
        help=f"Path to Zotero storage directory (default: {_DEFAULT_ZOTERO_DIR})",
    )
    parser.add_argument(
        "--zotero-db",
        type=Path,
        default=_DEFAULT_ZOTERO_DB,
        help=f"Path to Zotero SQLite database (default: {_DEFAULT_ZOTERO_DB})",
    )
    parser.add_argument(
        "--db-url",
        default="postgresql://paperstore:paperstore@localhost:5433/paperstore",
        help="PostgreSQL connection URL (default: localhost:5433)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported/tagged without writing to DB or Drive.",
    )
    parser.add_argument(
        "--tags-only",
        action="store_true",
        help="Skip PDF import; only sync tags from the Zotero database.",
    )
    args = parser.parse_args()

    zotero_dir: Path = args.zotero_dir
    zotero_db: Path = args.zotero_db
    dry_run: bool = args.dry_run
    tags_only: bool = args.tags_only

    if not tags_only:
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

    if not zotero_db.is_file():
        print(f"ERROR: Zotero database not found: {zotero_db}", file=sys.stderr)
        sys.exit(1)

    _sync_tags(zotero_db, dry_run)


if __name__ == "__main__":
    main()
