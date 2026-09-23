"""Unit tests for OpenAlexClient."""

from unittest.mock import MagicMock, patch

from src.services.openalex_client import OpenAlexClient

_RESPONSE = {
    "results": [
        {
            "display_name": "Why there are complementary learning systems",
            "publication_year": 1995,
            "doi": "https://doi.org/10.1037/0033-295X.102.3.419",
            "type": "article",
            "authorships": [
                {"author": {"display_name": "James L. McClelland"}},
                {"author": {"display_name": "Bruce L. McNaughton"}},
            ],
            "locations": [
                {
                    "landing_page_url": "https://doi.org/10.1037/0033-295x.102.3.419",
                    "pdf_url": None,
                },
                {
                    "landing_page_url": "http://arxiv.org/abs/2102.11174",
                    "pdf_url": "https://arxiv.org/pdf/2102.11174",
                },
                None,
            ],
        },
        {"display_name": None, "publication_year": None, "doi": None, "type": "article"},
    ]
}


class TestOpenAlexClient:
    @patch("src.services.openalex_client.httpx.get")
    def test_parses_best_result(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(json=MagicMock(return_value=_RESPONSE))

        works = OpenAlexClient().search("complementary learning systems")

        assert mock_get.call_args.kwargs["params"]["search"] == "complementary learning systems"
        assert len(works) == 1  # the untitled result is skipped
        work = works[0]
        assert work.title == "Why there are complementary learning systems"
        assert work.year == 1995
        assert work.doi == "10.1037/0033-295x.102.3.419"
        assert work.type == "article"
        assert work.authors == ["James L. McClelland", "Bruce L. McNaughton"]
        assert work.pdf_urls == ["https://arxiv.org/pdf/2102.11174"]
        assert work.arxiv_id == "2102.11174"
        assert work.landing_url == "https://doi.org/10.1037/0033-295x.102.3.419"

    @patch("src.services.openalex_client.httpx.get")
    def test_returns_empty_on_http_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = RuntimeError("503")

        assert OpenAlexClient().search("anything") == []
