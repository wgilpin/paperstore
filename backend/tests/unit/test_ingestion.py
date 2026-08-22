"""Unit tests for IngestionService."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.arxiv_client import ArxivUnavailableError
from src.services.biorxiv_client import BiorxivUnavailableError
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
    mock_biorxiv: MagicMock | None = None,
) -> IngestionService:
    if isinstance(mock_drive.find_file.return_value, MagicMock):
        mock_drive.find_file.return_value = None
    with (
        patch("src.services.ingestion.ArxivClient", return_value=mock_arxiv),
        patch("src.services.ingestion.BiorxivClient", return_value=mock_biorxiv or MagicMock()),
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

    def test_detects_alphaxiv_url_and_delegates_to_arxiv_client(self) -> None:
        mock_arxiv = MagicMock()
        mock_arxiv.fetch.return_value = _paper_metadata(arxiv_id="2608.16753")
        mock_pdf = MagicMock()
        mock_pdf.download_and_extract.return_value = (_paper_metadata(), b"%PDF")
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        svc.ingest("https://www.alphaxiv.org/abs/2608.16753v1", _make_db())

        mock_arxiv.fetch.assert_called_once()
        mock_pdf.download_and_extract.assert_called_once_with("https://arxiv.org/pdf/2608.16753")

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

    def test_arxiv_api_failure_falls_back_to_direct_pdf(self) -> None:
        mock_arxiv = MagicMock()
        mock_arxiv.fetch.side_effect = ArxivUnavailableError("arXiv API down")
        mock_pdf = MagicMock()
        # Ensure pdf_parser extract_metadata returns a fallback metadata dict
        mock_pdf.download_and_extract.return_value = (
            _paper_metadata(title="Direct Fallback Title"),
            b"%PDF",
        )
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        db = _make_db()
        svc = _make_service(mock_arxiv, mock_pdf, mock_drive)
        paper = svc.ingest("https://arxiv.org/abs/2606.99999", db)

        # Confirm fetch failed, and we called download_and_extract with the PDF URL
        mock_arxiv.fetch.assert_called_once()
        mock_pdf.download_and_extract.assert_called_once_with("https://arxiv.org/pdf/2606.99999")

        # Check that the paper has the correct fields populated from fallback and logic
        assert paper.title == "Direct Fallback Title"
        assert paper.arxiv_id == "2606.99999"
        db.commit.assert_called_once()


class TestIngestionServiceBiorxiv:
    _URL = "https://www.biorxiv.org/content/10.64898/2026.02.12.705387v2?utm_source=chatgpt.com"
    _CANONICAL = "https://www.biorxiv.org/content/10.64898/2026.02.12.705387v2"
    _PDF_URL = "https://www.biorxiv.org/content/10.64898/2026.02.12.705387v2.full.pdf"

    def test_delegates_to_biorxiv_client_and_stores_canonical_url(self) -> None:
        mock_arxiv = MagicMock()
        mock_biorxiv = MagicMock()
        mock_biorxiv.fetch.return_value = _paper_metadata(title="Zebra Finch Playbacks")
        mock_pdf = MagicMock()
        mock_pdf.download_and_extract.return_value = (_paper_metadata(), b"%PDF")
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        db = _make_db()
        svc = _make_service(mock_arxiv, mock_pdf, mock_drive, mock_biorxiv)
        svc.ingest(self._URL, db)

        mock_biorxiv.fetch.assert_called_once_with("10.64898/2026.02.12.705387")
        mock_pdf.download_and_extract.assert_called_once_with(self._PDF_URL)
        mock_arxiv.fetch.assert_not_called()

        paper = db.add.call_args_list[0][0][0]
        assert paper.submission_url == self._CANONICAL
        assert paper.title == "Zebra Finch Playbacks"
        assert paper.arxiv_id is None

    def test_falls_back_to_pdf_metadata_when_crossref_unavailable(self) -> None:
        mock_arxiv = MagicMock()
        mock_biorxiv = MagicMock()
        mock_biorxiv.fetch.side_effect = BiorxivUnavailableError("crossref down")
        mock_pdf = MagicMock()
        mock_pdf.download_and_extract.return_value = (
            _paper_metadata(title="PDF Fallback Title"),
            b"%PDF",
        )
        mock_drive = MagicMock()
        mock_drive.upload.return_value = _drive_result()

        db = _make_db()
        svc = _make_service(mock_arxiv, mock_pdf, mock_drive, mock_biorxiv)
        svc.ingest(self._URL, db)

        mock_pdf.download_and_extract.assert_called_once_with(self._PDF_URL)
        paper = db.add.call_args_list[0][0][0]
        assert paper.title == "PDF Fallback Title"

    def test_duplicate_detected_across_tracking_parameters(self) -> None:
        mock_arxiv = MagicMock()
        mock_biorxiv = MagicMock()
        mock_pdf = MagicMock()
        mock_drive = MagicMock()

        db = _make_db(first_results=[MagicMock()])
        svc = _make_service(mock_arxiv, mock_pdf, mock_drive, mock_biorxiv)
        with pytest.raises(DuplicateError):
            svc.ingest(self._URL, db)

        filter_arg = db.query.return_value.filter.call_args[0][0]
        assert self._CANONICAL in str(filter_arg.compile(compile_kwargs={"literal_binds": True}))
