"""SQLAlchemy engine and session factory."""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def make_engine(database_url: str | None = None) -> Engine:
    url = database_url or _get_database_url()
    return create_engine(url)


# Module-level singletons — created lazily on first access via _get_engine().
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = make_engine()
        _session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_session() -> Session:
    """Return a new database session. Caller is responsible for closing it."""
    _get_engine()
    assert _session_factory is not None
    return _session_factory()


def create_tables() -> None:
    """Create all tables (idempotent — skips existing tables)."""
    Base.metadata.create_all(bind=_get_engine())
