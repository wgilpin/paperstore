"""Reading list service — create, read and change reading lists and their items."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models.reading_list import ReadingList, ReadingListItem
from src.schemas.reading_list import ListProgress, ParsedItem
from src.services.notes import NotFoundError


class ReadingListService:
    def create_list(
        self, name: str, raw_text: str, items: list[ParsedItem], db: Session
    ) -> ReadingList:
        """Save a list named *name* with *items* in the given order."""
        reading_list = ReadingList(
            name=name,
            raw_text=raw_text,
            items=[
                ReadingListItem(
                    position=position,
                    citation=item.citation,
                    title=item.title,
                    authors=item.authors,
                    year=item.year,
                    note=item.note,
                )
                for position, item in enumerate(items)
            ],
        )
        db.add(reading_list)
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
        item = db.get(ReadingListItem, item_id)
        if item is None or item.list_id != list_id:
            raise NotFoundError(f"Item {item_id} not found in reading list {list_id}")
        # Naive UTC, matching the other timestamps in this database.
        item.read_at = None if item.read_at else datetime.now(tz=UTC).replace(tzinfo=None)
        db.commit()
        return item

    def progress(self, reading_list: ReadingList) -> ListProgress:
        """Count the ticked items of *reading_list*."""
        items = reading_list.items
        return ListProgress(read=sum(1 for i in items if i.read_at), total=len(items))
