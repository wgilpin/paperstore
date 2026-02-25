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
        self._service: Any = None

    def _get_service(self) -> Any:
        if self._service is None:
            token_path = os.environ.get("GOOGLE_TOKEN_PATH", "token.json")
            if not os.path.exists(token_path):
                raise DriveUploadError(
                    f"Google OAuth token not found at {token_path}. "
                    "Complete the OAuth flow first."
                )
            creds = Credentials.from_authorized_user_file(token_path)  # type: ignore[no-untyped-call]
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    def upload(self, pdf_bytes: bytes, filename: str) -> DriveUploadResult:
        """Upload *pdf_bytes* to Drive as *filename*.

        Returns a DriveUploadResult with file_id and view_url.
        Raises DriveUploadError on failure.
        """
        try:
            service = self._get_service()
            media = MediaIoBaseUpload(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                resumable=False,
            )
            folder_id = os.environ.get("DRIVE_FOLDER_ID", "").strip()
            file_metadata: dict[str, object] = {
                "name": filename,
                "mimeType": "application/pdf",
            }
            if folder_id:
                file_metadata["parents"] = [folder_id]
            created = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id,webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
            file_id: str = created["id"]

            # Make the file readable by anyone with the link.
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()

            # Use the /preview URL — it embeds cleanly in iframes unlike /view.
            embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
            return DriveUploadResult(file_id=file_id, view_url=embed_url)
        except Exception as exc:
            raise DriveUploadError(str(exc)) from exc

    def delete(self, file_id: str) -> None:
        """Delete *file_id* from Drive. Silently ignores errors (best-effort)."""
        try:
            service = self._get_service()
            service.files().delete(fileId=file_id).execute()
        except Exception:
            pass
