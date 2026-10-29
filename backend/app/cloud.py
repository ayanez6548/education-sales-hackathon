"""Start the single-service cloud demo without any dependency on a developer PC."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
import uvicorn
from alembic import command
from alembic.config import Config

from app.config import Settings, get_settings
from app.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def register_webhook(settings: Settings) -> None:
    if not settings.register_telegram_webhook:
        return
    if settings.telegram_adapter != "live" or not settings.public_api_url.startswith("https://"):
        raise RuntimeError("Webhook registration requires live Telegram and an HTTPS public URL")
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
                json={
                    "url": settings.public_api_url.rstrip("/") + "/webhooks/telegram",
                    "secret_token": settings.telegram_webhook_secret,
                    "allowed_updates": ["message"],
                    "drop_pending_updates": False,
                },
            )
        if response.status_code != 200 or response.json().get("ok") is not True:
            raise RuntimeError("Telegram refused webhook registration; verify deployment secrets")
    except (httpx.HTTPError, ValueError):
        raise RuntimeError("Telegram webhook registration failed; details suppressed to protect bot credentials") from None
    logger.info("Telegram webhook registered successfully")


def main() -> None:
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if external_url and not os.environ.get("PUBLIC_API_URL"):
        os.environ["PUBLIC_API_URL"] = external_url
        os.environ.setdefault("ALLOWED_ORIGINS", external_url)
    settings = get_settings()
    settings.validate_runtime()
    configure_logging()
    if not settings.is_sqlite:
        backend = Path(__file__).resolve().parents[1]
        migration = Config(str(backend / "alembic.ini"))
        migration.set_main_option("script_location", str(backend / "alembic"))
        command.upgrade(migration, "head")
    register_webhook(settings)
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))


if __name__ == "__main__":
    main()
