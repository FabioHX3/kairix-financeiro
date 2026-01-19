"""
Fixtures compartilhados para testes.
"""

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables BEFORE importing the app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-32-characters"
os.environ["ENVIRONMENT"] = "development"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from backend.core.database import get_db
from backend.core.security import gerar_hash_senha
from backend.main import app
from backend.models import Base, Usuario


# SQLite in-memory database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database override."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> Usuario:
    """Create a test user."""
    user = Usuario(
        nome="Test User",
        email="test@example.com",
        senha_hash=gerar_hash_senha("TestPass123"),
        whatsapp="11999999999",
        ativo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(client: TestClient, test_user: Usuario) -> dict:
    """Get authentication headers for a test user."""
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "senha": "TestPass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def inactive_user(db: Session) -> Usuario:
    """Create an inactive test user."""
    user = Usuario(
        nome="Inactive User",
        email="inactive@example.com",
        senha_hash=gerar_hash_senha("TestPass123"),
        whatsapp="11888888888",
        ativo=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
