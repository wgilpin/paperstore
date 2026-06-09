"""Unit tests for database string sanitization (NUL character stripping)."""

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.db import _clean_value, _has_nul

Base = declarative_base()


class DummyModel(Base):
    __tablename__ = "dummy_model"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    description = Column(String, nullable=True)


def test_has_nul_helper() -> None:
    assert not _has_nul("Hello World")
    assert _has_nul("Hello\x00World")
    assert not _has_nul(["hello", "world"])
    assert _has_nul(["hello", "world\x00"])
    assert not _has_nul({"key": "value"})
    assert _has_nul({"key": "value\x00"})
    assert not _has_nul(123)
    assert not _has_nul(None)


def test_clean_value_helper() -> None:
    assert _clean_value("Hello\x00World") == "HelloWorld"
    assert _clean_value(["hello\x00", "world"]) == ["hello", "world"]
    assert _clean_value({"key": "val\x00ue"}) == {"key": "value"}
    assert _clean_value(123) == 123
    assert _clean_value(None) is None


def test_db_sanitize_on_insert_and_update() -> None:
    # Setup SQLite in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Test insert sanitization
        dummy = DummyModel(name="Hello\x00World", description="Test\x00Description")
        session.add(dummy)
        session.commit()

        # Retrieve and check
        retrieved = session.query(DummyModel).filter(DummyModel.id == dummy.id).first()
        assert retrieved is not None
        assert retrieved.name == "HelloWorld"
        assert retrieved.description == "TestDescription"

        # 2. Test update sanitization
        retrieved.name = "Updated\x00Name"
        retrieved.description = "Updated\x00Description"
        session.commit()

        # Retrieve again and check
        retrieved_updated = session.query(DummyModel).filter(DummyModel.id == dummy.id).first()
        assert retrieved_updated is not None
        assert retrieved_updated.name == "UpdatedName"
        assert retrieved_updated.description == "UpdatedDescription"

    finally:
        session.close()
        Base.metadata.drop_all(engine)
