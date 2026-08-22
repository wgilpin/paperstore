"""Unit tests for the bioRxiv client."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.services.biorxiv_client import (
    BiorxivClient,
    BiorxivUnavailableError,
    biorxiv_pdf_url,
    canonical_biorxiv_url,
    is_biorxiv_url,
    parse_biorxiv_url,
)

_CROSSREF_MESSAGE = {
    "message": {
        "title": ["Leveraging AI-powered interactive playbacks"],
        "author": [
            {"given": "Logan S.", "family": "James"},
            {"given": "Benjamin", "family": "Hoffman"},
        ],
        "posted": {"date-parts": [[2026, 2, 14]]},
        "abstract": "<jats:p>Vocal interactions are fundamental.</jats:p>",
    }
}


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.biorxiv.org/content/10.64898/2026.02.12.705387v2", True),
        ("https://biorxiv.org/content/10.1101/2020.01.30.927871v1.full.pdf", True),
        ("https://arxiv.org/abs/2301.00001", False),
        ("not a url", False),
    ],
)
def test_is_biorxiv_url(url: str, expected: bool) -> None:
    assert is_biorxiv_url(url) is expected


@pytest.mark.parametrize(
    "url,doi,version",
    [
        (
            "https://www.biorxiv.org/content/10.64898/2026.02.12.705387v2?utm_source=chatgpt.com",
            "10.64898/2026.02.12.705387",
            "2",
        ),
        (
            "https://www.biorxiv.org/content/10.1101/2020.01.30.927871v1.full.pdf",
            "10.1101/2020.01.30.927871",
            "1",
        ),
        (
            "https://www.biorxiv.org/content/10.1101/2020.01.30.927871",
            "10.1101/2020.01.30.927871",
            None,
        ),
        (
            "https://doi.org/10.1101/2020.01.30.927871",
            "10.1101/2020.01.30.927871",
            None,
        ),
    ],
)
def test_parse_biorxiv_url(url: str, doi: str, version: str | None) -> None:
    assert parse_biorxiv_url(url) == (doi, version)


def test_parse_biorxiv_url_rejects_url_without_doi() -> None:
    with pytest.raises(ValueError):
        parse_biorxiv_url("https://www.biorxiv.org/collection/neuroscience")


def test_url_builders() -> None:
    doi = "10.64898/2026.02.12.705387"
    assert canonical_biorxiv_url(doi, "2") == f"https://www.biorxiv.org/content/{doi}v2"
    assert biorxiv_pdf_url(doi, "2") == f"https://www.biorxiv.org/content/{doi}v2.full.pdf"
    assert biorxiv_pdf_url(doi, None) == f"https://www.biorxiv.org/content/{doi}.full.pdf"


def test_fetch_returns_metadata() -> None:
    response = MagicMock()
    response.json.return_value = _CROSSREF_MESSAGE
    with patch("src.services.biorxiv_client.httpx.get", return_value=response) as mock_get:
        metadata = BiorxivClient().fetch(
            "https://www.biorxiv.org/content/10.64898/2026.02.12.705387v2"
        )

    called_url = mock_get.call_args[0][0]
    assert "10.64898/2026.02.12.705387" in called_url
    assert metadata["title"] == "Leveraging AI-powered interactive playbacks"
    assert metadata["authors"] == ["Logan S. James", "Benjamin Hoffman"]
    assert metadata["published_date"] == date(2026, 2, 14)
    assert metadata["abstract"] == "Vocal interactions are fundamental."
    assert metadata["arxiv_id"] is None


def test_fetch_raises_when_crossref_fails() -> None:
    with (
        patch(
            "src.services.biorxiv_client.httpx.get",
            side_effect=httpx.ConnectError("boom"),
        ),
        pytest.raises(BiorxivUnavailableError),
    ):
        BiorxivClient().fetch("10.1101/2020.01.30.927871")
