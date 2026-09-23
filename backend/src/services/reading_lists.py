"""Reading list service — create, read and change reading lists and their items."""

import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session, sessionmaker

from src.models.reading_list import ReadingList, ReadingListItem
from src.schemas.reading_list import (
    Candidate,
    ListProgress,
    ListSummary,
    LookupStatus,
    ParsedItem,
)
from src.services.biorxiv_client import is_biorxiv_url
from src.services.citation_resolver import CitationResolver, arxiv_id_in, library_by_doi, pdf_check
from src.services.ingestion import DuplicateError, IngestionService
from src.services.notes import NotFoundError

logger = logging.getLogger(__name__)

# Lists whose lookup thread is running. In memory, like the batch metadata loop:
# a restart ends the thread, the items stay "new", and "Find papers" starts again.
_running_lookups: set[uuid.UUID] = set()
_lookup_lock = threading.Lock()


class ReadingListService:
    def create_list(
        self, name: str, raw_text: str, items: list[ParsedItem], db: Session
    ) -> ReadingList:
        """Save a list named *name* with *items* in the given order.

        With no items, the list is saved with its raw text and marked parse_failed.
        """
        reading_list = ReadingList(
            name=name,
            raw_text=raw_text,
            parse_failed=not items,
            items=_to_rows(items),
        )
        db.add(reading_list)
        db.commit()
        return reading_list

    def parse_again(self, list_id: uuid.UUID, items: list[ParsedItem], db: Session) -> ReadingList:
        """Replace a list's items with a new parse; clear parse_failed when items were found."""
        reading_list = self.get_list(list_id, db)
        if items:
            reading_list.items = _to_rows(items)
            reading_list.parse_failed = False
        db.commit()
        return reading_list

    def get_list(self, list_id: uuid.UUID, db: Session) -> ReadingList:
        """Return the list with *list_id*; raise NotFoundError if absent."""
        reading_list = db.get(ReadingList, list_id)
        if reading_list is None:
            raise NotFoundError(f"Reading list {list_id} not found")
        return reading_list

    def toggle_tick(self, list_id: uuid.UUID, item_id: uuid.UUID, db: Session) -> ReadingListItem:
        """Tick an unticked item, or untick a ticked one.

        Raises NotFoundError if the item does not exist or belongs to another list.
        """
        item = self._get_item(list_id, item_id, db)
        # Naive UTC, matching the other timestamps in this database.
        now = datetime.now(tz=UTC).replace(tzinfo=None)
        if item.paper is not None:
            # A paper item's tick is the paper's shared read flag.
            item.paper.read_at = None if item.paper.read_at else now
        else:
            item.read_at = None if item.read_at else now
        db.commit()
        return item

    def progress(self, reading_list: ReadingList) -> ListProgress:
        """Count the ticked items of *reading_list*."""
        items = reading_list.items
        return ListProgress(read=sum(1 for i in items if i.is_read), total=len(items))

    def lookup_list(
        self, list_id: uuid.UUID, db: Session, resolver: CitationResolver | None = None
    ) -> None:
        """Look up every item not linked or looked up yet, holding the results for review.

        Commits after each item, so the list page can show progress.
        """
        resolver = resolver or CitationResolver()
        reading_list = self.get_list(list_id, db)
        for item in reading_list.items:
            if item.paper_id is not None or item.status != "new":
                continue
            candidate = resolver.resolve(_query(item), db)
            item.candidate = candidate
            item.outcome = candidate.outcome if candidate else "not_found"
            item.status = "review"
            db.commit()

    def lookup_status(self, reading_list: ReadingList) -> LookupStatus:
        """How far the list's lookup has got, and what is left to do."""
        review = len(self.review_items(reading_list))
        return LookupStatus(
            running=lookup_running(reading_list.id),
            importing=sum(1 for i in reading_list.items if i.status == "importing"),
            looked_up=review,
            unlooked=sum(1 for i in reading_list.items if i.status == "new" and i.paper_id is None),
            pending_review=review,
        )

    def review_items(self, reading_list: ReadingList) -> list[ReadingListItem]:
        """The items of *reading_list* waiting for review, in list order."""
        return [i for i in reading_list.items if i.status == "review"]

    def apply_review(
        self, list_id: uuid.UUID, accepted: set[uuid.UUID], db: Session
    ) -> list[uuid.UUID]:
        """Apply the review; return the IDs of accepted free-PDF items, now to import.

        Every reviewed item leaves review. An accepted free PDF keeps its candidate
        for the importer; any other item is finished here.
        """
        reading_list = self.get_list(list_id, db)
        to_import: list[uuid.UUID] = []
        for item in self.review_items(reading_list):
            candidate = item.candidate
            if item.id in accepted and candidate is not None:
                if candidate.outcome == "free_pdf":
                    item.status = "importing"
                    to_import.append(item.id)
                    continue
                _accept(item, candidate)
            item.candidate = None
            item.status = "done"
        db.commit()
        return to_import

    def import_item(
        self, item_id: uuid.UUID, db: Session, ingestion: IngestionService | None = None
    ) -> None:
        """Import one accepted free-PDF item through the existing ingestion, and link it.

        A duplicate links the existing paper. Any other failure marks the item
        import_failed and keeps a link to the paper, and its candidate for a retry.
        """
        item = db.get(ReadingListItem, item_id)
        if item is None or item.status != "importing":
            return
        candidate = item.candidate
        if candidate is None or not (candidate.arxiv_id or candidate.pdf_url):
            _mark_import_failed(item)
            db.commit()
            return
        url = (
            f"https://arxiv.org/abs/{candidate.arxiv_id}"
            if candidate.arxiv_id
            else candidate.pdf_url or ""
        )
        try:
            paper = (ingestion or IngestionService()).ingest(url, db)
        except DuplicateError as exc:
            db.rollback()
            if exc.paper_id:
                item.paper_id = uuid.UUID(exc.paper_id)
                item.candidate = None
                item.status = "done"
            else:
                _mark_import_failed(item)
        except Exception:
            db.rollback()
            logger.exception("import failed for reading list item %s (%s)", item_id, url)
            _mark_import_failed(item)
        else:
            item.paper_id = paper.id
            # Keep the lookup's DOI as a dedupe key, unless another paper has it.
            if candidate.doi and paper.doi is None and library_by_doi(candidate.doi, db) is None:
                paper.doi = candidate.doi
            item.candidate = None
            item.status = "done"
        db.commit()

    def upload_pdf(
        self,
        list_id: uuid.UUID,
        item_id: uuid.UUID,
        pdf_bytes: bytes,
        filename: str,
        db: Session,
        ingestion: IngestionService | None = None,
    ) -> ReadingListItem:
        """Ingest an uploaded PDF for an item without a paper, and link the paper.

        The item's link (usually its DOI) is the paper's source URL. A duplicate links
        the existing paper. Raises ValueError for a linked item or bytes that are not
        a PDF; the item is then unchanged.
        """
        item = self._get_item(list_id, item_id, db)
        if item.paper_id is not None:
            raise ValueError("This item already links to a paper.")
        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("That file is not a PDF.")
        try:
            paper = (ingestion or IngestionService()).ingest_local(
                pdf_bytes=pdf_bytes, local_path=Path(filename), db=db, source_url=item.url
            )
        except DuplicateError as exc:
            db.rollback()
            if not exc.paper_id:
                raise ValueError(str(exc)) from exc
            item.paper_id = uuid.UUID(exc.paper_id)
        else:
            item.paper_id = paper.id
            # The DOI from a doi.org link, else the one a lookup found (a failed import).
            candidate = item.candidate
            doi = _doi_of(item.url) or (candidate.doi if candidate else None)
            if doi and paper.doi is None and library_by_doi(doi, db) is None:
                paper.doi = doi
        item.candidate = None
        item.status = "done"
        db.commit()
        return item

    def add_url(
        self, list_id: uuid.UUID, item_id: uuid.UUID, url: str, db: Session
    ) -> list[uuid.UUID]:
        """Give an item without a paper a URL; return the item ID when an import starts.

        An arXiv, alphaXiv or bioRxiv URL, or one that serves a PDF, is set up for the
        importer. Any other http(s) URL becomes the item's plain link. Raises ValueError
        for any other scheme, or for a linked item; the item is then unchanged.
        """
        clean = safe_url(url.strip())
        if clean is None:
            raise ValueError("Use a link that starts with http:// or https://.")
        item = self._get_item(list_id, item_id, db)
        if item.paper_id is not None:
            raise ValueError("This item already links to a paper.")
        arxiv_id = arxiv_id_in(clean) if _is_arxiv_host(clean) else None
        if arxiv_id or is_biorxiv_url(clean) or pdf_check(clean):
            item.candidate = Candidate(
                source="manual",
                title=item.title,
                authors=list(item.authors or []),
                year=item.year,
                arxiv_id=arxiv_id,
                pdf_url=None if arxiv_id else clean,
                landing_url=clean,
                confident=True,
                outcome="free_pdf",
            )
            item.status = "importing"
            db.commit()
            return [item.id]
        item.url = clean
        item.candidate = None
        item.status = "done"
        db.commit()
        return []

    def search_again(self, list_id: uuid.UUID, item_id: uuid.UUID, db: Session) -> None:
        """Send an item without a paper back to lookup; the caller starts the lookup."""
        item = self._get_item(list_id, item_id, db)
        if item.paper_id is not None:
            raise ValueError("This item already links to a paper. Unlink it first.")
        item.status = "new"
        item.outcome = None
        item.candidate = None
        db.commit()

    def unlink(self, list_id: uuid.UUID, item_id: uuid.UUID, db: Session) -> None:
        """Remove an item's paper link; the paper, and its read state, stay in the library."""
        item = self._get_item(list_id, item_id, db)
        if item.paper_id is None:
            raise ValueError("This item has no paper to unlink.")
        # Clear the relationship too, so the flush does not restore paper_id from it.
        item.paper = None
        item.paper_id = None
        item.status = "done"
        db.commit()

    def retry_import(self, list_id: uuid.UUID, item_id: uuid.UUID, db: Session) -> list[uuid.UUID]:
        """Queue a failed import again; return the item ID for the importer."""
        item = self._get_item(list_id, item_id, db)
        if item.status != "import_failed" or item.candidate is None:
            raise ValueError("Only a failed import can be retried.")
        item.status = "importing"
        db.commit()
        return [item.id]

    def reset_stuck_imports(self, db: Session) -> int:
        """Mark items left importing by a restart as import_failed; return how many."""
        stuck = db.query(ReadingListItem).filter(ReadingListItem.status == "importing").all()
        for item in stuck:
            _mark_import_failed(item)
        db.commit()
        return len(stuck)

    def list_summaries(self, db: Session) -> list[ListSummary]:
        """Return every list with its progress, newest first."""
        lists = sorted(db.query(ReadingList).all(), key=lambda rl: rl.created_at, reverse=True)
        return [
            ListSummary(
                id=rl.id, name=rl.name, created_at=rl.created_at, progress=self.progress(rl)
            )
            for rl in lists
        ]

    def drop_item(self, list_id: uuid.UUID, item_id: uuid.UUID, db: Session) -> None:
        """Delete one item from a list. The other items keep their positions."""
        db.delete(self._get_item(list_id, item_id, db))
        db.commit()

    def delete_list(self, list_id: uuid.UUID, db: Session) -> None:
        """Delete a list; the database cascade deletes its items."""
        db.delete(self.get_list(list_id, db))
        db.commit()

    def get_item(self, list_id: uuid.UUID, item_id: uuid.UUID, db: Session) -> ReadingListItem:
        """Return the item; raise NotFoundError if absent or on another list."""
        return self._get_item(list_id, item_id, db)

    def _get_item(self, list_id: uuid.UUID, item_id: uuid.UUID, db: Session) -> ReadingListItem:
        """Return the item; raise NotFoundError if absent or on another list."""
        item = db.get(ReadingListItem, item_id)
        if item is None or item.list_id != list_id:
            raise NotFoundError(f"Item {item_id} not found in reading list {list_id}")
        return item


