"""Google Drive upload service."""

import io
import os
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from src.services.types import DriveUploadResult


class DriveUploadError(Exception):
    """Raised when a Drive upload fails."""


class DriveService:
    """Uploads PDFs to Google Drive using the authenticated user's account."""

    def __init__(self) -> None:
        self._service: Any = self._build_service()

    @staticmethod
    def _build_service() -> Any:
        token_path = os.environ.get("GOOGLE_TOKEN_PATH", "token.json")
        creds = Credentials.from_authorized_user_file(token_path)  # type: ignore[no-untyped-call]
        return build("drive", "v3", credentials=creds)

    def upload(self, pdf_bytes: bytes, filename: str) -> DriveUploadResult:
        """Upload *pdf_bytes* to Drive as *filename*.

        Returns a DriveUploadResult with file_id and view_url.
        Raises DriveUploadError on failure.
        """
        try:
            media = MediaIoBaseUpload(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                resumable=False,
            )
            file_metadata = {
                "name": filename,
                "mimeType": "application/pdf",
            }
            created = (
                self._service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id,webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
            file_id: str = created["id"]
            view_url: str = created["webViewLink"]

            # Make the file readable by anyone with the link.
            self._service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()

            return DriveUploadResult(file_id=file_id, view_url=view_url)
        except Exception as exc:
            raise DriveUploadError(str(exc)) from exc
