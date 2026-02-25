"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def db_session() -> MagicMock:
    """Mock database session for unit tests."""
    return MagicMock()


@pytest.fixture()
def mock_drive_client() -> MagicMock:
    """Mock Google Drive API client."""
    return MagicMock()


@pytest.fixture()
def mock_httpx_client() -> MagicMock:
    """Mock httpx client."""
    return MagicMock()
