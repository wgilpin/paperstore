"""SQLAlchemy engine and session factory."""

import os
from collections.abc import Generator

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


def get_session() -> Generator[Session, None, None]:
    """Yield a database session and close it when the request is done."""
    _get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def create_tables() -> None:
    """Create all tables and ensure search_vector is a generated column."""
    # Import models so Base.metadata includes them before create_all().
    import src.models.batch_job  # noqa: F401
    import src.models.paper_tag  # noqa: F401
    import src.models.tag  # noqa: F401

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)

    # Maintain search_vector via a trigger (GENERATED ALWAYS AS cannot use
    # array_to_string, which is STABLE not IMMUTABLE).
    # This is idempotent: safe to run on every startup.
    _fix_search_vector_sql = """
    DO $$
    BEGIN
        -- If search_vector is still a generated column from an old migration, drop it
        -- so we can recreate it as a plain column owned by the trigger.
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'papers'
              AND column_name = 'search_vector'
              AND is_generated = 'ALWAYS'
        ) THEN
            ALTER TABLE papers DROP COLUMN search_vector;
        END IF;

        -- Add as a plain tsvector column if absent.
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'papers' AND column_name = 'search_vector'
        ) THEN
            ALTER TABLE papers ADD COLUMN search_vector tsvector;
        END IF;

        -- Ensure GIN index exists.
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'papers' AND indexname = 'idx_papers_search'
        ) THEN
            CREATE INDEX idx_papers_search ON papers USING gin(search_vector);
        END IF;

        -- Create or replace the trigger function.
        CREATE OR REPLACE FUNCTION papers_search_vector_update() RETURNS trigger AS $func$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.abstract, '')), 'B') ||
                setweight(to_tsvector('simple',  coalesce(array_to_string(NEW.authors, ' '), '')), 'C');
            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;

        -- Create trigger if absent.
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'papers_search_vector_trigger'
        ) THEN
            CREATE TRIGGER papers_search_vector_trigger
                BEFORE INSERT OR UPDATE ON papers
                FOR EACH ROW EXECUTE FUNCTION papers_search_vector_update();
        END IF;
    END $$;

    -- Backfill existing rows that have a NULL search_vector.
    UPDATE papers
       SET search_vector =
               setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
               setweight(to_tsvector('english', coalesce(abstract, '')), 'B') ||
               setweight(to_tsvector('simple',  coalesce(array_to_string(authors, ' '), '')), 'C')
     WHERE search_vector IS NULL;
    """
    with engine.connect() as conn:
        conn.execute(text(_fix_search_vector_sql))
        conn.commit()