def _to_rows(items: list[ParsedItem]) -> list[ReadingListItem]:
    """Turn parsed items into item rows, numbered in list order."""
    return [
        ReadingListItem(
            position=position,
            citation=item.citation,
            title=item.title,
            authors=item.authors,
            year=item.year,
            note=item.note,
        )
        for position, item in enumerate(items)
    ]


def _query(item: ReadingListItem) -> ParsedItem:
    """The lookup query for a stored item."""
    return ParsedItem(
        citation=item.citation,
        title=item.title,
        authors=list(item.authors or []),
        year=item.year,
        note=item.note,
    )


def _accept(item: ReadingListItem, candidate: Candidate) -> None:
    """Apply an accepted match to *item*."""
    if candidate.outcome == "in_library" and candidate.paper_id is not None:
        item.paper_id = candidate.paper_id
    elif candidate.outcome == "record_only":
        item.url = candidate.landing_url or (
            f"https://doi.org/{candidate.doi}" if candidate.doi else None
        )


def safe_url(url: str | None) -> str | None:
    """Return *url* when it is an http(s) URL with a host; None for anything else."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return None
    return url


def _is_arxiv_host(url: str) -> bool:
    """True for arxiv.org and alphaxiv.org URLs, including their subdomains."""
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in ("arxiv.org", "alphaxiv.org"))


def _doi_of(url: str | None) -> str | None:
    """The DOI in a https://doi.org/ link, lower case; None for any other URL."""
    prefix = "https://doi.org/"
    if url and url.lower().startswith(prefix):
        return url[len(prefix) :].lower() or None
    return None


