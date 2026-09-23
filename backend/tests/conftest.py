"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import pytest

# Import every model so SQLAlchemy can configure its mappers in any test order.
import src.models.batch_job  # noqa: F401
import src.models.note  # noqa: F401
import src.models.paper  # noqa: F401
import src.models.paper_tag  # noqa: F401
import src.models.reading_list  # noqa: F401
import src.models.setting  # noqa: F401
import src.models.tag  # noqa: F401


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
