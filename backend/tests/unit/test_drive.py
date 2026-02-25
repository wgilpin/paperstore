"""Unit tests for DriveService."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.drive import DriveService, DriveUploadError


class TestDriveServiceUpload:
    def _make_service(self) -> tuple[DriveService, MagicMock]:
        mock_drive = MagicMock()
        with patch("src.services.drive.DriveService._build_service", return_value=mock_drive):
            svc = DriveService()
        svc._service = mock_drive
        return svc, mock_drive

    def test_returns_drive_upload_result_with_file_id_and_view_url(self) -> None:
        svc, mock_drive = self._make_service()

        mock_create = MagicMock()
        mock_create.execute.return_value = {
            "id": "file-abc-123",
            "webViewLink": "https://drive.google.com/file/d/file-abc-123/view",
        }
        mock_drive.files.return_value.create.return_value = mock_create

        mock_perm = MagicMock()
        mock_perm.execute.return_value = {}
        mock_drive.permissions.return_value.create.return_value = mock_perm

        result = svc.upload(b"%PDF fake", "paper.pdf")

        assert result["file_id"] == "file-abc-123"
        assert "drive.google.com" in result["view_url"]

    def test_raises_drive_upload_error_on_api_failure(self) -> None:
        svc, mock_drive = self._make_service()

        mock_create = MagicMock()
        mock_create.execute.side_effect = Exception("API quota exceeded")
        mock_drive.files.return_value.create.return_value = mock_create

        with pytest.raises(DriveUploadError, match="quota exceeded"):
            svc.upload(b"%PDF fake", "paper.pdf")