def _mark_import_failed(item: ReadingListItem) -> None:
    """Set import_failed and keep a link to the paper (the candidate stays for a retry)."""
    candidate = item.candidate
    item.status = "import_failed"
    if candidate is not None:
        item.url = candidate.landing_url or candidate.pdf_url


def start_import(item_ids: list[uuid.UUID]) -> None:
    """Import accepted free-PDF items in a background thread, one after another."""
    if item_ids:
        threading.Thread(target=_import_thread, args=(item_ids,), daemon=True).start()


def _import_thread(item_ids: list[uuid.UUID]) -> None:
    """Run the imports in their own session."""
    from src.db import _get_engine

    db = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)()
    ingestion = IngestionService()
    try:
        for item_id in item_ids:
            ReadingListService().import_item(item_id, db, ingestion)
    except Exception:
        logger.exception("import thread failed")
    finally:
        db.close()


def start_lookup(list_id: uuid.UUID) -> None:
    """Start the background lookup for a list; no-op if one is already running."""
    with _lookup_lock:
        if list_id in _running_lookups:
            return
        _running_lookups.add(list_id)
    threading.Thread(target=_lookup_thread, args=(list_id,), daemon=True).start()


def lookup_running(list_id: uuid.UUID) -> bool:
    """True while a lookup thread runs for the list."""
    with _lookup_lock:
        return list_id in _running_lookups


def _lookup_thread(list_id: uuid.UUID) -> None:
    """Run one list's lookup in its own session."""
    from src.db import _get_engine

    db = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)()
    try:
        ReadingListService().lookup_list(list_id, db)
    except Exception:
        logger.exception("lookup failed for reading list %s", list_id)
    finally:
        db.close()
        with _lookup_lock:
            _running_lookups.discard(list_id)
