"""Unit tests for IngestionService.ingest_local()."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.drive import DriveUploadError
from src.services.ingestion import DuplicateError, IngestionService
from src.services.types import DriveUploadResult, PaperMetadata

_PDF_BYTES = b"%PDF-1.4 fake"


def _paper_metadata(title: str | None = "Local Paper") -> PaperMetadata:
    return PaperMetadata(
        title=title,
        authors=["Alice"],
        published_date=None,
        abstract=None,
        arxiv_id=None,
    )


def _drive_result() -> DriveUploadResult:
    return {
        "file_id": "drive-file-456",
        "view_url": "https://drive.google.com/file/d/drive-file-456/view",
    }


def _make_db(first_results: list[object] | None = None) -> MagicMock:
    db = MagicMock()
    if first_results is None:
        db.query.return_value.filter.return_value.first.return_value = None
    else:
        db.query.return_value.filter.return_value.first.side_effect = first_results
    return db


def _make_service(
    mock_pdf: MagicMock,
    mock_drive: MagicMock,
) -> IngestionService:
    mock_arxiv = MagicMock()
    with (
        patch("src.services.ingestion.ArxivClient", return_value=mock_arxiv),
        patch("src.services.ingestion.PdfParser", return_value=mock_pdf),
        patch("src.services.ingestion.DriveService", return_value=mock_drive),
    ):
        return IngestionService()


class TestIngestionServiceIngestLocal:
    def test_imports_new_pdf_and_persists_paper_and_note(self) -> None:
        mock_pdf = MagicMock()
        mock_pdf.extract_metadata.return_value = _paper_metadata()
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        db = _make_db()
        svc = _make_service(mock_pdf, mock_drive)
        svc.ingest_local(_PDF_BYTES, Path("C:/tmp/paper.pdf"), db)

        mock_pdf.extract_metadata.assert_called_once_with(_PDF_BYTES)
        mock_drive.upload.assert_called_once()
        assert db.add.call_count == 2
        db.flush.assert_called_once()
        db.commit.assert_called_once()

    def test_raises_duplicate_error_when_submission_url_already_exists(self) -> None:
        mock_pdf = MagicMock()
        mock_drive = MagicMock()

        db = _make_db(first_results=[MagicMock()])
        svc = _make_service(mock_pdf, mock_drive)

        with pytest.raises(DuplicateError):
            svc.ingest_local(_PDF_BYTES, Path("C:/tmp/paper.pdf"), db)

    def test_does_not_commit_on_drive_failure(self) -> None:
        mock_pdf = MagicMock()
        mock_pdf.extract_metadata.return_value = _paper_metadata()
        mock_drive = MagicMock()
        mock_drive.upload.side_effect = DriveUploadError("Drive unavailable")

        db = _make_db()
        svc = _make_service(mock_pdf, mock_drive)

        with pytest.raises(DriveUploadError):
            svc.ingest_local(_PDF_BYTES, Path("C:/tmp/paper.pdf"), db)

        db.commit.assert_not_called()
