"""Reading list service — create, read and change reading lists and their items."""

import logging
import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from src.models.reading_list import ReadingList, ReadingListItem
from src.schemas.reading_list import (
    Candidate,
    ListProgress,
    ListSummary,
    LookupStatus,
    ParsedItem,
)
from src.services.citation_resolver import CitationResolver
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
            looked_up=review,
            unlooked=sum(1 for i in reading_list.items if i.status == "new" and i.paper_id is None),
            pending_review=review,
        )

    def review_items(self, reading_list: ReadingList) -> list[ReadingListItem]:
        """The items of *reading_list* waiting for review, in list order."""
        return [i for i in reading_list.items if i.status == "review"]

    def apply_review(self, list_id: uuid.UUID, accepted: set[uuid.UUID], db: Session) -> None:
        """Apply the review: link accepted matches; every reviewed item leaves review."""
        reading_list = self.get_list(list_id, db)
        for item in self.review_items(reading_list):
            candidate = item.candidate
            if item.id in accepted and candidate is not None:
                _accept(item, candidate)
            item.candidate = None
            item.status = "done"
        db.commit()

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
    elif candidate.outcome == "free_pdf":
        # Until the importer exists, an accepted free PDF becomes a link to it.
        item.url = candidate.landing_url or candidate.pdf_url


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
