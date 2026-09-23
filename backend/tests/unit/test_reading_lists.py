"""Unit tests for ReadingListService."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.paper import Paper
from src.models.reading_list import ReadingList, ReadingListItem
from src.schemas.reading_list import Candidate, ParsedItem
from src.services.ingestion import DuplicateError
from src.services.notes import NotFoundError
from src.services.reading_lists import ReadingListService


def _item(title: str, year: int | None = 2020, note: str | None = None) -> ParsedItem:
    return ParsedItem(
        citation=f"{title} ({year})", title=title, authors=["A"], year=year, note=note
    )


class TestCreateList:
    def test_create_list_stores_items_with_positions(self) -> None:
        db = MagicMock()
        items = [_item("First", note="Read first."), _item("Second"), _item("Third", year=None)]

        result = ReadingListService().create_list("Memory", "raw pasted text", items, db)

        db.add.assert_called_once_with(result)
        db.commit.assert_called_once()
        assert result.name == "Memory"
        assert result.raw_text == "raw pasted text"
        assert [(i.position, i.title) for i in result.items] == [
            (0, "First"),
            (1, "Second"),
            (2, "Third"),
        ]
        assert result.items[0].note == "Read first."
        assert result.items[0].citation == "First (2020)"
        assert result.items[0].authors == ["A"]
        assert result.items[2].year is None


class TestCreateListParseFailed:
    def test_create_list_with_no_items_marks_parse_failed(self) -> None:
        db = MagicMock()

        result = ReadingListService().create_list("Memory", "raw pasted text", [], db)

        db.add.assert_called_once_with(result)
        assert result.raw_text == "raw pasted text"
        assert result.items == []
        assert result.parse_failed is True

    def test_create_list_with_items_is_not_marked_parse_failed(self) -> None:
        db = MagicMock()

        result = ReadingListService().create_list("Memory", "raw", [_item("First")], db)

        assert result.parse_failed is False


class TestParseAgain:
    def test_parse_again_replaces_items(self) -> None:
        stored = ReadingList(name="Memory", raw_text="raw", parse_failed=True, items=[])
        db = MagicMock()
        db.get.return_value = stored

        result = ReadingListService().parse_again(
            uuid.uuid4(), [_item("First"), _item("Second")], db
        )

        assert result is stored
        assert [(i.position, i.title) for i in stored.items] == [(0, "First"), (1, "Second")]
        assert stored.parse_failed is False
        db.commit.assert_called_once()

    def test_parse_again_with_no_items_keeps_parse_failed(self) -> None:
        stored = ReadingList(name="Memory", raw_text="raw", parse_failed=True, items=[])
        db = MagicMock()
        db.get.return_value = stored

        ReadingListService().parse_again(uuid.uuid4(), [], db)

        assert stored.items == []
        assert stored.parse_failed is True


class TestGetList:
    def test_get_list_returns_the_list(self) -> None:
        db = MagicMock()
        stored = ReadingList(name="Memory", raw_text="raw")
        db.get.return_value = stored

        assert ReadingListService().get_list(uuid.uuid4(), db) is stored

    def test_get_list_unknown_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().get_list(uuid.uuid4(), db)


def _stored_item(list_id: uuid.UUID, read_at: datetime | None = None) -> ReadingListItem:
    return ReadingListItem(
        list_id=list_id, position=0, citation="c", title="t", authors=[], read_at=read_at
    )


class TestToggleTick:
    def test_toggle_tick_sets_read_at(self) -> None:
        list_id = uuid.uuid4()
        item = _stored_item(list_id)
        db = MagicMock()
        db.get.return_value = item

        result = ReadingListService().toggle_tick(list_id, uuid.uuid4(), db)

        assert result is item
        assert item.read_at is not None
        db.commit.assert_called_once()

    def test_toggle_tick_clears_read_at(self) -> None:
        list_id = uuid.uuid4()
        item = _stored_item(list_id, read_at=datetime(2026, 9, 1, 12, 0))
        db = MagicMock()
        db.get.return_value = item

        ReadingListService().toggle_tick(list_id, uuid.uuid4(), db)

        assert item.read_at is None
        db.commit.assert_called_once()

    def test_toggle_tick_unknown_item_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().toggle_tick(uuid.uuid4(), uuid.uuid4(), db)

    def test_toggle_tick_item_of_another_list_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = _stored_item(uuid.uuid4())

        with pytest.raises(NotFoundError):
            ReadingListService().toggle_tick(uuid.uuid4(), uuid.uuid4(), db)
        db.commit.assert_not_called()


class TestProgress:
    def test_progress_counts_ticked_items(self) -> None:
        list_id = uuid.uuid4()
        ticked = datetime(2026, 9, 1, 12, 0)
        reading_list = ReadingList(
            name="Memory",
            raw_text="raw",
            items=[
                _stored_item(list_id, read_at=ticked),
                _stored_item(list_id),
                _stored_item(list_id, read_at=ticked),
                _stored_item(list_id),
            ],
        )

        progress = ReadingListService().progress(reading_list)

        assert (progress.read, progress.total) == (2, 4)


class TestListSummaries:
    def test_list_summaries_newest_first_with_progress(self) -> None:
        older_id, newer_id = uuid.uuid4(), uuid.uuid4()
        older = ReadingList(
            id=older_id,
            name="Older",
            raw_text="raw",
            created_at=datetime(2026, 9, 1, 9, 0),
            items=[_stored_item(older_id, read_at=datetime(2026, 9, 2)), _stored_item(older_id)],
        )
        newer = ReadingList(
            id=newer_id,
            name="Newer",
            raw_text="raw",
            created_at=datetime(2026, 9, 20, 9, 0),
            items=[_stored_item(newer_id)],
        )
        db = MagicMock()
        db.query.return_value.all.return_value = [older, newer]

        summaries = ReadingListService().list_summaries(db)

        assert [s.name for s in summaries] == ["Newer", "Older"]
        assert summaries[0].id == newer_id
        assert summaries[0].created_at == datetime(2026, 9, 20, 9, 0)
        assert (summaries[1].progress.read, summaries[1].progress.total) == (1, 2)


class TestDropItem:
    def test_drop_item_deletes_only_that_item(self) -> None:
        list_id = uuid.uuid4()
        first, second, third = (_stored_item(list_id) for _ in range(3))
        first.position, second.position, third.position = 0, 1, 2
        db = MagicMock()
        db.get.return_value = second

        ReadingListService().drop_item(list_id, uuid.uuid4(), db)

        db.delete.assert_called_once_with(second)
        db.commit.assert_called_once()
        assert (first.position, third.position) == (0, 2)

    def test_drop_item_unknown_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().drop_item(uuid.uuid4(), uuid.uuid4(), db)
        db.delete.assert_not_called()

    def test_drop_item_of_another_list_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = _stored_item(uuid.uuid4())

        with pytest.raises(NotFoundError):
            ReadingListService().drop_item(uuid.uuid4(), uuid.uuid4(), db)
        db.delete.assert_not_called()


class TestDeleteList:
    def test_delete_list_deletes_list(self) -> None:
        stored = ReadingList(name="Memory", raw_text="raw")
        db = MagicMock()
        db.get.return_value = stored

        ReadingListService().delete_list(uuid.uuid4(), db)

        db.delete.assert_called_once_with(stored)
        db.commit.assert_called_once()

    def test_delete_list_unknown_raises_not_found(self) -> None:
        db = MagicMock()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            ReadingListService().delete_list(uuid.uuid4(), db)
        db.delete.assert_not_called()


def _review_item(list_id: uuid.UUID, candidate: Candidate | None, outcome: str) -> ReadingListItem:
    item = _stored_item(list_id)
    item.id = uuid.uuid4()
    item.status = "review"
    item.outcome = outcome
    item.candidate = candidate
    return item


def _library_candidate(paper_id: uuid.UUID) -> Candidate:
    return Candidate(
        source="library",
        title="Dense Associative Memory",
        authors=["Krotov"],
        year=2016,
        paper_id=paper_id,
        confident=True,
        outcome="in_library",
    )


class TestApplyReview:
    def test_accept_library_match_links_item(self) -> None:
        list_id, paper_id = uuid.uuid4(), uuid.uuid4()
        item = _review_item(list_id, _library_candidate(paper_id), "in_library")
        reading_list = ReadingList(id=list_id, name="Memory", raw_text="raw", items=[item])
        db = MagicMock()
        db.get.return_value = reading_list

        ReadingListService().apply_review(list_id, {item.id}, db)

        assert item.paper_id == paper_id
        assert item.status == "done"
        assert item.candidate is None
        db.commit.assert_called_once()

    def test_reject_leaves_text_item(self) -> None:
        list_id = uuid.uuid4()
        item = _review_item(list_id, _library_candidate(uuid.uuid4()), "in_library")
        reading_list = ReadingList(id=list_id, name="Memory", raw_text="raw", items=[item])
        db = MagicMock()
        db.get.return_value = reading_list

        ReadingListService().apply_review(list_id, set(), db)

        assert item.paper_id is None
        assert item.url is None
        assert item.status == "done"
        assert item.candidate is None


class TestPaperItems:
    def test_tick_paper_item_sets_paper_read_at(self) -> None:
        list_id = uuid.uuid4()
        paper = Paper(id=uuid.uuid4(), title="Dense Associative Memory")
        item = _stored_item(list_id)
        item.paper_id, item.paper = paper.id, paper
        db = MagicMock()
        db.get.return_value = item

        ReadingListService().toggle_tick(list_id, uuid.uuid4(), db)
        assert paper.read_at is not None
        assert item.read_at is None

        ReadingListService().toggle_tick(list_id, uuid.uuid4(), db)
        assert paper.read_at is None

    def test_progress_counts_paper_read_at(self) -> None:
        list_id = uuid.uuid4()
        paper = Paper(id=uuid.uuid4(), title="Read paper", read_at=datetime(2026, 9, 1))
        paper_item = _stored_item(list_id)
        paper_item.paper_id, paper_item.paper = paper.id, paper
        reading_list = ReadingList(
            name="Memory", raw_text="raw", items=[paper_item, _stored_item(list_id)]
        )

        progress = ReadingListService().progress(reading_list)

        assert (progress.read, progress.total) == (1, 2)


class _FakeResolver:
    """Stands in for CitationResolver: returns a fixed candidate per title."""

    def __init__(self, by_title: dict[str, Candidate | None]) -> None:
        self.by_title = by_title
        self.seen: list[str] = []

    def resolve(self, query: ParsedItem, db: object) -> Candidate | None:
        self.seen.append(query.title)
        return self.by_title.get(query.title)


class TestLookup:
    def test_run_lookup_stores_candidates_for_unlinked_items(self) -> None:
        list_id = uuid.uuid4()
        found, missing = _stored_item(list_id), _stored_item(list_id)
        found.title, missing.title = "Found", "Missing"
        found.status = missing.status = "new"
        reading_list = ReadingList(id=list_id, name="L", raw_text="raw", items=[found, missing])
        db = MagicMock()
        db.get.return_value = reading_list
        candidate = _library_candidate(uuid.uuid4())

        ReadingListService().lookup_list(
            list_id, db, _FakeResolver({"Found": candidate, "Missing": None})
        )

        assert (found.status, found.outcome, found.candidate) == ("review", "in_library", candidate)
        assert (missing.status, missing.outcome, missing.candidate) == ("review", "not_found", None)

    def test_run_lookup_skips_linked_items(self) -> None:
        list_id = uuid.uuid4()
        linked = _stored_item(list_id)
        linked.title, linked.status, linked.paper_id = "Linked", "done", uuid.uuid4()
        reading_list = ReadingList(id=list_id, name="L", raw_text="raw", items=[linked])
        db = MagicMock()
        db.get.return_value = reading_list
        resolver = _FakeResolver({})

        ReadingListService().lookup_list(list_id, db, resolver)

        assert resolver.seen == []
        assert linked.status == "done"


class TestApplyReviewOutside:
    def test_accept_record_only_sets_doi_link(self) -> None:
        list_id = uuid.uuid4()
        candidate = Candidate(
            source="openalex",
            title="Computational principles of synaptic memory consolidation",
            authors=["Benna"],
            year=2016,
            doi="10.1038/nn.4401",
            landing_url="https://doi.org/10.1038/nn.4401",
            confident=True,
            outcome="record_only",
        )
        item = _review_item(list_id, candidate, "record_only")
        reading_list = ReadingList(id=list_id, name="Memory", raw_text="raw", items=[item])
        db = MagicMock()
        db.get.return_value = reading_list

        ReadingListService().apply_review(list_id, {item.id}, db)

        assert item.url == "https://doi.org/10.1038/nn.4401"
        assert item.paper_id is None
        assert item.status == "done"


def _free_pdf_candidate(arxiv_id: str | None = "2203.08913") -> Candidate:
    return Candidate(
        source="arxiv" if arxiv_id else "openalex",
        title="Memorizing Transformers",
        authors=["Wu"],
        year=2022,
        arxiv_id=arxiv_id,
        doi="10.48550/arxiv.2203.08913",
        pdf_url="https://example.org/memorizing.pdf",
        landing_url="https://example.org/memorizing",
        confident=True,
        outcome="free_pdf",
    )


class _FakeIngestion:
    """Stands in for IngestionService: returns a paper, or raises a set error."""

    def __init__(self, result: Paper | Exception) -> None:
        self.result = result
        self.urls: list[str] = []

    def ingest(self, url: str, db: object) -> Paper:
        self.urls.append(url)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _importing_item(candidate: Candidate) -> ReadingListItem:
    item = _review_item(uuid.uuid4(), candidate, "free_pdf")
    item.status = "importing"
    return item


_SVC = "src.services.reading_lists"


class TestImport:
    def test_accept_free_pdf_marks_importing(self) -> None:
        list_id = uuid.uuid4()
        item = _review_item(list_id, _free_pdf_candidate(), "free_pdf")
        reading_list = ReadingList(id=list_id, name="Memory", raw_text="raw", items=[item])
        db = MagicMock()
        db.get.return_value = reading_list

        to_import = ReadingListService().apply_review(list_id, {item.id}, db)

        assert item.status == "importing"
        assert item.candidate is not None  # the importer needs it
        assert to_import == [item.id]

    @patch(f"{_SVC}.library_by_doi", return_value=None)
    def test_import_links_new_paper_and_sets_doi(self, by_doi: MagicMock) -> None:
        item = _importing_item(_free_pdf_candidate())
        paper = Paper(id=uuid.uuid4(), title="Memorizing Transformers")
        db = MagicMock()
        db.get.return_value = item
        ingestion = _FakeIngestion(paper)

        ReadingListService().import_item(item.id, db, ingestion)

        assert ingestion.urls == ["https://arxiv.org/abs/2203.08913"]
        assert item.paper_id == paper.id
        assert item.status == "done"
        assert item.candidate is None
        assert paper.doi == "10.48550/arxiv.2203.08913"

    @patch(f"{_SVC}.library_by_doi", return_value=None)
    def test_import_without_arxiv_id_uses_the_pdf_url(self, by_doi: MagicMock) -> None:
        item = _importing_item(_free_pdf_candidate(arxiv_id=None))
        db = MagicMock()
        db.get.return_value = item
        ingestion = _FakeIngestion(Paper(id=uuid.uuid4(), title="t"))

        ReadingListService().import_item(item.id, db, ingestion)

        assert ingestion.urls == ["https://example.org/memorizing.pdf"]

    def test_import_duplicate_links_existing_paper(self) -> None:
        item = _importing_item(_free_pdf_candidate())
        existing_id = uuid.uuid4()
        db = MagicMock()
        db.get.return_value = item

        ReadingListService().import_item(
            item.id, db, _FakeIngestion(DuplicateError("exists", paper_id=str(existing_id)))
        )

        assert item.paper_id == existing_id
        assert item.status == "done"

    def test_import_failure_marks_item_and_keeps_url(self) -> None:
        item = _importing_item(_free_pdf_candidate())
        db = MagicMock()
        db.get.return_value = item

        ReadingListService().import_item(item.id, db, _FakeIngestion(RuntimeError("HTTP 403")))

        db.rollback.assert_called_once()
        assert item.status == "import_failed"
        assert item.paper_id is None
        assert item.url == "https://example.org/memorizing"
        assert item.candidate is not None  # kept for a retry

    def test_reset_stuck_imports_marks_import_failed(self) -> None:
        stuck = _importing_item(_free_pdf_candidate())
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [stuck]

        count = ReadingListService().reset_stuck_imports(db)

        assert count == 1
        assert stuck.status == "import_failed"
        assert stuck.url == "https://example.org/memorizing"
        db.commit.assert_called_once()


class _FakeLocalIngestion:
    """Stands in for IngestionService.ingest_local."""

    def __init__(self, result: Paper | Exception) -> None:
        self.result = result
        self.calls: list[tuple[bytes, str, str | None]] = []

    def ingest_local(
        self, pdf_bytes: bytes, local_path: object, db: object, source_url: str | None = None
    ) -> Paper:
        self.calls.append((pdf_bytes, str(local_path), source_url))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _record_only_item(list_id: uuid.UUID) -> ReadingListItem:
    item = _stored_item(list_id)
    item.status = "done"
    item.url = "https://doi.org/10.1038/nn.4401"
    return item


_PDF = b"%PDF-1.7 fake body"


class TestUploadPdf:
    @patch(f"{_SVC}.library_by_doi", return_value=None)
    def test_upload_pdf_links_item_and_sets_doi(self, by_doi: MagicMock) -> None:
        list_id = uuid.uuid4()
        item = _record_only_item(list_id)
        paper = Paper(id=uuid.uuid4(), title="Computational principles")
        db = MagicMock()
        db.get.return_value = item
        ingestion = _FakeLocalIngestion(paper)

        ReadingListService().upload_pdf(list_id, uuid.uuid4(), _PDF, "benna.pdf", db, ingestion)

        assert ingestion.calls == [(_PDF, "benna.pdf", "https://doi.org/10.1038/nn.4401")]
        assert item.paper_id == paper.id
        assert item.status == "done"
        assert paper.doi == "10.1038/nn.4401"
        db.commit.assert_called_once()

    def test_upload_non_pdf_is_refused(self) -> None:
        list_id = uuid.uuid4()
        item = _record_only_item(list_id)
        db = MagicMock()
        db.get.return_value = item
        ingestion = _FakeLocalIngestion(Paper(id=uuid.uuid4(), title="t"))

        with pytest.raises(ValueError):
            ReadingListService().upload_pdf(
                list_id, uuid.uuid4(), b"hello", "notes.pdf", db, ingestion
            )
        assert ingestion.calls == []
        assert item.paper_id is None
        db.commit.assert_not_called()

    def test_upload_duplicate_links_existing_paper(self) -> None:
        list_id = uuid.uuid4()
        item = _record_only_item(list_id)
        existing_id = uuid.uuid4()
        db = MagicMock()
        db.get.return_value = item

        ReadingListService().upload_pdf(
            list_id,
            uuid.uuid4(),
            _PDF,
            "benna.pdf",
            db,
            _FakeLocalIngestion(DuplicateError("exists", paper_id=str(existing_id))),
        )

        assert item.paper_id == existing_id

    def test_upload_only_for_items_without_paper(self) -> None:
        list_id = uuid.uuid4()
        item = _record_only_item(list_id)
        item.paper_id = uuid.uuid4()
        db = MagicMock()
        db.get.return_value = item
        ingestion = _FakeLocalIngestion(Paper(id=uuid.uuid4(), title="t"))

        with pytest.raises(ValueError):
            ReadingListService().upload_pdf(list_id, uuid.uuid4(), _PDF, "x.pdf", db, ingestion)
        assert ingestion.calls == []
