"""SQLAlchemy engine and session factory."""

import os

from sqlalchemy import Engine, create_engine, text
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
    """Create all tables and ensure search_vector is a generated column."""
    # Import models so Base.metadata includes them before create_all().
    import src.models.paper_tag  # noqa: F401
    import src.models.tag  # noqa: F401

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)

    # Ensure search_vector is a GENERATED ALWAYS AS stored column.
    # create_all() creates it as a plain nullable TSVECTOR; we need to replace it.
    # This is idempotent: if it's already generated, the DO block exits early.
    _fix_search_vector_sql = """
    DO $$
    BEGIN
        -- Drop and re-add search_vector only if it is not already a generated column.
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'papers'
              AND column_name = 'search_vector'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'papers'
              AND column_name = 'search_vector'
              AND is_generated = 'ALWAYS'
        ) THEN
            ALTER TABLE papers DROP COLUMN search_vector;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'papers'
              AND column_name = 'search_vector'
        ) THEN
            ALTER TABLE papers
                ADD COLUMN search_vector tsvector
                GENERATED ALWAYS AS (
                    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(abstract, '')), 'B')
                ) STORED;
        END IF;

        -- Ensure the GIN index exists.
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'papers' AND indexname = 'idx_papers_search'
        ) THEN
            CREATE INDEX idx_papers_search ON papers USING gin(search_vector);
        END IF;
    END $$;
    """
    with engine.connect() as conn:
        conn.execute(text(_fix_search_vector_sql))
        conn.commit()
