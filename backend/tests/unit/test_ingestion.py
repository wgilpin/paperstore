"""Unit tests for IngestionService."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.drive import DriveUploadError
from src.services.ingestion import DuplicateError, IngestionService
from src.services.types import DriveUploadResult, PaperMetadata


def _paper_metadata(
    title: str | None = "Test Paper",
    authors: list[str] | None = None,
    abstract: str | None = "Some abstract.",
    arxiv_id: str | None = None,
) -> PaperMetadata:
    return PaperMetadata(
        title=title,
        authors=authors if authors is not None else ["Alice"],
        published_date=None,
        abstract=abstract,
        arxiv_id=arxiv_id,
    )


def _drive_result() -> DriveUploadResult:
    return {
        "file_id": "drive-file-123",
        "view_url": "https://drive.google.com/file/d/drive-file-123/view",
    }


def _make_db(first_results: list[object] | None = None) -> MagicMock:
    """Return a MagicMock db session.

    *first_results* controls successive return values of .query().filter().first().
    Defaults to all-None (no duplicates found).
    """
    db = MagicMock()
    if first_results is None:
        db.query.return_value.filter.return_value.first.return_value = None
    else:
        db.query.return_value.filter.return_value.first.side_effect = first_results
    return db


def _make_service(
    mock_arxiv: MagicMock,
    mock_pdf: MagicMock,
    mock_drive: MagicMock,
) -> IngestionService:
    with (
        patch("src.services.ingestion.ArxivClient", return_value=mock_arxiv),
        patch("src.services.ingestion.PdfParser", return_value=mock_pdf),
        patch("src.services.ingestion.DriveService", return_value=mock_drive),
    ):
        return IngestionService()


class TestIngestionServiceIngest:
    def test_detects_arxiv_url_and_delegates_to_arxiv_client(self) -> None:
        mock_arxiv = MagicMock()
        mock_arxiv.fetch.return_value = _paper_metadata(arxiv_id="2301.00001")
        mock_pdf = MagicMock()
        mock_pdf.download_and_extract.return_value = (_paper_metadata(), b"%PDF")
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        svc.ingest("https://arxiv.org/abs/2301.00001", _make_db())

        mock_arxiv.fetch.assert_called_once()
        # PdfParser downloads the PDF bytes for arXiv papers too
        mock_pdf.download_and_extract.assert_called_once()

    def test_detects_plain_pdf_url_and_delegates_to_pdf_parser(self) -> None:
        mock_arxiv = MagicMock()
        mock_pdf = MagicMock()
        mock_pdf.download_and_extract.return_value = (_paper_metadata(), b"%PDF")
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        svc.ingest("https://example.com/paper.pdf", _make_db())

        mock_pdf.download_and_extract.assert_called_once()
        mock_arxiv.fetch.assert_not_called()

    def test_raises_duplicate_error_when_submission_url_already_exists(self) -> None:
        mock_arxiv = MagicMock()
        mock_pdf = MagicMock()
        mock_drive = MagicMock()

        # First .first() returns an existing paper (submission_url match).
        db = _make_db(first_results=[MagicMock()])

        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        with pytest.raises(DuplicateError):
            svc.ingest("https://example.com/paper.pdf", db)

    def test_raises_duplicate_error_when_arxiv_id_already_exists(self) -> None:
        mock_arxiv = MagicMock()
        mock_arxiv.fetch.return_value = _paper_metadata(arxiv_id="2301.00001")
        mock_pdf = MagicMock()
        mock_drive = MagicMock()

        # First .first() → None (no submission_url match), second → existing (arxiv_id match).
        db = _make_db(first_results=[None, MagicMock()])

        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        with pytest.raises(DuplicateError):
            svc.ingest("https://arxiv.org/abs/2301.00001", db)

    def test_persists_paper_and_note_on_success(self) -> None:
        mock_arxiv = MagicMock()
        mock_arxiv.fetch.return_value = _paper_metadata(arxiv_id="2301.99999")
        mock_pdf = MagicMock()
        mock_pdf.download_and_extract.return_value = (_paper_metadata(), b"%PDF")
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        db = _make_db()
        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        svc.ingest("https://arxiv.org/abs/2301.99999", db)

        # db.add called twice (Paper + Note), then flush + commit.
        assert db.add.call_count == 2
        db.flush.assert_called_once()
        db.commit.assert_called_once()

    def test_does_not_commit_on_drive_failure(self) -> None:
        mock_arxiv = MagicMock()
        mock_arxiv.fetch.return_value = _paper_metadata(arxiv_id="2301.88888")
        mock_pdf = MagicMock()
        mock_pdf.download_and_extract.return_value = (_paper_metadata(), b"%PDF")
        mock_drive = MagicMock()
        mock_drive.upload.side_effect = DriveUploadError("Drive unavailable")

        db = _make_db()
        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        with pytest.raises(DriveUploadError):
            svc.ingest("https://arxiv.org/abs/2301.88888", db)

        db.commit.assert_not_called()
