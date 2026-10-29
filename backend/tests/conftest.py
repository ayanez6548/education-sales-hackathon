from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bootstrap import prepare_database
from app.config import reset_settings, get_settings
from app.database import get_session_factory
from app.main import create_app
from app.models import OperatorProfile
from sqlalchemy import select


@pytest.fixture()
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = (tmp_path / "test.db").as_posix()
    monkeypatch.setenv("APP_ENV", "demo")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("EMBED_WORKER", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("TELEGRAM_ADAPTER", "demo")
    monkeypatch.setenv("LLM_ADAPTER", "demo")
    monkeypatch.setenv("AUTH_ADAPTER", "demo")
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    reset_settings()
    current = get_settings()
    current.validate_runtime()
    prepare_database(current)
    yield current
    reset_settings()


@pytest.fixture()
def session(settings) -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def app(settings):
    return create_app()


@pytest.fixture()
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def operator_a(session: Session, settings) -> OperatorProfile:
    return session.execute(
        select(OperatorProfile).where(OperatorProfile.email == settings.demo_operator_email)
    ).scalar_one()


@pytest.fixture()
def operator_b(session: Session, settings) -> OperatorProfile:
    return session.execute(
        select(OperatorProfile).where(OperatorProfile.email == settings.demo_operator_b_email)
    ).scalar_one()


def login(client: TestClient, settings, email: str | None = None, password: str | None = None) -> str:
    response = client.post(
        "/api/auth/login",
        json={
            "email": email or settings.demo_operator_email,
            "password": password or settings.demo_operator_password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
