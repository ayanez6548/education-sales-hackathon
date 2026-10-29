from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cloud import register_webhook
from app.config import Settings, reset_settings
from app.main import create_app


def public_settings(**overrides):
    values = dict(
        _env_file=None, app_env="public_demo", demo_mode=False,
        telegram_adapter="live", telegram_bot_token="test-bot-token",
        telegram_webhook_secret="test-webhook-secret", llm_adapter="openai",
        llm_api_key="test-llm-key", auth_adapter="demo",
        database_url="postgres://test:test@localhost/test",
        public_api_url="https://example.onrender.com",
        jwt_secret="a-random-test-secret-with-at-least-32-characters",
        demo_operator_password="a-random-operator-secret",
        demo_operator_b_password="a-different-operator-secret",
    )
    values.update(overrides)
    return Settings(**values)


def test_public_settings_normalize_render_database_url():
    settings = public_settings()
    settings.validate_runtime()
    assert settings.database_url == "postgresql+psycopg://test:test@localhost/test"


@pytest.mark.parametrize("overrides", [
    {"demo_operator_password": "demo-operador"},
    {"demo_operator_b_password": "demo-operador-b"},
    {"jwt_secret": "short"},
    {"demo_mode": True},
    {"telegram_adapter": "demo"},
    {"llm_adapter": "demo"},
    {"database_url": "sqlite://"},
    {"public_api_url": "http://localhost:8000"},
    {"llm_timeout_seconds": 60, "job_lease_seconds": 45},
])
def test_public_settings_reject_unsafe_deployment(overrides):
    with pytest.raises(RuntimeError):
        public_settings(**overrides).validate_runtime()


def test_webhook_registration_preserves_pending_updates_and_sets_secret(monkeypatch):
    captured = {}

    def post(self, url, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx.Client, "post", post)
    register_webhook(public_settings(register_telegram_webhook=True))
    assert captured == {
        "url": "https://example.onrender.com/webhooks/telegram",
        "secret_token": "test-webhook-secret",
        "allowed_updates": ["message"],
        "drop_pending_updates": False,
    }


def test_webhook_network_error_does_not_expose_bot_token(monkeypatch):
    def post(self, url, **kwargs):
        raise httpx.ConnectError(url)

    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(RuntimeError) as error:
        register_webhook(public_settings(register_telegram_webhook=True))
    assert "test-bot-token" not in str(error.value)
    assert error.value.__suppress_context__ is True


def test_static_dashboard_keeps_api_authentication_and_blocks_traversal(settings, tmp_path, monkeypatch):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html>Panel de operadores</html>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("private", encoding="utf-8")
    monkeypatch.setenv("STATIC_DIRECTORY", str(static))
    reset_settings()
    with TestClient(create_app()) as client:
        assert "Panel de operadores" in client.get("/").text
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/api/me").status_code == 401
        response = client.get("/%2e%2e/secret.txt")
        assert response.status_code == 404
        assert "private" not in response.text
