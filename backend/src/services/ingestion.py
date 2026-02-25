"""Paper ingestion service — orchestrates fetch, upload, and persistence."""

from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from src.models.note import Note
from src.models.paper import Paper
from src.services.arxiv_client import ArxivClient, extract_arxiv_id
from src.services.drive import DriveService
from src.services.pdf_parser import PdfParser

_ARXIV_HOSTNAMES = {"arxiv.org", "ar5iv.labs.arxiv.org"}


class DuplicateError(Exception):
    """Raised when the submitted paper already exists in the library."""


def _is_arxiv_url(url: str) -> bool:
    try:
        hostname = urlparse(url).hostname or ""
        return hostname in _ARXIV_HOSTNAMES or hostname.endswith(".arxiv.org")
    except Exception:
        return False


class IngestionService:
    def __init__(self) -> None:
        self._arxiv = ArxivClient()
        self._pdf = PdfParser()
        self._drive = DriveService()

    def ingest(self, url: str, db: Session) -> Paper:
        """Ingest a paper from *url* into the library.

        Returns the created Paper ORM object.
        Raises DuplicateError if the paper already exists.
        Raises DriveUploadError if the Drive upload fails (no partial record created).
        """
        # Duplicate check by submission URL.
        if db.query(Paper).filter(Paper.submission_url == url).first():
            raise DuplicateError("Paper already exists in your library")

        if _is_arxiv_url(url):
            arxiv_id = extract_arxiv_id(url)
            # Duplicate check by arXiv ID (covers different URL forms of the same paper).
            if db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first():
                raise DuplicateError("Paper already exists in your library")
            metadata = self._arxiv.fetch(url)
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
            _, pdf_bytes = self._pdf.download_and_extract(pdf_url)
        else:
            metadata, pdf_bytes = self._pdf.download_and_extract(url)

        # Upload to Drive — raises DriveUploadError on failure.
        title = metadata.get("title") or "Untitled"
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
        drive_result = self._drive.upload(
            pdf_bytes,
            filename=f"{safe_title}.pdf",
        )
        paper = Paper(
            title=title,
            authors=metadata.get("authors") or [],
            published_date=metadata.get("published_date"),
            abstract=metadata.get("abstract"),
            arxiv_id=metadata.get("arxiv_id"),
            submission_url=url,
            drive_file_id=drive_result["file_id"],
            drive_view_url=drive_result["view_url"],
        )
        db.add(paper)
        db.flush()

        note = Note(paper_id=paper.id, content="")
        db.add(note)
        db.commit()
        db.refresh(paper)
        return paper

    def ingest_local(self, pdf_bytes: bytes, local_path: Path, db: Session) -> Paper:
        """Ingest a locally stored PDF into the library.

        Returns the created Paper ORM object.
        Raises DuplicateError if the paper already exists (by path or title).
        Raises DriveUploadError if the Drive upload fails (no partial record created).
        """
        submission_url = local_path.as_uri()

        if db.query(Paper).filter(Paper.submission_url == submission_url).first():
            raise DuplicateError("Paper already exists in your library")

        metadata = self._pdf.extract_metadata(pdf_bytes)
        title = metadata.get("title") or "Untitled"

        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
        drive_result = self._drive.upload(pdf_bytes, filename=f"{safe_title}.pdf")

        paper = Paper(
            title=title,
            authors=metadata.get("authors") or [],
            published_date=metadata.get("published_date"),
            abstract=metadata.get("abstract"),
            arxiv_id=metadata.get("arxiv_id"),
            submission_url=submission_url,
            drive_file_id=drive_result["file_id"],
            drive_view_url=drive_result["view_url"],
        )
        db.add(paper)
        db.flush()

        note = Note(paper_id=paper.id, content="")
        db.add(note)
        db.commit()
        db.refresh(paper)
        return paper
