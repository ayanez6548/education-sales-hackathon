"""Receive private Telegram messages locally without a public webhook URL."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from app.config import DATA_DIR, Settings, get_settings
from app.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def load_offset(path: Path) -> int | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))["next_offset"]
    if type(value) is not int or value < 0:
        raise ValueError("Invalid polling cursor")
    return value


def save_offset(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"next_offset": value}), encoding="utf-8")
    temporary.replace(path)


def forward_updates(client: httpx.Client, settings: Settings, updates: list[dict], cursor_path: Path) -> int | None:
    offset = load_offset(cursor_path)
    for update in updates:
        update_id = update.get("update_id")
        if type(update_id) is not int:
            raise ValueError("Invalid Telegram update identifier")
        if offset is not None and update_id < offset:
            continue
        message = update.get("message") or {}
        if message.get("text") and (message.get("chat") or {}).get("type") == "private":
            response = client.post(
                settings.public_api_url.rstrip("/") + "/webhooks/telegram",
                json=update,
                headers={"X-Telegram-Bot-Api-Secret-Token": settings.telegram_webhook_secret},
            )
            response.raise_for_status()
            if response.json().get("status") != "ok":
                raise RuntimeError("Backend did not accept the update")
            logger.info("Telegram update persisted update_id=%s", update_id)
        # Telegram acknowledges this update on the next getUpdates call, after durable storage.
        offset = update_id + 1
        save_offset(cursor_path, offset)
    return offset


def main() -> None:
    configure_logging()
    settings = get_settings()
    settings.validate_runtime()
    if settings.telegram_adapter != "live":
        raise RuntimeError("TELEGRAM_ADAPTER must be live for local polling")
    cursor = DATA_DIR / "telegram_polling_cursor.json"
    base = "https://api.telegram.org/bot" + settings.telegram_bot_token
    with httpx.Client(timeout=30, trust_env=False) as client:
        metadata = client.get(base + "/getWebhookInfo")
        metadata.raise_for_status()
        information = metadata.json()
        if not information.get("ok"):
            raise RuntimeError("Telegram rejected webhook information request")
        if information["result"].get("url"):
            raise RuntimeError("A webhook is active; polling will not replace it")
        health = client.get(settings.public_api_url.rstrip("/") + "/health/ready")
        health.raise_for_status()
        logger.info("Telegram local polling started llm_adapter=%s", settings.llm_adapter)
        failures = 0
        while True:
            try:
                payload = {"timeout": 20, "allowed_updates": ["message"]}
                offset = load_offset(cursor)
                if offset is not None:
                    payload["offset"] = offset
                response = client.post(base + "/getUpdates", json=payload)
                if response.status_code in {401, 409}:
                    logger.error("Telegram polling stopped status=%s", response.status_code)
                    return
                response.raise_for_status()
                result = response.json()
                if not result.get("ok"):
                    raise RuntimeError("Telegram rejected polling request")
                forward_updates(client, settings, result["result"], cursor)
                failures = 0
            except (httpx.HTTPError, RuntimeError, ValueError, OSError) as error:
                failures += 1
                logger.warning("Polling retry failure_type=%s", type(error).__name__)
                time.sleep(min(30, 2 ** min(failures, 5)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Telegram local polling stopped")
    except Exception as error:
        logger.error("Telegram polling startup failed failure_type=%s", type(error).__name__)
        raise SystemExit(1) from None
