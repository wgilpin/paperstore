"""Unit tests for ReadingListParser."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.services.reading_list_parser import ReadingListParser

_THREE_ITEMS = [
    {
        "citation": "Collins and Loftus (1975), A spreading-activation theory",
        "title": "A spreading-activation theory of semantic processing",
        "authors": ["Collins", "Loftus"],
        "year": 1975,
        "note": "The original model.",
    },
    {
        "citation": "Anderson (1974), Retrieval of propositional information",
        "title": "Retrieval of propositional information from long-term memory",
        "authors": ["Anderson"],
        "year": 1974,
        "note": "The fan effect.",
    },
    {
        "citation": "pymdp",
        "title": "pymdp",
        "authors": [],
        "year": None,
        "note": None,
    },
]


def _mock_client(mock_client_class: MagicMock, text: str | None) -> MagicMock:
    """Make genai.Client(...).models.generate_content return *text*."""
    response = MagicMock()
    response.text = text
    client = MagicMock()
    client.models.generate_content.return_value = response
    mock_client_class.return_value = client
    return client


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_PDF_MODEL": "test-model"})
class TestReadingListParser:
    @patch("src.services.reading_list_parser.genai.Client")
    def test_parses_items_in_order_with_notes(self, mock_client_class: MagicMock) -> None:
        _mock_client(mock_client_class, json.dumps(_THREE_ITEMS))

        items = ReadingListParser().parse("raw list text")

        assert [i.title for i in items] == [
            "A spreading-activation theory of semantic processing",
            "Retrieval of propositional information from long-term memory",
            "pymdp",
        ]
        assert items[0].authors == ["Collins", "Loftus"]
        assert items[0].year == 1975
        assert items[0].note == "The original model."
        assert items[0].citation == "Collins and Loftus (1975), A spreading-activation theory"
        assert items[2].year is None
        assert items[2].note is None

    @patch("src.services.reading_list_parser.genai.Client")
    def test_sends_the_raw_text_to_gemini(self, mock_client_class: MagicMock) -> None:
        client = _mock_client(mock_client_class, "[]")

        ReadingListParser().parse("my pasted list")

        kwargs = client.models.generate_content.call_args.kwargs
        assert kwargs["model"] == "test-model"
        assert "my pasted list" in kwargs["contents"]

    @patch("src.services.reading_list_parser.genai.Client")
    def test_returns_empty_on_invalid_json(self, mock_client_class: MagicMock) -> None:
        _mock_client(mock_client_class, "not json [")

        assert ReadingListParser().parse("raw list text") == []

    @patch("src.services.reading_list_parser.genai.Client")
    def test_returns_empty_on_empty_response(self, mock_client_class: MagicMock) -> None:
        _mock_client(mock_client_class, None)

        assert ReadingListParser().parse("raw list text") == []

    @patch("src.services.reading_list_parser.genai.Client")
    def test_returns_empty_on_gemini_error(self, mock_client_class: MagicMock) -> None:
        client = _mock_client(mock_client_class, "[]")
        client.models.generate_content.side_effect = RuntimeError("503 unavailable")

        assert ReadingListParser().parse("raw list text") == []


class TestReadingListParserConfig:
    @patch.dict("os.environ", {"GEMINI_API_KEY": "", "GEMINI_PDF_MODEL": "test-model"})
    def test_raises_when_api_key_missing(self) -> None:
        with pytest.raises(ValueError):
            ReadingListParser().parse("raw list text")
