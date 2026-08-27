"""
pytest fixtures for backend tests.
Uses SQLite in-memory so tests require zero external dependencies.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite://"  # in-memory

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the test session."""
    # Import all models so Base.metadata knows about them
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Per-test DB session — rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """Test client with DB dependency overridden to use in-memory SQLite."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def merchant(db):
    from app.models.merchant import Merchant
    from app.security import generate_api_key, hash_api_key

    plaintext_key = generate_api_key()
    m = Merchant(
        name="Test Merchant",
        email="test@example.com",
        api_key_hash=hash_api_key(plaintext_key),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    m.plaintext_api_key = plaintext_key  # test-only convenience, not a real column
    return m


@pytest.fixture
def auth_headers(merchant):
    """X-API-Key header for the `merchant` fixture, for HTTP-level route tests."""
    return {"X-API-Key": merchant.plaintext_api_key}
