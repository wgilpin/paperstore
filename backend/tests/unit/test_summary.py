"""Unit tests for SummaryService."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.models.paper import Paper
from src.models.setting import Setting
from src.services.summary import SummaryService


def _make_paper_id() -> uuid.UUID:
    return uuid.uuid4()


def _mock_paper(paper_id: uuid.UUID, extracted_text: str | None = None) -> Paper:
    paper = MagicMock(spec=Paper)
    paper.id = paper_id
    paper.extracted_text = (
        extracted_text if extracted_text is not None else "Full paper text..." * 20
    )
    paper.summary_text = None
    paper.summary_image = None
    paper.drive_file_id = "drive-123"
    return paper


def _mock_setting(value: str = "My background details") -> Setting:
    setting = MagicMock(spec=Setting)
    setting.key = "about_me"
    setting.value = value
    return setting


class TestSummaryServiceGetSummary:
    def test_returns_cached_summary_when_present(self) -> None:
        paper_id = _make_paper_id()
        paper = _mock_paper(paper_id)
        paper.summary_text = "This is a cached summary."
        paper.summary_image = b"some-image-data-here"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = paper

        summary_text, has_image = SummaryService().get_summary(str(paper_id), db)

        assert summary_text == "This is a cached summary."
        assert has_image is True

    def test_returns_none_when_no_summary_cached(self) -> None:
        paper_id = _make_paper_id()
        paper = _mock_paper(paper_id)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = paper

        summary_text, has_image = SummaryService().get_summary(str(paper_id), db)

        assert summary_text is None
        assert has_image is False

    def test_raises_value_error_when_paper_does_not_exist(self) -> None:
        paper_id = _make_paper_id()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Paper not found"):
            SummaryService().get_summary(str(paper_id), db)


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
class TestSummaryServiceGenerateSummary:
    @patch("src.services.summary.genai.Client")
    def test_generates_and_caches_summary_and_image(self, mock_client_class: MagicMock) -> None:
        paper_id = _make_paper_id()
        paper = _mock_paper(paper_id)
        setting = _mock_setting()

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [paper, setting]

        # Mock genai client response
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock text generation response
        text_resp = MagicMock()
        text_resp.text = "Generated AI summary content."

        # Mock image generation response
        image_part = MagicMock()
        image_part.inline_data.data = b"image-raw-bytes"
        image_resp = MagicMock()
        image_resp.parts = [image_part]

        mock_client.models.generate_content.side_effect = [text_resp, image_resp]

        summary_text, has_image = SummaryService().generate_summary(str(paper_id), db)

        assert summary_text == "Generated AI summary content."
        assert has_image is True
        assert paper.summary_text == "Generated AI summary content."
        assert paper.summary_image == b"image-raw-bytes"
        db.commit.assert_called_once()

    @patch("src.services.summary.PdfParser")
    @patch("src.services.summary.DriveService")
    @patch("src.services.summary.genai.Client")
    def test_extracts_text_from_pdf_if_extracted_text_missing(
        self, mock_client_class: MagicMock, mock_drive_class: MagicMock, mock_pdf_class: MagicMock
    ) -> None:
        paper_id = _make_paper_id()
        paper = _mock_paper(paper_id, extracted_text="")
        setting = _mock_setting()

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [paper, setting]

        # Mock Drive download and PDF parsing
        mock_drive = MagicMock()
        mock_drive_class.return_value = mock_drive
        mock_drive.download.return_value = b"%PDF-dummy"

        mock_pdf = MagicMock()
        mock_pdf_class.return_value = mock_pdf
        mock_pdf.extract_full_text.return_value = "Newly extracted PDF text..."

        # Mock genai client responses
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        text_resp = MagicMock()
        text_resp.text = "AI summary."
        mock_client.models.generate_content.return_value = text_resp

        SummaryService().generate_summary(str(paper_id), db)

        # PDF parsing should have been triggered
        mock_drive.download.assert_called_once_with("drive-123")
        mock_pdf.extract_full_text.assert_called_once_with(b"%PDF-dummy")
        assert paper.extracted_text == "Newly extracted PDF text..."

    @patch("src.services.summary.genai.Client")
    def test_handles_image_generation_failures_silently(self, mock_client_class: MagicMock) -> None:
        paper_id = _make_paper_id()
        paper = _mock_paper(paper_id)
        setting = _mock_setting()

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [paper, setting]

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock text generation success
        text_resp = MagicMock()
        text_resp.text = "AI summary text."

        # Mock image generation throwing exception
        mock_client.models.generate_content.side_effect = [
            text_resp,
            Exception("Billing quota exceeded or safety filter triggered"),
        ]

        summary_text, has_image = SummaryService().generate_summary(str(paper_id), db)

        assert summary_text == "AI summary text."
        assert has_image is False
        assert paper.summary_text == "AI summary text."
        assert paper.summary_image is None
        db.commit.assert_called_once()
